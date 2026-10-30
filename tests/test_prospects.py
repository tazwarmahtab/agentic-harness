"""User-observable prospect intake, evidence and review contracts."""

import base64
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO

import pytest


def intake(**changes):
    from aos.prospects.models import Intake

    values = {
        "venture": "netso",
        "project": "factory-a",
        "prospect": "Synthetic Factory",
        "purpose": "Prepare discovery",
        "documents": [
            {
                "filename": "notes.txt",
                "content_b64": base64.b64encode(
                    b"Buyer: Example Person\nRoof survey not supplied."
                ).decode(),
            }
        ],
    }
    values.update(changes)
    return Intake(**values)


def store(tmp_path):
    from aos.prospects.store import ProspectStore

    return ProspectStore(tmp_path / "prospects.sqlite3")


def test_restart_preserves_original_evidence_and_review(tmp_path):
    from aos.prospects.store import ProspectStore

    db = store(tmp_path)
    job = db.create(intake())
    result = db.generate(job["id"], "netso", "factory-a")
    assert result["status"] == "needs_review"
    assert result["output"]["facts"][0]["quote"] == "Buyer: Example Person"
    fresh = ProspectStore(tmp_path / "prospects.sqlite3")
    assert fresh.get(job["id"], "netso", "factory-a") == result
    source = fresh.source(job["id"], result["sources"][0]["id"], "netso", "factory-a")
    assert source[1].startswith(b"Buyer:")
    decided = fresh.review(
        job["id"], "netso", "factory-a", result["output_hash"], "approve", "founder"
    )
    assert decided["status"] == "approved"
    assert decided["send_authorized"] is False


def test_wrong_scope_never_exposes_sources(tmp_path):
    db = store(tmp_path)
    job = db.create(intake())
    with pytest.raises(KeyError):
        db.get(job["id"], "other", "factory-a")
    with pytest.raises(KeyError):
        db.source(job["id"], job["sources"][0]["id"], "netso", "other")
    assert db.list("other", "factory-a") == []


def test_model_cannot_invent_a_citation_and_failed_job_can_retry(tmp_path):
    from aos.prospects.models import Analysis, Fact

    db = store(tmp_path)
    job = db.create(intake())

    def invented(pages):
        return Analysis(
            facts=[
                Fact(
                    source_id=pages[0].source_id,
                    page=1,
                    quote="Annual bill is BDT 999 million",
                    topic="bill",
                )
            ]
        )

    with pytest.raises(ValueError, match="citation"):
        db.generate(job["id"], "netso", "factory-a", analyzer=invented)
    assert db.get(job["id"], "netso", "factory-a")["status"] == "failed"
    assert db.generate(job["id"], "netso", "factory-a")["status"] == "needs_review"


def test_exact_reference_page_is_required(tmp_path):
    from aos.prospects.models import Analysis, Fact

    db = store(tmp_path)
    job = db.create(intake())
    with pytest.raises(ValueError, match="citation"):
        db.generate(
            job["id"],
            "netso",
            "factory-a",
            analyzer=lambda pages: Analysis(
                facts=[
                    Fact(
                        source_id=pages[0].source_id,
                        page=999,
                        quote=pages[0].text,
                        topic="other",
                    )
                ]
            ),
        )


def test_review_hash_and_terminal_decision_cannot_change(tmp_path):
    db = store(tmp_path)
    job = db.create(intake())
    job = db.generate(job["id"], "netso", "factory-a")
    with pytest.raises(ValueError, match="version"):
        db.review(job["id"], "netso", "factory-a", "stale", "approve", "founder")
    a = db.review(
        job["id"], "netso", "factory-a", job["output_hash"], "reject", "founder"
    )
    b = db.review(
        job["id"], "netso", "factory-a", job["output_hash"], "reject", "founder"
    )
    assert a == b
    with pytest.raises(ValueError, match="decided"):
        db.review(
            job["id"], "netso", "factory-a", job["output_hash"], "approve", "founder"
        )


def test_defer_does_not_approve_and_can_be_reviewed_again(tmp_path):
    db = store(tmp_path)
    job = db.create(intake())
    job = db.generate(job["id"], "netso", "factory-a")
    deferred = db.review(
        job["id"], "netso", "factory-a", job["output_hash"], "defer", "founder"
    )
    assert deferred["status"] == "needs_review"
    assert deferred["send_authorized"] is False
    assert (
        db.review(
            job["id"], "netso", "factory-a", job["output_hash"], "approve", "founder"
        )["status"]
        == "approved"
    )


def test_concurrent_conflicting_decisions_do_not_overwrite(tmp_path):
    db = store(tmp_path)
    job = db.create(intake())
    job = db.generate(job["id"], "netso", "factory-a")

    def decide(decision):
        try:
            return db.review(
                job["id"], "netso", "factory-a", job["output_hash"], decision, "founder"
            )["status"]
        except ValueError:
            return "conflict"

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(decide, ["approve", "reject"]))
    assert results.count("conflict") == 1


@pytest.mark.parametrize(
    "filename,body",
    [
        ("scan.pdf", b"bad pdf"),
        ("notes.exe", b"x"),
        ("../notes.txt", b"x"),
        ("empty.txt", b" "),
        ("bad.txt", b"\xff"),
    ],
)
def test_unreadable_or_unsafe_documents_fail_explicitly(tmp_path, filename, body):
    with pytest.raises(ValueError):
        store(tmp_path).create(
            intake(
                documents=[
                    {
                        "filename": filename,
                        "content_b64": base64.b64encode(body).decode(),
                    }
                ]
            )
        )


def test_docx_paragraphs_get_stable_locators(tmp_path):
    from docx import Document

    f = BytesIO()
    doc = Document()
    doc.add_paragraph("Buyer is Synthetic Person")
    doc.save(f)
    db = store(tmp_path)
    job = db.create(
        intake(
            documents=[
                {
                    "filename": "notes.docx",
                    "content_b64": base64.b64encode(f.getvalue()).decode(),
                }
            ]
        )
    )
    result = db.generate(job["id"], "netso", "factory-a")
    assert result["output"]["facts"][0]["quote"] == "Buyer is Synthetic Person"
    assert result["sources"][0]["locator_kind"] == "paragraph/table-row"


def test_missing_items_and_no_guaranteed_savings_are_explicit(tmp_path):
    db = store(tmp_path)
    result = db.generate(db.create(intake())["id"], "netso", "factory-a")
    assert len(result["output"]["missing_information"]) >= 4
    assert "30%" not in result["output"]["follow_up"]
    assert result["mode"] == "extractive"
    assert result["output"]["source_review_required"] is True


def test_duplicate_generate_returns_same_immutable_output(tmp_path):
    db = store(tmp_path)
    job = db.create(intake())
    first = db.generate(job["id"], "netso", "factory-a")
    assert db.generate(job["id"], "netso", "factory-a") == first


def test_editing_draft_creates_new_review_version_and_preserves_history(tmp_path):
    db = store(tmp_path)
    job = db.generate(db.create(intake())["id"], "netso", "factory-a")
    old_hash = job["output_hash"]
    db.review(job["id"], "netso", "factory-a", old_hash, "approve", "founder")
    changed = db.edit_draft(
        job["id"], "netso", "factory-a", old_hash, "Founder edited draft"
    )
    assert changed["status"] == "needs_review"
    assert changed["output_hash"] != old_hash
    assert changed["review"] is None
    assert db.versions(job["id"], "netso", "factory-a")[0]["output_hash"] == old_hash
    with pytest.raises(ValueError, match="version"):
        db.review(job["id"], "netso", "factory-a", old_hash, "approve", "founder")


def test_reverting_draft_text_never_resurrects_a_decided_version(tmp_path):
    db = store(tmp_path)
    job = db.generate(db.create(intake())["id"], "netso", "factory-a")
    a = db.edit_draft(job["id"], "netso", "factory-a", job["output_hash"], "Draft A")
    db.review(job["id"], "netso", "factory-a", a["output_hash"], "approve", "founder")
    b = db.edit_draft(job["id"], "netso", "factory-a", a["output_hash"], "Draft B")
    again = db.edit_draft(job["id"], "netso", "factory-a", b["output_hash"], "Draft A")
    assert again["output_hash"] != a["output_hash"]


def test_pdf_parsing_has_a_wall_clock_budget(tmp_path, monkeypatch):
    import subprocess

    from aos.prospects import ingest

    def timeout(*args, **kwargs):
        assert kwargs["timeout"] == 15
        raise subprocess.TimeoutExpired(args[0], 15)

    monkeypatch.setattr(ingest.subprocess, "run", timeout)
    with pytest.raises(ValueError, match="budget"):
        store(tmp_path).create(
            intake(
                documents=[
                    {
                        "filename": "notes.pdf",
                        "content_b64": base64.b64encode(b"%PDF-1.7").decode(),
                    }
                ]
            )
        )


def test_text_pdf_retains_page_reference(tmp_path):
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    writer = PdfWriter()
    page = writer.add_blank_page(width=400, height=400)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
    )
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 10 300 Td (Buyer: Synthetic PDF Person) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    buffer = BytesIO()
    writer.write(buffer)
    db = store(tmp_path)
    job = db.create(
        intake(
            documents=[
                {
                    "filename": "bill.pdf",
                    "content_b64": base64.b64encode(buffer.getvalue()).decode(),
                }
            ]
        )
    )
    output = db.generate(job["id"], "netso", "factory-a")
    assert output["sources"][0]["locator_kind"] == "page"
    assert output["output"]["facts"][0]["page"] == 1
    assert output["output"]["facts"][0]["quote"] == "Buyer: Synthetic PDF Person"
