"""Regression checks for the shared provider-free grounded matching contract."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from x_factory.grounded_matcher_v0_1 import MATCHING_CONTRACT, match_approved_entry, suggested_questions


BUNDLE = ROOT / "runs/interactive/draft-ava-home-services-concierge-20260826-001523-0612cc/instance/knowledge/approved-knowledge.v0.1.json"


def main() -> None:
    entries = json.loads(BUNDLE.read_text(encoding="utf-8"))["entries"]
    approved = {
        "What home repair services do you offer?": "APPROVED_CAPABILITY_SUMMARY",
        "Can you install a ceiling fan?": "CONSERVATIVE_APPROVED_TERM_OVERLAP",
        "Can you repair my kitchen cabinets?": "CONSERVATIVE_APPROVED_TERM_OVERLAP",
        "Do you work in Jackson?": "APPROVED_LOCATION_TERM",
    }
    rejected = [
        "Do you repair water heaters?",
        "Do you install swimming pool pumps?",
        "My AC isn't cooling. I'm in Mesa and it's urgent.",
    ]
    observations = []
    for question, expected_reason in approved.items():
        entry, reason = match_approved_entry(entries, question)
        assert entry is not None, question
        assert reason == expected_reason, (question, reason)
        observations.append({"question": question, "entry_id": entry["entry_id"], "reason": reason})
    for question in rejected:
        entry, reason = match_approved_entry(entries, question)
        assert entry is None, (question, entry["entry_id"])
        assert reason == "NO_APPROVED_MATCH", (question, reason)
        observations.append({"question": question, "entry_id": None, "reason": reason})
    suggestions = suggested_questions(entries)
    assert suggestions
    for suggestion in suggestions:
        entry, reason = match_approved_entry(entries, suggestion["question"])
        assert entry and entry["entry_id"] == suggestion["expected_entry_id"]
        assert reason == suggestion["match_reason"] != "EXACT_APPROVED_TITLE"
    print(json.dumps({"status": "PASS", "contract": MATCHING_CONTRACT, "observations": observations, "suggestions": suggestions}, indent=2))


if __name__ == "__main__":
    main()
