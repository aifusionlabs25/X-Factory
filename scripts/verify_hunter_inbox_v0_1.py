"""Provider-free verification for the owner-reviewed Hunter lead inbox."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True

from x_factory import hunter_inbox_v0_1 as inbox
from x_factory import hunter_refresh_v0_1 as refresh
from x_factory import hunter_draft_v0_1 as draft
from x_factory.chassis_depot_v0_1 import get_chassis


class HunterInboxTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.receipts = root / "receipts"
        self.handoffs = root / "handoffs"
        self.incoming = root / "incoming"
        self.receipts.mkdir()
        chassis = get_chassis("operational-qa-concierge")
        prospect = {
            "prospect_id": "demo-prospect-001",
            "company_name": "Demo Home Services",
            "website": "https://demo.example/",
            "vertical": "Home services",
            "location": "Phoenix, Arizona",
            "gtm_wedge": "emergency_after_hours",
            "overall_score": 91,
            "overall_band": "strong_commercial_candidate",
            "stage": "qualified",
            "verification_status": "verified_public",
            "rob_demo_recommendation": "YES",
            "public_sources": [{"url": "https://demo.example/", "observed_on": date.today().isoformat()}],
            "browser_audit": {"checked_on": date.today().isoformat(), "rendered_page_checked": True, "submission_performed": False},
            "factory_intake_brief": {
                "agent_job": "A contained service-intake concierge that prepares a human review handoff.",
                "additional_boundaries": ["No dispatch"],
                "system_prompt_brief": "A contained service-intake concierge that prepares a human review handoff.",
                "who_will_use_this": "Prospective customers",
                "personality_and_communication_style": "Calm and concise",
                "additional_requirements": ["Ask one useful question at a time"],
                "appearance_recommendation": "TEXT_ONLY",
            },
        }
        snapshot = {
            "source_id": draft.SOURCE_ID,
            "source_run_sha256": "a" * 64,
            "prospect_id": prospect["prospect_id"],
            "research_status": "UNAPPROVED_RESEARCH",
            "original_prospect": prospect,
        }
        fields = {
            "purpose": "A contained service-intake concierge that prepares a human review handoff.",
            "x_agent_name": "Demo",
            "client_name": prospect["company_name"],
            "target_users": "Prospective customers",
            "personality": "Calm and concise",
            "additional_requirements": "Ask one useful question at a time",
            "additional_boundaries": "No dispatch",
            "presence_mode": "TEXT_ONLY",
        }
        record = {
            "schema_version": "hunter.owner-reviewed-draft.v0.1",
            "status": "OWNER_REVIEWED_DRAFT_ONLY",
            "reviewed_at": "2026-09-04T12:00:00+00:00",
            "snapshot": snapshot,
            "snapshot_sha256": inbox._digest(snapshot),
            "fields": fields,
            "chassis_id": chassis["chassis_id"],
            "chassis_sha256": chassis["chassis_sha256"],
            "knowledge_approved": False,
            "mission_created": False,
            "provider_calls": 0,
            "outreach_performed": False,
        }
        record["record_sha256"] = inbox._digest(record)
        self.prospect = prospect
        self.run = {"qualified_prospects": [prospect]}
        self.patchers = [
            patch.object(inbox, "REVIEW_ROOT", self.receipts),
            patch.object(inbox, "INBOX_ROOT", self.handoffs),
            patch.object(inbox, "INCOMING_ROOT", self.incoming),
            patch.object(inbox, "REFRESH_REQUEST_ROOT", self.handoffs / "refresh-requests"),
            patch.object(refresh, "REQUEST_ROOT", self.handoffs / "refresh-requests"),
            patch.object(draft, "REVIEW_ROOT", self.receipts),
            patch.object(draft, "SOURCE_SHA256", "a" * 64),
            patch.object(draft, "source_run", return_value=self.run),
        ]
        for patcher in self.patchers:
            patcher.start()
        self.receipt = draft.receipt_path(prospect["prospect_id"])
        self.receipt.write_text(json.dumps(record), encoding="utf-8")

    def update_bound_record(self):
        record = json.loads(self.receipt.read_text(encoding="utf-8"))
        record["snapshot"]["original_prospect"] = self.prospect
        record["snapshot_sha256"] = inbox._digest(record["snapshot"])
        record["record_sha256"] = inbox._digest({k: v for k, v in record.items() if k != "record_sha256"})
        self.receipt.write_text(json.dumps(record), encoding="utf-8")

    def tearDown(self) -> None:
        for patcher in self.patchers:
            patcher.stop()
        self.temp.cleanup()

    def test_list_and_send_are_owner_gated_and_hash_bound(self) -> None:
        listing = inbox.list_inbox()
        self.assertEqual(listing["schema_version"], "hunter.factory-lead-inbox.v0.1")
        self.assertEqual(listing["leads"][0]["status"], "READY_TO_SEND")
        self.assertFalse(listing["leads"][0]["reverification_required"])
        self.assertEqual(listing["leads"][0]["source_id"], draft.SOURCE_ID)

        result = inbox.send_to_factory({"prospect_id": "demo-prospect-001"})
        handoff = result["handoff"]
        self.assertFalse(result["reused"])
        self.assertEqual(handoff["status"], "READY_FOR_FACTORY_REVIEW")
        self.assertFalse(handoff["guardrails"]["knowledge_approved"])
        self.assertFalse(handoff["guardrails"]["mission_created"])
        self.assertEqual(handoff["guardrails"]["provider_calls"], 0)
        self.assertFalse(handoff["guardrails"]["outreach_performed"])
        self.assertTrue((self.handoffs / "demo-prospect-001.json").is_file())
        loaded = inbox.use_handoff({"prospect_id": "demo-prospect-001"})
        self.assertEqual(loaded["fields"]["client_name"], "Demo Home Services")
        self.assertEqual(loaded["chassis"]["chassis_id"], "operational-qa-concierge")

        reused = inbox.send_to_factory({"prospect_id": "demo-prospect-001"})
        self.assertTrue(reused["reused"])
        self.assertEqual(reused["handoff"]["handoff_sha256"], handoff["handoff_sha256"])
        self.assertEqual(inbox.list_inbox()["leads"][0]["status"], "HANDOFF_READY")

    def test_extra_request_fields_are_rejected(self) -> None:
        with self.assertRaises(inbox.HunterInboxError):
            inbox.send_to_factory({"prospect_id": "demo-prospect-001", "approve": True})

    def test_refresh_request_is_bounded_and_idempotent(self) -> None:
        result = refresh.create_refresh_request({"prospect_id": "demo-prospect-001"})
        request = result["refresh_request"]
        self.assertFalse(result["reused"])
        self.assertEqual(request["status"], "READY_FOR_HUNTER")
        self.assertEqual(request["instructions"]["scope"], "ONE_PROSPECT_PUBLIC_SOURCE_REVERIFICATION")
        self.assertEqual(request["return_contract"]["dropbox"], "drafts/hunter/incoming")
        self.assertEqual(request["guardrails"]["provider_calls"], 0)
        self.assertFalse(request["guardrails"]["knowledge_approved"])
        self.assertFalse(result["automatic_return_supported"])
        self.assertTrue((self.handoffs / "refresh-requests" / "demo-prospect-001.json").is_file())
        reused = refresh.create_refresh_request({"prospect_id": "demo-prospect-001"})
        self.assertTrue(reused["reused"])
        self.assertEqual(reused["refresh_request"]["request_sha256"], request["request_sha256"])

    def test_self_claimed_owner_review_in_dropbox_cannot_supersede_receipt(self) -> None:
        refresh_result = refresh.create_refresh_request({"prospect_id": "demo-prospect-001"})
        request = refresh_result["refresh_request"]
        record = json.loads(self.receipt.read_text(encoding="utf-8"))
        record["snapshot"]["source_run_sha256"] = "b" * 64
        record["snapshot"]["original_prospect"]["public_sources"][0]["observed_on"] = date.today().isoformat()
        record["snapshot"]["original_prospect"]["browser_audit"]["checked_on"] = date.today().isoformat()
        record["record_sha256"] = inbox._digest({k: v for k, v in record.items() if k != "record_sha256"})
        wrapper = {"schema_version": "hunter.factory-refresh-result.v0.1", "refresh_id": request["refresh_id"], "record": record}
        wrapper["result_sha256"] = inbox._digest(wrapper)
        self.incoming.mkdir()
        (self.incoming / "demo-prospect-001.json").write_text(json.dumps(wrapper), encoding="utf-8")
        listing = inbox.list_inbox()
        self.assertEqual(len(listing["leads"]), 1)
        self.assertFalse(listing["leads"][0]["reverification_required"])
        self.assertEqual(listing["leads"][0]["source_receipt"], self.receipt.name)
        result = inbox.send_to_factory({"prospect_id": "demo-prospect-001"})
        self.assertEqual(result["handoff"]["source"]["source_run_sha256"], "a" * 64)
        self.receipt.unlink()
        self.assertEqual(inbox.list_inbox()["leads"], [])
        with self.assertRaises(inbox.HunterInboxError):
            inbox.send_to_factory({"prospect_id": "demo-prospect-001"})

    def test_stale_handoff_is_labeled_and_blocked_by_original_review(self) -> None:
        self.prospect["browser_audit"]["checked_on"] = (date.today() - timedelta(days=8)).isoformat()
        self.update_bound_record()
        inbox.send_to_factory({"prospect_id": "demo-prospect-001"})
        self.assertEqual(inbox.list_inbox()["leads"][0]["status"], "NEEDS_FRESH_RESEARCH")
        with self.assertRaisesRegex(inbox.HunterInboxError, "seven-day"):
            inbox.use_handoff({"prospect_id": "demo-prospect-001"})

    def test_fresh_date_does_not_bypass_missing_rendered_source_evidence(self) -> None:
        self.prospect["browser_audit"]["rendered_page_checked"] = False
        self.update_bound_record()
        inbox.send_to_factory({"prospect_id": "demo-prospect-001"})
        self.assertEqual(inbox.list_inbox()["leads"][0]["status"], "REVIEW_BLOCKED")
        with self.assertRaisesRegex(inbox.HunterInboxError, "rendered-source evidence"):
            inbox.use_handoff({"prospect_id": "demo-prospect-001"})

    def test_handoff_with_recomputed_hash_still_must_match_reviewed_fields(self) -> None:
        handoff = inbox.send_to_factory({"prospect_id": "demo-prospect-001"})["handoff"]
        handoff["factory_intake"]["fields"]["purpose"] = "Unreviewed replacement purpose bypassing the owner"
        handoff["handoff_sha256"] = inbox._digest({k: v for k, v in handoff.items() if k != "handoff_sha256"})
        (self.handoffs / "demo-prospect-001.json").write_text(json.dumps(handoff), encoding="utf-8")
        with self.assertRaisesRegex(inbox.HunterInboxError, "does not match"):
            inbox.use_handoff({"prospect_id": "demo-prospect-001"})

    def test_bad_refresh_request_hash_does_not_get_reused(self) -> None:
        saved = refresh.create_refresh_request({"prospect_id": "demo-prospect-001"})["refresh_request"]
        saved["instructions"]["prompt"] += " Tampered."
        path = self.handoffs / "refresh-requests" / "demo-prospect-001.json"
        path.write_text(json.dumps(saved), encoding="utf-8")
        original_bytes = path.read_bytes()
        with self.assertRaises(refresh.HunterRefreshError):
            refresh.create_refresh_request({"prospect_id": "demo-prospect-001"})
        self.assertEqual(path.read_bytes(), original_bytes)

    def test_receipt_rehash_cannot_change_pinned_source(self) -> None:
        record = json.loads(self.receipt.read_text(encoding="utf-8"))
        record["snapshot"]["original_prospect"]["company_name"] = "Unreviewed changed company"
        record["snapshot_sha256"] = inbox._digest(record["snapshot"])
        record["record_sha256"] = inbox._digest({k: v for k, v in record.items() if k != "record_sha256"})
        self.receipt.write_text(json.dumps(record), encoding="utf-8")
        self.assertEqual(inbox.list_inbox()["leads"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
