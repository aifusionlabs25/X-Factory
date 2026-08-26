#!/usr/bin/env python3
"""Disposable live canary for the explicit website-capture transport."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import x_factory.knowledge_loading_v0_1 as knowledge  # noqa: E402
from x_factory.knowledge_compiler_v0_1 import compile_package  # noqa: E402
from x_factory.website_ingestion_v0_1 import capture_website_knowledge  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture a public website into a disposable knowledge sandbox, print bounded evidence, then remove it.")
    parser.add_argument("url")
    args = parser.parse_args()
    sandbox_parent = ROOT / "verification" / "tmp"
    sandbox_parent.mkdir(parents=True, exist_ok=True)
    sandbox = sandbox_parent / f"website-live-canary-{os.getpid()}"
    sandbox.mkdir()
    original_root = knowledge.KNOWLEDGE_ROOT
    knowledge.KNOWLEDGE_ROOT = sandbox / "knowledge-packages"
    try:
        package = capture_website_knowledge({"url": args.url, "label": "Disposable live website canary"})
        knowledge.approve_knowledge_package(package["package_id"])
        compilation = compile_package(package["package_id"])
        print("LIVE_WEBSITE_CAPTURE_PASS")
        print(f"PAGES={len(package['website_capture']['pages'])}")
        print(f"NETWORK_CALLS={package['authority']['network_calls']}")
        print(f"EXTRACTED_BYTES={package['total_bytes']}")
        for page in package["website_capture"]["pages"]:
            print(f"PAGE={page['url']}")
        print(f"RAW_PROPOSALS={compilation['quality_filter']['input_entries']}")
        print(f"BOILERPLATE_REMOVED={compilation['quality_filter']['boilerplate_removed']}")
        print(f"GROUPED_FRAGMENTS={compilation['quality_filter']['grouped_fragments']}")
        print(f"DUPLICATES_REMOVED={compilation['quality_filter']['duplicates_removed']}")
        print(f"REVIEW_PROPOSALS={len(compilation['entries'])}")
        print(f"CATEGORIES={compilation['quality_filter']['categories']}")
        print(f"SYSTEM_PROMPT_CANDIDATES={compilation['quality_filter']['system_prompt_candidates']}")
        for entry in compilation["entries"]:
            print(f"PROPOSAL={entry['relevance']['category']} | {entry['title']} | {entry['statement'][:260]}")
        print("PERSISTED_PACKAGE=NO")
        return 0
    finally:
        knowledge.KNOWLEDGE_ROOT = original_root
        shutil.rmtree(sandbox, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
