#!/usr/bin/env python3
"""Provider-free regression for bounded website-backed knowledge ingestion."""

from __future__ import annotations

import shutil
import sys
import os
from urllib.request import ProxyHandler
from pathlib import Path


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import x_factory.knowledge_loading_v0_1 as knowledge  # noqa: E402
from x_factory.knowledge_compiler_v0_1 import (  # noqa: E402
    KnowledgeCompilerError,
    compile_package,
    review_compilation,
)
from x_factory.instance_knowledge_builder_v0_1 import _system_prompt  # noqa: E402
from x_factory.website_ingestion_v0_1 import WebsiteCaptureError, _direct_opener, capture_website_knowledge  # noqa: E402


def public_resolver(host: str, port: object, *, type: object) -> list[tuple]:  # noqa: A002
    assert host == "example.com"
    return [(2, 1, 6, "", ("93.184.216.34", 0))]


PAGES = {
    "https://example.com/": (200, {"content-type": "text/html; charset=utf-8"}, b"""
        <html><head><title>Summit Services</title><script>ignore secret noise</script></head>
        <body><nav><span>Open Menu Close Menu</span><span>Cart ( 0 )</span></nav><main><h1>Summit Home Services</h1><p>We repair water heaters and air conditioning systems.</p>
        <p>Final pricing requires staff review.</p><span>View fullsize</span><span>Book now</span><a href='/services'>Services</a><a href='/store'>Store</a><a href='https://outside.example/'>Outside</a></main></body></html>
    """),
    "https://example.com/services": (200, {"content-type": "text/html"}, b"""
        <html><head><title>Service Area</title></head><body><main><h1>Service area</h1>
        <p>Urgent HVAC requests are prioritized in Gilbert and Mesa.</p><p>Final pricing requires staff review.</p><span>View fullsize</span><a href='/'>Home</a></main></body></html>
    """),
}


def fake_fetch(url: str) -> tuple[int, dict[str, str], bytes]:
    if url not in PAGES:
        raise AssertionError(f"Unexpected fetch: {url}")
    return PAGES[url]


def main() -> int:
    original_root = knowledge.KNOWLEDGE_ROOT
    sandbox_parent = ROOT / "verification" / "tmp"
    sandbox_parent.mkdir(parents=True, exist_ok=True)
    sandbox = sandbox_parent / f"website-proof-{os.getpid()}"
    sandbox.mkdir()
    temp_root = sandbox / "knowledge-packages"
    knowledge.KNOWLEDGE_ROOT = temp_root
    try:
        old_http_proxy = os.environ.get("HTTP_PROXY")
        old_https_proxy = os.environ.get("HTTPS_PROXY")
        os.environ["HTTP_PROXY"] = "http://127.0.0.1:1"
        os.environ["HTTPS_PROXY"] = "http://127.0.0.1:1"
        try:
            proxy_handlers = [handler for handler in _direct_opener().handlers if isinstance(handler, ProxyHandler)]
            # urllib omits an explicitly empty ProxyHandler from the finalized
            # chain; its absence proves no environment-derived proxy remains.
            assert not proxy_handlers
        finally:
            if old_http_proxy is None:
                os.environ.pop("HTTP_PROXY", None)
            else:
                os.environ["HTTP_PROXY"] = old_http_proxy
            if old_https_proxy is None:
                os.environ.pop("HTTPS_PROXY", None)
            else:
                os.environ["HTTPS_PROXY"] = old_https_proxy
        package = capture_website_knowledge(
            {"url": "https://example.com", "label": "Summit website capture"},
            resolver=public_resolver,
            fetcher=fake_fetch,
            captured_at="2026-08-24T12:00:00+00:00",
        )
        assert package["effective_status"] == "INGESTED_PENDING_OWNER_APPROVAL"
        assert package["authority"] == {
            "source": "OWNER_REQUESTED_PUBLIC_WEBSITE_CAPTURE",
            "runtime_truth": False,
            "provider_calls": 0,
            "network_calls": 2,
            "production_approved": False,
        }
        assert len(package["website_capture"]["pages"]) == 2
        assert package["website_capture"]["scope"] == "SAME_ORIGIN_PUBLIC_PAGES"
        assert all(page["url"].startswith("https://example.com/") for page in package["website_capture"]["pages"])
        try:
            compile_package(package["package_id"])
        except KnowledgeCompilerError as error:
            assert "Owner approval" in str(error)
        else:
            raise AssertionError("Compilation must remain blocked before owner approval")

        approved_package = knowledge.approve_knowledge_package(package["package_id"])
        assert "explicitly requested this bounded public-website capture" in approved_package["approval"]["owner_attestation"]
        compilation = compile_package(package["package_id"])
        statements = " ".join(item["statement"] for item in compilation["entries"])
        assert "water heaters" in statements
        assert "Urgent HVAC" in statements
        assert "Source URL:" not in statements
        assert "Captured:" not in statements
        assert "View fullsize" not in statements
        assert "Book now" not in statements
        assert compilation["quality_filter"]["version"] == "WEBSITE_RELEVANCE_V0_1"
        assert compilation["quality_filter"]["boilerplate_removed"] >= 3
        assert compilation["quality_filter"]["duplicates_removed"] >= 1
        assert compilation["quality_filter"]["system_prompt_candidates"] == 0
        assert all(item["relevance"]["recommended_target"] == "KNOWLEDGE_BANK_ONLY" for item in compilation["entries"])
        sample_prompt = _system_prompt(
            {
                "display_name": "Ava — Home Services Concierge",
                "agent_name": "Ava",
                "role_title": "Home Services Concierge",
                "client_name": "Summit Home Services",
                "purpose": "Answer approved home-service questions.",
                "personality": "Warm and concise",
                "never_do": ["Invent pricing"],
                "must_accomplish": ["Answer approved questions"],
                "output_artifact": "Staff handoff",
            },
            compilation["entries"],
        )
        assert "use the exact approved statement in the separate Knowledge Bank" in sample_prompt
        assert "We repair water heaters" not in sample_prompt
        decisions = [{"entry_id": item["entry_id"], "decision": "APPROVE"} for item in compilation["entries"]]
        reviewed = review_compilation(package["package_id"], {"compilation_id": compilation["compilation_id"], "decisions": decisions})
        assert reviewed["latest_review"]["status"] == "OWNER_REVIEW_COMPLETE_READY_FOR_INSTANCE_BUILD"

        fetch_attempted = False

        def private_resolver(host: str, port: object, *, type: object) -> list[tuple]:  # noqa: A002
            return [(2, 1, 6, "", ("127.0.0.1", 0))]

        def forbidden_fetch(url: str) -> tuple[int, dict[str, str], bytes]:
            nonlocal fetch_attempted
            fetch_attempted = True
            return PAGES["https://example.com/"]

        try:
            capture_website_knowledge(
                {"url": "https://example.com", "label": "Blocked private target"},
                resolver=private_resolver,
                fetcher=forbidden_fetch,
            )
        except WebsiteCaptureError as error:
            assert "Private, local" in str(error)
        else:
            raise AssertionError("Private targets must be rejected")
        assert not fetch_attempted

        def redirect_fetch(url: str) -> tuple[int, dict[str, str], bytes]:
            return 302, {"location": "https://outside.example/"}, b""

        try:
            capture_website_knowledge(
                {"url": "https://example.com", "label": "Blocked redirect"},
                resolver=public_resolver,
                fetcher=redirect_fetch,
            )
        except WebsiteCaptureError as error:
            assert "Cross-site redirects" in str(error)
        else:
            raise AssertionError("Cross-site redirects must be rejected")

        print("WEBSITE_INGESTION_V0_1_PASS")
        print(f"PACKAGE={package['package_id']}")
        print(f"PAGES={len(package['website_capture']['pages'])}")
        print(f"ENTRIES={len(compilation['entries'])}")
        print("PRIVATE_TARGET_BLOCKED=PASS")
        print("CROSS_SITE_REDIRECT_BLOCKED=PASS")
        print("AMBIENT_PROXY_BYPASS=PASS")
        return 0
    finally:
        knowledge.KNOWLEDGE_ROOT = original_root
        shutil.rmtree(sandbox, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
