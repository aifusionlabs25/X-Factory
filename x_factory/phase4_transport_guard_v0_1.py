"""Fail-closed, offline-testable physical-request guard for Phase 4.

This module contains no provider client and performs no network activity.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable


class PhysicalRequestBudgetExceeded(PermissionError):
    """Raised before a second physical model request can be attempted."""


@dataclass
class SinglePhysicalRequestGuard:
    calls_started: int = 0

    def wrap(self, stream: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(stream)
        def guarded_stream(*args: Any, **kwargs: Any) -> Any:
            if self.calls_started >= 1:
                raise PhysicalRequestBudgetExceeded(
                    "Phase 4 permits exactly one physical request for this stage; retry blocked"
                )
            self.calls_started += 1
            return stream(*args, **kwargs)

        return guarded_stream


def install_into_hermes() -> SinglePhysicalRequestGuard:
    """Patch the loaded Hermes request boundary and suppress outer retries.

    The guarded bridge calls this only inside its short-lived Hermes subprocess.
    """

    from agent import agent_init, relay_llm

    guard = SinglePhysicalRequestGuard()
    relay_llm.stream = guard.wrap(relay_llm.stream)

    original_init_agent = agent_init.init_agent

    @wraps(original_init_agent)
    def guarded_init_agent(agent: Any, *args: Any, **kwargs: Any) -> Any:
        result = original_init_agent(agent, *args, **kwargs)
        agent._api_max_retries = 1
        return result

    agent_init.init_agent = guarded_init_agent
    return guard
