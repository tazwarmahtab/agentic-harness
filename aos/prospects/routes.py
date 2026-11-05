"""Strictly authenticated, single-founder prospect API. Reviews never send messages."""

from __future__ import annotations

import hmac
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import Response
from pydantic import Field
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from aos.prospects.models import Contract, DraftEdit, Intake, Review
from aos.prospects.store import ProspectStore
from aos.prospects.workflow import model_analyzer


def require_founder(authorization: str | None = Header(None)) -> None:
    token = os.getenv("AOS_API_TOKEN", "") or os.getenv("TAZOS_API_TOKEN", "")
    if not token:
        raise HTTPException(
            503, "Configure AOS_API_TOKEN before accessing prospect documents"
        )
    if not authorization or not hmac.compare_digest(authorization, "Bearer " + token):
        raise HTTPException(401, "Valid founder token required")


def get_store() -> ProspectStore:
    root = Path(os.getenv("AOS_STATE_DIR", str(Path.home() / ".local/state/aos")))
    return ProspectStore(root / "prospects.sqlite3")


STORE_DEPENDENCY = Depends(get_store)

router = APIRouter(
    prefix="/api/prospects", dependencies=[Depends(require_founder)], tags=["prospects"]
)


class Generate(Contract):
    use_model: bool = False
    allow_model_disclosure: bool = False
    model: str = Field(default="default", min_length=1, max_length=120)


def _call[T](operation: Callable[[], T]) -> T:
    try:
        return operation()
    except KeyError:
        raise HTTPException(404, "Prospect job or source not found") from None
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None


@router.post("", status_code=201)
def create(request: Intake, store: ProspectStore = STORE_DEPENDENCY) -> dict[str, Any]:
    try:
        return store.create(request)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None


@router.get("")
def list_jobs(
    venture: str = Query(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$"),
    project: str = Query(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$"),
    store: ProspectStore = STORE_DEPENDENCY,
) -> list[dict[str, Any]]:
    return [
        {key: job[key] for key in ("id", "prospect", "purpose", "status", "created_at")}
        for job in store.list(venture, project)
    ]


@router.get("/{job_id}")
def get_job(
    job_id: str,
    venture: str = Query(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$"),
    project: str = Query(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$"),
    store: ProspectStore = STORE_DEPENDENCY,
) -> dict[str, Any]:
    return _call(lambda: store.get(job_id, venture, project))


@router.get("/{job_id}/events")
def events(
    job_id: str,
    venture: str = Query(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$"),
    project: str = Query(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$"),
    store: ProspectStore = STORE_DEPENDENCY,
) -> list[dict[str, Any]]:
    return _call(lambda: store.events(job_id, venture, project))


@router.get("/{job_id}/sources/{source_id}")
def source(
    job_id: str,
    source_id: str,
    venture: str = Query(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$"),
    project: str = Query(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$"),
    store: ProspectStore = STORE_DEPENDENCY,
) -> Response:
    filename, raw = _call(lambda: store.source(job_id, source_id, venture, project))
    return Response(
        raw,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": "attachment; filename*=UTF-8''"
            + quote(filename, safe=""),
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )


@router.post("/{job_id}/generate")
def generate(
    job_id: str,
    request: Generate,
    venture: str = Query(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$"),
    project: str = Query(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$"),
    store: ProspectStore = STORE_DEPENDENCY,
) -> dict[str, Any]:
    analyzer = None
    if request.use_model:
        if (
            os.getenv("AOS_PROSPECT_MODEL_ENABLED") != "1"
            or not request.allow_model_disclosure
        ):
            raise HTTPException(
                403,
                "Model processing requires server enablement and explicit document-disclosure consent",
            )
        # Verify scoped existence before constructing an external provider.
        _call(lambda: store.get(job_id, venture, project))
        from aos.llm import create_llm_client

        analyzer = model_analyzer(create_llm_client(), request.model)
    return _call(lambda: store.generate(job_id, venture, project, analyzer))


@router.post("/{job_id}/review")
def review(
    job_id: str,
    request: Review,
    venture: str = Query(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$"),
    project: str = Query(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$"),
    store: ProspectStore = STORE_DEPENDENCY,
) -> dict[str, Any]:
    return _call(
        lambda: store.review(
            job_id,
            venture,
            project,
            request.output_hash,
            request.decision,
            "founder-token",
        )
    )


class ProspectBodyLimit:
    """Bound request buffering, including chunked bodies, before JSON parsing."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or not scope.get("path", "").startswith("/api/prospects")
            or scope.get("method") not in {"POST", "PUT", "PATCH"}
        ):
            return await self.app(scope, receive, send)
        data = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            data.extend(message.get("body", b""))
            if len(data) > 15 * 1024 * 1024:
                response = Response("Request exceeds 15 MiB", status_code=413)
                return await response(scope, receive, send)
            if not message.get("more_body", False):
                break
        delivered = False

        async def replay() -> Message:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(data), "more_body": False}
            return await receive()

        return await self.app(scope, replay, send)


@router.patch("/{job_id}/draft")
def edit_draft(
    job_id: str,
    request: DraftEdit,
    venture: str = Query(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$"),
    project: str = Query(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$"),
    store: ProspectStore = STORE_DEPENDENCY,
) -> dict[str, Any]:
    return _call(
        lambda: store.edit_draft(
            job_id, venture, project, request.output_hash, request.text
        )
    )


@router.get("/{job_id}/versions")
def versions(
    job_id: str,
    venture: str = Query(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$"),
    project: str = Query(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$"),
    store: ProspectStore = STORE_DEPENDENCY,
) -> list[dict[str, Any]]:
    return _call(lambda: store.versions(job_id, venture, project))
