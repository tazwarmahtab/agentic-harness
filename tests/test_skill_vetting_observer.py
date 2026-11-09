import json
import tempfile
import unittest
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
from scripts.verify_candidate_skill import validate


class CandidateSkillContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for relative in [
            "skills/skill-vetting-observer/SKILL.md",
            "skills/skill-vetting-observer/manifest.json",
            "skills/skill-vetting-observer/references/eval-cases.json",
            "docs/skill-governance/INCIDENT-LEDGER.md",
        ]:
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, target)

    def _manifest(self, mutator):
        path = self.root / "skills/skill-vetting-observer/manifest.json"
        data = json.loads(path.read_text())
        mutator(data)
        path.write_text(json.dumps(data))

    def _eval(self, mutator):
        path = self.root / "skills/skill-vetting-observer/references/eval-cases.json"
        data = json.loads(path.read_text())
        mutator(data)
        path.write_text(json.dumps(data))

    def test_candidate_baseline_passes_static_contract(self):
        self.assertEqual(validate(self.root), [])

    def test_unreviewed_candidate_cannot_claim_installed(self):
        self._manifest(lambda m: m.update(status="installed"))
        self.assertTrue(any("self-report" in e for e in validate(self.root)))

    def test_promotion_requires_human_approval(self):
        self._manifest(lambda m: m.update(requires_human_approval=[]))
        self.assertTrue(any("human approval" in e for e in validate(self.root)))

    def test_cross_workstream_manifest_is_rejected(self):
        self._manifest(lambda m: m.update(workstream="netso"))
        self.assertTrue(any("workstream" in e for e in validate(self.root)))

    def test_external_verification_cannot_be_omitted(self):
        self._manifest(lambda m: m.update(external_verification="optional"))
        self.assertTrue(any("verification policy" in e for e in validate(self.root)))

    def test_duplicate_evaluation_id_is_rejected(self):
        self._eval(lambda d: d["cases"][1].update(id=d["cases"][0]["id"]))
        self.assertTrue(any("duplicate" in e for e in validate(self.root)))

    def test_nontrigger_cases_cannot_be_removed(self):
        self._eval(lambda d: [c.update(should_trigger=True) for c in d["cases"]])
        self.assertTrue(any("non-trigger" in e for e in validate(self.root)))

    def test_missing_incident_ledger_blocks(self):
        (self.root / "docs/skill-governance/INCIDENT-LEDGER.md").unlink()
        self.assertTrue(any("missing required file" in e for e in validate(self.root)))

    def test_missing_negative_scope_blocks(self):
        self._manifest(lambda m: m.update(not_for=[]))
        self.assertTrue(any("negative usage" in e for e in validate(self.root)))

    def test_missing_observation_section_blocks(self):
        path = self.root / "skills/skill-vetting-observer/SKILL.md"
        path.write_text(path.read_text().replace("## OBSERVE", "## DISABLED"))
        self.assertTrue(any("OBSERVE" in e for e in validate(self.root)))


if __name__ == "__main__":
    unittest.main()
