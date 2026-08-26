"""Fail-closed Phase 4 transport, tool, auth, and credential-import guards.

This module is inert until installed inside the short-lived governed bridge.
It contains no provider client and performs no network or filesystem activity.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import wraps
import sys
from typing import Any, Callable


class GovernedRuntimeViolation(PermissionError):
    pass


@dataclass
class GovernedRuntimeGuard:
    physical_requests: int = 0
    tool_attempts: int = 0
    oauth_refresh_attempts: int = 0
    auth_write_attempts: int = 0
    codex_cli_import_attempts: int = 0

    def request_wrapper(self, stream: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(stream)
        def guarded_stream(*args: Any, **kwargs: Any) -> Any:
            if self.physical_requests >= 1:
                raise GovernedRuntimeViolation("Second physical model request blocked before transport")
            self.physical_requests += 1
            return stream(*args, **kwargs)
        return guarded_stream

    def blocked_tool(self, *args: Any, **kwargs: Any) -> Any:
        self.tool_attempts += 1
        raise GovernedRuntimeViolation("Tool execution blocked before dispatch")

    def blocked_refresh(self, *args: Any, **kwargs: Any) -> Any:
        self.oauth_refresh_attempts += 1
        raise GovernedRuntimeViolation("OAuth refresh blocked before network transport")

    def blocked_auth_write(self, *args: Any, **kwargs: Any) -> Any:
        self.auth_write_attempts += 1
        raise GovernedRuntimeViolation("Authentication write blocked before filesystem mutation")

    def blocked_codex_cli_import(self, *args: Any, **kwargs: Any) -> Any:
        self.codex_cli_import_attempts += 1
        raise GovernedRuntimeViolation("Codex CLI credential import blocked before filesystem read")


def install_into_hermes() -> GovernedRuntimeGuard:
    """Install all guards before importing the Hermes CLI entry point."""

    from agent import agent_init, relay_llm, tool_executor
    from hermes_cli import auth

    guard = GovernedRuntimeGuard()
    relay_llm.stream = guard.request_wrapper(relay_llm.stream)

    original_init_agent = agent_init.init_agent

    @wraps(original_init_agent)
    def guarded_init_agent(agent: Any, *args: Any, **kwargs: Any) -> Any:
        result = original_init_agent(agent, *args, **kwargs)
        agent._api_max_retries = 1
        agent.api_mode = "codex_responses"
        agent.tools = []
        agent.valid_tool_names = set()
        agent._fallback_chain = []
        agent._fallback_model = None
        agent._fallback_index = 0
        return result

    agent_init.init_agent = guarded_init_agent

    tool_executor.execute_tool_calls_concurrent = guard.blocked_tool
    tool_executor.execute_tool_calls_sequential = guard.blocked_tool
    tool_executor.execute_tool_calls_segmented = guard.blocked_tool

    original_resolver = auth.resolve_codex_runtime_credentials
    original_refresh = auth.refresh_codex_oauth_pure
    original_refresh_tokens = auth._refresh_codex_auth_tokens
    original_recover = auth._recover_codex_tokens_from_cli
    original_import = auth._import_codex_cli_tokens
    original_save_tokens = auth._save_codex_tokens
    original_save_store = auth._save_auth_store

    def read_only_resolver(*, force_refresh: bool = False, **kwargs: Any) -> Any:
        if force_refresh:
            return guard.blocked_refresh()
        kwargs["refresh_if_expiring"] = False
        return original_resolver(force_refresh=False, **kwargs)

    auth.resolve_codex_runtime_credentials = read_only_resolver
    auth.refresh_codex_oauth_pure = guard.blocked_refresh
    auth._refresh_codex_auth_tokens = guard.blocked_refresh
    auth._recover_codex_tokens_from_cli = guard.blocked_codex_cli_import
    auth._import_codex_cli_tokens = guard.blocked_codex_cli_import
    auth._probe_codex_quota_restored = lambda *args, **kwargs: False
    auth.clear_codex_pool_quota_cooldowns = guard.blocked_auth_write
    auth._save_codex_tokens = guard.blocked_auth_write
    auth._save_auth_store = guard.blocked_auth_write

    # Replace aliases captured before installation. Modules imported later
    # receive guarded attributes directly from hermes_cli.auth.
    replacements = (
        (original_resolver, read_only_resolver),
        (original_refresh, guard.blocked_refresh),
        (original_refresh_tokens, guard.blocked_refresh),
        (original_recover, guard.blocked_codex_cli_import),
        (original_import, guard.blocked_codex_cli_import),
        (original_save_tokens, guard.blocked_auth_write),
        (original_save_store, guard.blocked_auth_write),
    )
    for module in tuple(sys.modules.values()):
        namespace = getattr(module, "__dict__", None)
        if not isinstance(namespace, dict):
            continue
        for name, value in tuple(namespace.items()):
            for original, replacement in replacements:
                if value is original:
                    namespace[name] = replacement
                    break
    return guard
