import json
import tempfile
from pathlib import Path
from aos.deals import Deal, DealPipeline, DealStage


def test_deal_creation():
    deal = Deal(id="D1", customer="CGS", stage=DealStage.LOI_SIGNED, venture="netso")
    assert deal.id == "D1"
    assert deal.stage == DealStage.LOI_SIGNED


def test_deal_advance():
    deal = Deal(id="D1", customer="Test", stage=DealStage.LEAD, venture="netso")
    next_stage = deal.advance()
    assert next_stage == DealStage.QUALIFIED
    assert deal.stage == DealStage.QUALIFIED


def test_deal_advance_at_end():
    deal = Deal(id="D1", customer="Test", stage=DealStage.REVENUE, venture="netso")
    next_stage = deal.advance()
    assert next_stage is None
    assert deal.stage == DealStage.REVENUE


def test_pipeline_summary():
    pipeline = DealPipeline(venture="netso")
    pipeline.add_deal(Deal(id="D1", customer="A", stage=DealStage.LEAD, venture="netso"))
    pipeline.add_deal(Deal(id="D2", customer="B", stage=DealStage.LEAD, venture="netso"))
    pipeline.add_deal(Deal(id="D3", customer="C", stage=DealStage.LOI_SIGNED, venture="netso"))
    summary = pipeline.summary()
    assert summary["lead"] == 2
    assert summary["loi_signed"] == 1


def test_pipeline_save_load():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    pipeline = DealPipeline(venture="netso")
    pipeline.add_deal(Deal(id="D1", customer="CGS", stage=DealStage.LOI_SIGNED, venture="netso", capacity_kw=80))
    pipeline.save(path)

    loaded = DealPipeline.load(path)
    assert loaded.venture == "netso"
    assert len(loaded.deals) == 1
    assert loaded.deals[0].customer == "CGS"
    Path(path).unlink()


def test_pipeline_value():
    pipeline = DealPipeline(venture="netso")
    pipeline.add_deal(Deal(id="D1", customer="A", stage=DealStage.LEAD, venture="netso", capacity_kw=80, ppa_rate=10.0))
    pipeline.add_deal(Deal(id="D2", customer="B", stage=DealStage.LEAD, venture="netso", capacity_kw=0))
    assert pipeline.total_pipeline_value() == 800.0


def test_deal_to_dict_roundtrip():
    deal = Deal(id="D1", customer="CGS", stage=DealStage.LOI_SIGNED, venture="netso", notes=["test"])
    d = deal.to_dict()
    restored = Deal.from_dict(d)
    assert restored.id == deal.id
    assert restored.stage == deal.stage
    assert restored.notes == deal.notes
