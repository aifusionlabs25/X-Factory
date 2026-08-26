"""Prove the generated-repository JavaScript matcher matches the Python contract cases."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from x_factory.repo_foundry_v0_1 import WEB_JS, WEB_MATCHER_JS


def main() -> None:
    bundle = json.loads((ROOT / "runs/interactive/draft-ava-home-services-concierge-20260826-001523-0612cc/instance/knowledge/approved-knowledge.v0.1.json").read_text(encoding="utf-8"))
    contract = {
        "minimum_distinct_term_overlap": 2,
        "minimum_weighted_score": 2,
        "minimum_query_coverage": 0.6,
        "title_term_weight": 3,
        "statement_term_weight": 1,
    }
    cases = {
        "What home repair services do you offer?": "APPROVED_CAPABILITY_SUMMARY",
        "Can you install a ceiling fan?": "CONSERVATIVE_APPROVED_TERM_OVERLAP",
        "Can you repair my kitchen cabinets?": "CONSERVATIVE_APPROVED_TERM_OVERLAP",
        "Do you work in Jackson?": "APPROVED_LOCATION_TERM",
        "Do you repair water heaters?": "NO_APPROVED_MATCH",
        "Do you install swimming pool pumps?": "NO_APPROVED_MATCH",
        "My AC isn't cooling. I'm in Mesa and it's urgent.": "NO_APPROVED_MATCH",
    }
    payload = json.dumps({"entries": bundle["entries"], "contract": contract, "cases": cases}, separators=(",", ":"))
    runner = WEB_MATCHER_JS + (
        '\nconst matcher=module.exports; const data=JSON.parse(process.argv[1]); const out={}; '
        'for(const [question,expected] of Object.entries(data.cases)){ '
        'const result=matcher.match(data.entries,question,data.contract); out[question]=result.reason; '
        'if(result.reason!==expected) throw new Error(`${question}: ${result.reason} != ${expected}`); } '
        'console.log(JSON.stringify({status:"PASS",observed:out},null,2));'
    )
    result = subprocess.run(["node", "-e", runner, payload], capture_output=True, text=True, check=False, timeout=30)
    if result.returncode:
        raise AssertionError(result.stderr or result.stdout)
    syntax = subprocess.run(["node", "-e", "new Function(process.argv[1]); console.log('APP_SYNTAX_PASS')", WEB_JS], capture_output=True, text=True, check=False, timeout=30)
    if syntax.returncode:
        raise AssertionError(syntax.stderr or syntax.stdout)
    print(result.stdout.strip())
    print(syntax.stdout.strip())


if __name__ == "__main__":
    main()
