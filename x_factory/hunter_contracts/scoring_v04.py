"""Wedge-specific commercial scoring for Hunter v0.4."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


CONTRACT_VERSION = "hunter.scoring.v0.4"

WEIGHTS: Mapping[str, int] = {
    "problem_intensity_visible_friction": 20,
    "current_factory_fit": 20,
    "structured_conversation_value": 15,
    "lead_customer_economic_leverage": 15,
    "human_avatar_experience_value": 10,
    "public_demo_readiness": 10,
    "adoption_reachability": 10,
}

INTEGRATION_DEDUCTIONS: Mapping[str, int] = {
    "NONE": 0,
    "LOW": 0,
    "MEDIUM": 5,
    "HIGH": 12,
}


@dataclass(frozen=True)
class ScoreComponentsV04:
    problem_intensity_visible_friction: int
    current_factory_fit: int
    structured_conversation_value: int
    lead_customer_economic_leverage: int
    human_avatar_experience_value: int
    public_demo_readiness: int
    adoption_reachability: int

    def __post_init__(self) -> None:
        for name, value in self.as_dict().items():
            if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 5:
                raise ValueError(f"{name} must be an integer from 0 to 5")

    def as_dict(self) -> dict[str, int]:
        return {name: getattr(self, name) for name in WEIGHTS}

    @classmethod
    def from_mapping(cls, values: Mapping[str, object]) -> "ScoreComponentsV04":
        missing = sorted(set(WEIGHTS) - set(values))
        extras = sorted(set(values) - set(WEIGHTS))
        if missing:
            raise ValueError(f"missing score components: {', '.join(missing)}")
        if extras:
            raise ValueError(f"unknown score components: {', '.join(extras)}")
        return cls(**{name: values[name] for name in WEIGHTS})  # type: ignore[arg-type]


@dataclass(frozen=True)
class CommercialPenaltiesV04:
    static_form_only: bool = False
    human_replacement: bool = False
    integration_dependency: str = "NONE"
    weak_avatar: bool = False
    speculative_pain: bool = False

    def __post_init__(self) -> None:
        if self.integration_dependency not in INTEGRATION_DEDUCTIONS:
            raise ValueError("integration_dependency must be NONE, LOW, MEDIUM, or HIGH")
        for name in ("static_form_only", "human_replacement", "weak_avatar", "speculative_pain"):
            if not isinstance(getattr(self, name), bool):
                raise ValueError(f"{name} must be boolean")

    @classmethod
    def from_mapping(cls, values: Mapping[str, object]) -> "CommercialPenaltiesV04":
        expected = {
            "static_form_only", "human_replacement", "integration_dependency",
            "weak_avatar", "speculative_pain",
        }
        missing = sorted(expected - set(values))
        extras = sorted(set(values) - expected)
        if missing:
            raise ValueError(f"missing penalty fields: {', '.join(missing)}")
        if extras:
            raise ValueError(f"unknown penalty fields: {', '.join(extras)}")
        return cls(**{name: values[name] for name in expected})  # type: ignore[arg-type]


def compute_raw_score_v04(components: ScoreComponentsV04) -> int:
    return round(sum(components.as_dict()[name] / 5 * weight for name, weight in WEIGHTS.items()))


def compute_score_v04(
    components: ScoreComponentsV04,
    penalties: CommercialPenaltiesV04,
) -> tuple[int, int, list[str]]:
    raw = compute_raw_score_v04(components)
    score = raw
    applied: list[str] = []

    integration_deduction = INTEGRATION_DEDUCTIONS[penalties.integration_dependency]
    if integration_deduction:
        score -= integration_deduction
        applied.append(f"integration_dependency_{penalties.integration_dependency.lower()}:-{integration_deduction}")
    if penalties.weak_avatar:
        score -= 5
        applied.append("weak_avatar:-5")
    if penalties.speculative_pain:
        score -= 15
        score = min(score, 70)
        applied.append("speculative_pain:-15_cap70")
    if penalties.static_form_only:
        score = min(score, 75)
        applied.append("static_form_only:cap75")
    if penalties.human_replacement:
        score = min(score, 60)
        applied.append("human_replacement:cap60")

    return raw, max(0, score), applied


def qualification_band_v04(score: int) -> str:
    if isinstance(score, bool) or not isinstance(score, int) or not 0 <= score <= 100:
        raise ValueError("score must be an integer from 0 to 100")
    if score >= 85:
        return "strong_commercial_candidate"
    if score >= 75:
        return "credible_wedge_candidate"
    if score >= 65:
        return "hold_validate"
    return "exclude"
