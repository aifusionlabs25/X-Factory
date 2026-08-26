import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RepositoryTests(unittest.TestCase):
    def test_required_application_files_exist(self):
        required = [
            "README.md", ".env.example", "pyproject.toml", "agent/AGENT.md",
            "config/agent.spec.json", "config/persona-binding.json",
            "config/x-link-candidate.json", "web/index.html", "web/grounded-matcher.js", "web/app.js",
            "src/x_agent_runtime/server.py", "factory-record/vera-final.json",
        ]
        self.assertTrue(all((ROOT / item).is_file() for item in required))

    def test_authority_remains_local_and_nonproduction(self):
        preview = json.loads((ROOT / "web/agent.json").read_text(encoding="utf-8"))
        self.assertEqual(preview["repo_mode"], "LOCAL_STAGING_PREVIEW")
        self.assertTrue(all(value is False for value in preview["authority"].values()))

    def test_no_real_environment_file_or_embedded_secret(self):
        self.assertFalse((ROOT / ".env").exists())
        pattern = re.compile(r"(?:sk-[A-Za-z0-9_-]{12,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)")
        for path in ROOT.rglob("*"):
            if path.is_file() and path.stat().st_size < 1_000_000:
                text = path.read_text(encoding="utf-8", errors="ignore")
                self.assertIsNone(pattern.search(text), path.as_posix())

    def test_runtime_source_compiles(self):
        source = (ROOT / "src/x_agent_runtime/server.py").read_text(encoding="utf-8")
        compile(source, "server.py", "exec")

    def test_instance_knowledge_is_complete_when_declared_ready(self):
        preview = json.loads((ROOT / "web/agent.json").read_text(encoding="utf-8"))
        if preview.get("knowledge_status") == "LOCAL_INSTANCE_KNOWLEDGE_READY_NOT_DEPLOYED":
            required = [
                "knowledge/KB.md", "knowledge/approved-knowledge.json",
                "config/SYSTEM_PROMPT.md", "factory-record/knowledge-traceability.json",
                "tests/knowledge-tests.json", "factory-record/instance-knowledge-build-report.json",
                "runtime/runtime-plan.json", "runtime/profile-blueprint.json",
                "runtime/canary/exact-prompt.txt", "runtime/canary/exact-payload.json",
                "runtime/canary/inactive-activation-packet.json",
                "contracts/runtime_behavior_certification.v0.2.schema.json",
            ]
            self.assertTrue(preview.get("knowledge_entries"))
            self.assertTrue(all((ROOT / item).is_file() for item in required))

    def test_behavior_evidence_uses_canonical_match_reason_schema(self):
        certification_path = ROOT / "runtime/local-behavior-certification.json"
        if not certification_path.is_file():
            return
        certification = json.loads(certification_path.read_text(encoding="utf-8"))
        if certification.get("schema_version") == "0.1":
            return
        schema = json.loads((ROOT / "contracts/runtime_behavior_certification.v0.2.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(certification["schema_version"], "0.2")
        allowed = set(schema["$defs"]["match_reason"]["enum"])
        expected_turn_keys = {"turn", "message", "speaker", "outcome", "response", "supporting_entry_ids", "match_reason"}
        for session in certification["sessions"].values():
            for turn in session["turns"]:
                self.assertEqual(set(turn), expected_turn_keys)
                self.assertIn(turn["match_reason"], allowed)

    def test_preview_handoff_uses_intent_gated_state_updates(self):
        app = (ROOT / "web/app.js").read_text(encoding="utf-8")
        self.assertNotIn("", app, "JavaScript regex word boundaries were serialized as control characters")
        expected_intents = {
            "INFORMATIONAL_QUERY", "SERVICE_REQUEST", "QUALIFICATION_DETAIL",
            "CORRECTION", "UNKNOWN_REVIEW", "HANDOFF_REQUEST",
        }
        self.assertTrue(all(intent in app for intent in expected_intents))
        self.assertIn('["SERVICE_REQUEST", "QUALIFICATION_DETAIL", "CORRECTION"].includes(intent)', app)
        self.assertIn('if (intent === "SERVICE_REQUEST") handoff.request_summary = requestSummary(message);', app)
        self.assertIn('"URGENT_HVAC"', app)
        self.assertIn('"OUT_OF_KNOWLEDGE_SERVICE_QUESTION"', app)
        self.assertIn('"PRIMARY_SERVICE_OUTSIDE_APPROVED_KNOWLEDGE"', app)
        self.assertIn('"URGENT_HUMAN_REVIEW"', app)
        self.assertIn('"Service question outside approved knowledge"', app)
        self.assertIn('secondary_questions: handoff.known_unknowns', app)
        self.assertIn('handoff = createHandoff();', app)
        self.assertIn('$("#messages").textContent = "";', app)
        self.assertIn('id="fresh-session"', (ROOT / "web/index.html").read_text(encoding="utf-8"))
        self.assertNotIn('if (!handoff.request_summary)', app)


if __name__ == "__main__":
    unittest.main()
