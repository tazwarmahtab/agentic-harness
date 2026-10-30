"""Transactional prospect jobs, original sources, immutable outputs and review events."""

from __future__ import annotations

import builtins
import hashlib
import json
import os
import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

from aos.prospects.ingest import MAX_TEXT_CHARS, MAX_TOTAL_BYTES, extract
from aos.prospects.models import Analysis, Intake, Passage
from aos.prospects.workflow import Analyzer, build_output, extractive_analysis

JsonObject = dict[str, Any]


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


class ProspectStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            pass
        else:
            os.close(descriptor)
        path.chmod(0o600)
        with self._db() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, venture TEXT NOT NULL, project TEXT NOT NULL, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS sources(id TEXT PRIMARY KEY, job_id TEXT NOT NULL, filename TEXT NOT NULL, raw BLOB NOT NULL);
                CREATE TABLE IF NOT EXISTS versions(job_id TEXT NOT NULL, output_hash TEXT NOT NULL, data TEXT NOT NULL, at REAL NOT NULL, PRIMARY KEY(job_id,output_hash));
                CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL, kind TEXT NOT NULL, at REAL NOT NULL, data TEXT NOT NULL);
            """)
        path.chmod(0o600)

    @contextmanager
    def _db(self) -> Iterator[sqlite3.Connection]:
        with sqlite3.connect(self.path, timeout=30) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("BEGIN IMMEDIATE")
            yield db

    def _get(
        self, db: sqlite3.Connection, job_id: str, venture: str, project: str
    ) -> JsonObject:
        row = db.execute(
            "SELECT data FROM jobs WHERE id=? AND venture=? AND project=?",
            (job_id, venture, project),
        ).fetchone()
        if row is None:
            raise KeyError("Prospect job not found")
        return dict(json.loads(row[0]))

    def _save(
        self,
        db: sqlite3.Connection,
        job: JsonObject,
        kind: str,
        details: JsonObject | None = None,
    ) -> None:
        db.execute("UPDATE jobs SET data=? WHERE id=?", (_json(job), job["id"]))
        db.execute(
            "INSERT INTO events(job_id,kind,at,data) VALUES(?,?,?,?)",
            (job["id"], kind, time.time(), _json(details or {})),
        )

    def create(self, request: Intake) -> JsonObject:
        extracted = [extract(document) for document in request.documents]
        if sum(len(raw) for _, raw, _ in extracted) > MAX_TOTAL_BYTES:
            raise ValueError("Combined documents exceed 10 MiB")
        if (
            sum(len(p.text) for _, _, pages in extracted for p in pages)
            > MAX_TEXT_CHARS
        ):
            raise ValueError("Combined extracted text exceeds 120,000 characters")
        job = {
            "id": str(uuid4()),
            "venture": request.venture,
            "project": request.project,
            "prospect": request.prospect,
            "purpose": request.purpose,
            "status": "received",
            "sources": [item for item, _, _ in extracted],
            "output": None,
            "output_hash": None,
            "review": None,
            "mode": None,
            "send_authorized": False,
            "created_at": time.time(),
        }
        with self._db() as db:
            db.execute(
                "INSERT INTO jobs VALUES(?,?,?,?)",
                (job["id"], request.venture, request.project, _json(job)),
            )
            for item, raw, _ in extracted:
                db.execute(
                    "INSERT INTO sources VALUES(?,?,?,?)",
                    (item["id"], job["id"], item["filename"], raw),
                )
            self._save(db, job, "received")
        return job

    def get(self, job_id: str, venture: str, project: str) -> JsonObject:
        with self._db() as db:
            return self._get(db, job_id, venture, project)

    def list(self, venture: str, project: str) -> builtins.list[JsonObject]:
        with self._db() as db:
            return [
                json.loads(row[0])
                for row in db.execute(
                    "SELECT data FROM jobs WHERE venture=? AND project=? ORDER BY rowid DESC LIMIT 100",
                    (venture, project),
                )
            ]

    def source(
        self, job_id: str, source_id: str, venture: str, project: str
    ) -> tuple[str, bytes]:
        with self._db() as db:
            self._get(db, job_id, venture, project)
            row = db.execute(
                "SELECT filename,raw FROM sources WHERE job_id=? AND id=?",
                (job_id, source_id),
            ).fetchone()
            if row is None:
                raise KeyError("Source not found")
            return row[0], row[1]

    def events(
        self, job_id: str, venture: str, project: str
    ) -> builtins.list[JsonObject]:
        with self._db() as db:
            self._get(db, job_id, venture, project)
            return [
                {"kind": r[0], "at": r[1], "data": json.loads(r[2])}
                for r in db.execute(
                    "SELECT kind,at,data FROM events WHERE job_id=? ORDER BY seq",
                    (job_id,),
                )
            ]

    def generate(
        self, job_id: str, venture: str, project: str, analyzer: Analyzer | None = None
    ) -> JsonObject:
        attempt = str(uuid4())
        with self._db() as db:
            job = self._get(db, job_id, venture, project)
            if job["output"] is not None:
                return job
            if job["status"] == "analyzing" and job.get("lease_until", 0) > time.time():
                raise ValueError("Analysis already running; retry after lease expiry")
            job.update(
                status="analyzing", attempt=attempt, lease_until=time.time() + 120
            )
            self._save(db, job, "analysis_started")
        try:
            passages = [
                Passage.model_validate(p)
                for source in job["sources"]
                for p in source["passages"]
            ]
            analysis = Analysis.model_validate(
                (analyzer or extractive_analysis)(passages)
            )
            output = build_output(passages, job["prospect"], analysis)
            output["version_id"] = str(uuid4())
            with self._db() as db:
                current = self._get(db, job_id, venture, project)
                if current.get("attempt") != attempt:
                    raise ValueError("Analysis lease was superseded; result discarded")
                current.update(
                    status="needs_review",
                    output=output,
                    output_hash=hashlib.sha256(_json(output).encode()).hexdigest(),
                    mode="model_selected" if analyzer else "extractive",
                    error=None,
                )
                db.execute(
                    "INSERT INTO versions VALUES(?,?,?,?)",
                    (job_id, current["output_hash"], _json(output), time.time()),
                )
                self._save(
                    db,
                    current,
                    "output_created",
                    {"output_hash": current["output_hash"]},
                )
                return current
        except Exception:
            with self._db() as db:
                current = self._get(db, job_id, venture, project)
                if current.get("attempt") == attempt:
                    current.update(
                        status="failed",
                        error="Analysis failed validation or execution; original sources preserved.",
                    )
                    self._save(db, current, "analysis_failed")
            raise

    def review(
        self,
        job_id: str,
        venture: str,
        project: str,
        output_hash: str,
        decision: str,
        reviewer: str,
    ) -> JsonObject:
        if decision not in {"approve", "reject", "defer"} or not reviewer.strip():
            raise ValueError("Invalid review decision or reviewer")
        with self._db() as db:
            job = self._get(db, job_id, venture, project)
            if not job["output"] or output_hash != job["output_hash"]:
                raise ValueError("Output version changed or is not ready")
            if job["status"] in {"approved", "rejected"}:
                if (
                    job["review"]["decision"] == decision
                    and job["review"]["reviewer"] == reviewer
                ):
                    return job
                raise ValueError("Output already decided")
            review = {
                "decision": decision,
                "reviewer": reviewer,
                "output_hash": output_hash,
            }
            if job["review"] == review:
                return job
            job.update(
                status={
                    "approve": "approved",
                    "reject": "rejected",
                    "defer": "needs_review",
                }[decision],
                review=review,
            )
            self._save(db, job, "reviewed", review)
            return job

    def versions(
        self, job_id: str, venture: str, project: str
    ) -> builtins.list[JsonObject]:
        with self._db() as db:
            self._get(db, job_id, venture, project)
            return [
                {"output_hash": row[0], "output": json.loads(row[1]), "at": row[2]}
                for row in db.execute(
                    "SELECT output_hash,data,at FROM versions WHERE job_id=? ORDER BY at",
                    (job_id,),
                )
            ]

    def edit_draft(
        self, job_id: str, venture: str, project: str, output_hash: str, text: str
    ) -> JsonObject:
        if not text.strip() or len(text) > 10000:
            raise ValueError("Draft must contain 1–10,000 characters")
        with self._db() as db:
            job = self._get(db, job_id, venture, project)
            if not job["output"] or job["output_hash"] != output_hash:
                raise ValueError("Output version changed or is not ready")
            if job["output"]["follow_up"] == text:
                return job
            job["output"]["version_id"] = str(uuid4())
            job["output"]["follow_up"] = text
            job["output"]["follow_up_author"] = "founder-edited"
            job["output_hash"] = hashlib.sha256(
                _json(job["output"]).encode()
            ).hexdigest()
            job.update(status="needs_review", review=None)
            db.execute(
                "INSERT OR IGNORE INTO versions VALUES(?,?,?,?)",
                (job_id, job["output_hash"], _json(job["output"]), time.time()),
            )
            self._save(db, job, "draft_edited", {"output_hash": job["output_hash"]})
            return job
