"""Revision 005 guard: v0.3 controls plus terminal-presentation suppression."""

from __future__ import annotations

from functools import wraps
import sys
from typing import Any

from .phase4_transport_guard_v0_3 import GovernedRuntimeGuard


def install_into_hermes() -> GovernedRuntimeGuard:
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
        agent.show_reasoning = False
        agent.quiet_mode = True
        agent.suppress_status_output = True
        agent.reasoning_callback = None
        return result

    agent_init.init_agent = guarded_init_agent
    tool_executor.execute_tool_calls_concurrent = guard.blocked_tool
    tool_executor.execute_tool_calls_sequential = guard.blocked_tool
    tool_executor.execute_tool_calls_segmented = guard.blocked_tool

    original_resolver = auth.resolve_codex_runtime_credentials
    originals = {
        auth.refresh_codex_oauth_pure: guard.blocked_refresh,
        auth._refresh_codex_auth_tokens: guard.blocked_refresh,
        auth._recover_codex_tokens_from_cli: guard.blocked_codex_cli_import,
        auth._import_codex_cli_tokens: guard.blocked_codex_cli_import,
        auth._save_codex_tokens: guard.blocked_auth_write,
        auth._save_auth_store: guard.blocked_auth_write,
    }

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

    replacements = {original_resolver: read_only_resolver, **originals}
    for module in tuple(sys.modules.values()):
        namespace = getattr(module, "__dict__", None)
        if not isinstance(namespace, dict):
            continue
        for name, value in tuple(namespace.items()):
            for original, replacement in replacements.items():
                if value is original:
                    namespace[name] = replacement
                    break
    return guard
