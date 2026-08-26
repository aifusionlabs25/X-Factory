"""Deterministic, provider-free matching against owner-approved knowledge only."""

from __future__ import annotations

import re
from typing import Any


STOPWORDS = {
    "the", "and", "can", "you", "your", "what", "with", "for", "from", "that", "this",
    "are", "have", "does", "how", "who", "why", "when", "where", "will", "would", "could",
    "please", "tell", "give", "about", "someone", "something", "service", "services", "provide",
    "customer", "customers", "home", "homes", "need", "needed", "new", "my", "me", "our",
}

MATCHING_CONTRACT = {
    "version": "GROUNDED_MATCHER_V0_2",
    "mode": "LOCAL_DETERMINISTIC_APPROVED_KNOWLEDGE_ONLY",
    "minimum_distinct_term_overlap": 2,
    "minimum_weighted_score": 2,
    "minimum_query_coverage": 0.6,
    "title_term_weight": 3,
    "statement_term_weight": 1,
    "broad_capability_questions": True,
    "location_intent_matching": True,
    "provider_calls": 0,
}

ALIASES = (
    (re.compile(r"\bwater[\s-]*heaters?\b", re.IGNORECASE), " waterheater "),
    (re.compile(r"\b(?:a\s*/\s*c|ac|air[\s-]*conditioning|hvac)\b", re.IGNORECASE), " airconditioning "),
    (re.compile(r"\b(?:fix|fixes|fixed|fixing|repair|repairs|repaired|repairing|service|services|serviced|servicing)\b", re.IGNORECASE), " repair "),
    (re.compile(r"\b(?:price|prices|pricing|cost|costs|costing|quote|quotes|estimate|estimates|pay|expensive|run)\b", re.IGNORECASE), " pricing "),
    (re.compile(r"\b(?:hours|hour|open|opened|opening|close|closed|closing)\b", re.IGNORECASE), " hours "),
    (re.compile(r"\b(?:availability|available|appointment|appointments|guarantee|guaranteed|promise|promised|tonight|after[\s-]*hours)\b", re.IGNORECASE), " availability "),
    (re.compile(r"\b(?:install|installs|installed|installing|installation|installations)\b", re.IGNORECASE), " install "),
    (re.compile(r"\b(?:replace|replaces|replaced|replacing|replacement|replacements)\b", re.IGNORECASE), " replace "),
    (re.compile(r"\b(?:remodel|remodels|remodeled|remodeling)\b", re.IGNORECASE), " remodel "),
    (re.compile(r"\b(?:maintain|maintains|maintained|maintaining|maintenance)\b", re.IGNORECASE), " maintain "),
    (re.compile(r"\b(?:inspect|inspects|inspected|inspecting|inspection|inspections)\b", re.IGNORECASE), " inspect "),
)

POLICY_MARKERS = ("pricing", "hours", "availability")
SERVICE_ENTITIES = {"waterheater", "airconditioning", "plumbing", "electrical", "heating"}
MATCH_REASONS = frozenset({
    "EXACT_APPROVED_TITLE",
    "APPROVED_PRICING_POLICY",
    "APPROVED_HOURS_POLICY",
    "APPROVED_AVAILABILITY_POLICY",
    "APPROVED_SERVICE_ENTITY_WATERHEATER",
    "APPROVED_SERVICE_ENTITY_AIRCONDITIONING",
    "APPROVED_SERVICE_ENTITY_PLUMBING",
    "APPROVED_SERVICE_ENTITY_ELECTRICAL",
    "APPROVED_SERVICE_ENTITY_HEATING",
    "APPROVED_CAPABILITY_SUMMARY",
    "APPROVED_LOCATION_TERM",
    "CONSERVATIVE_APPROVED_TERM_OVERLAP",
    "NO_APPROVED_MATCH",
    "SESSION_CORRECTION_CAPTURED",
})


def normalize_text(value: str) -> str:
    normalized = value.casefold()
    for pattern, replacement in ALIASES:
        normalized = pattern.sub(replacement, normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def significant_terms(value: str) -> set[str]:
    terms = {_canonical_term(term) for term in re.findall(r"[a-z0-9]{3,}", normalize_text(value))}
    return terms.difference(STOPWORDS)


def _canonical_term(term: str) -> str:
    """Apply bounded morphology so ordinary wording can match exact approved facts."""

    irregular = {
        "cabinets": "cabinet", "kitchens": "kitchen", "bathrooms": "bathroom",
        "windows": "window", "doors": "door", "fixtures": "fixture",
        "appliances": "appliance", "fans": "fan", "floors": "floor",
        "repairs": "repair", "offerings": "offer", "capabilities": "capability", "hours": "hours",
    }
    if term in irregular:
        return irregular[term]
    if term.endswith("ies") and len(term) > 5:
        return term[:-3] + "y"
    if term.endswith("s") and not term.endswith(("ss", "us")) and len(term) > 4:
        return term[:-1]
    return term


CAPABILITY_QUERY = re.compile(
    r"(?:what|which).{0,30}(?:service|services|capabilities).{0,30}(?:offer|provide|available|have)|"
    r"(?:service|services|capabilities).{0,20}(?:offer|provide|available)|what can you help with",
    re.IGNORECASE,
)
LOCATION_QUERY = re.compile(r"\b(?:work\s+in|serve|served|serving|located|location|area)\b", re.IGNORECASE)


def match_approved_entry(entries: list[dict[str, Any]], message: str) -> tuple[dict[str, Any] | None, str]:
    """Return one approved entry and an internal reason, or no match.

    Priority is exact title, explicit policy intent, recognized service entity, then conservative overlap.
    The function never composes or changes an approved statement.
    """

    clean = " ".join(str(message).split()).strip()
    message_normalized = normalize_text(clean)
    message_terms = significant_terms(clean)
    prepared: list[tuple[dict[str, Any], set[str], set[str]]] = []
    for entry in entries:
        title_terms = significant_terms(entry.get("title", ""))
        statement_terms = significant_terms(entry.get("statement", ""))
        prepared.append((entry, title_terms, statement_terms))
        if message_normalized == normalize_text(entry.get("title", "")):
            return entry, "EXACT_APPROVED_TITLE"

    for marker in POLICY_MARKERS:
        if marker not in message_terms:
            continue
        title_candidates = [item for item in prepared if marker in item[1]]
        candidates = title_candidates or [item for item in prepared if marker in item[2]]
        if candidates:
            best = max(candidates, key=lambda item: len(message_terms & (item[1] | item[2])))
            return best[0], f"APPROVED_{marker.upper()}_POLICY"

    entities = message_terms & SERVICE_ENTITIES
    if entities:
        candidates = [item for item in prepared if entities & item[2]]
        if candidates:
            best = max(candidates, key=lambda item: len(message_terms & (item[1] | item[2])))
            entity = sorted(entities & best[2])[0]
            return best[0], f"APPROVED_SERVICE_ENTITY_{entity.upper()}"

    if CAPABILITY_QUERY.search(clean):
        capability_candidates = [item for item in prepared if item[0].get("kind") == "CAPABILITY"]
        if capability_candidates:
            best = max(capability_candidates, key=lambda item: len(item[0].get("statement", "")))
            return best[0], "APPROVED_CAPABILITY_SUMMARY"

    if LOCATION_QUERY.search(clean):
        location_candidates = [item for item in prepared if message_terms & item[2]]
        if location_candidates:
            best = max(location_candidates, key=lambda item: len(message_terms & (item[1] | item[2])))
            if len(message_terms & best[2]) >= 1:
                return best[0], "APPROVED_LOCATION_TERM"

    best_entry = None
    best_score = 0
    best_overlap = 0
    for entry, title_terms, statement_terms in prepared:
        title_overlap = len(message_terms & title_terms)
        statement_overlap = len(message_terms & statement_terms)
        score = (title_overlap * 3) + statement_overlap
        if score > best_score:
            best_entry = entry
            best_score = score
            best_overlap = len(message_terms & (title_terms | statement_terms))
    query_coverage = best_overlap / max(1, len(message_terms))
    if (
        best_entry
        and best_overlap >= MATCHING_CONTRACT["minimum_distinct_term_overlap"]
        and best_score >= MATCHING_CONTRACT["minimum_weighted_score"]
        and query_coverage >= MATCHING_CONTRACT["minimum_query_coverage"]
    ):
        return best_entry, "CONSERVATIVE_APPROVED_TERM_OVERLAP"
    return None, "NO_APPROVED_MATCH"


def suggested_questions(entries: list[dict[str, Any]], limit: int = 4) -> list[dict[str, str]]:
    """Create owner-facing test questions that are proven to match the current KB."""

    candidates: list[tuple[str, dict[str, Any]]] = []
    capabilities = [entry for entry in entries if entry.get("kind") == "CAPABILITY"]
    if capabilities:
        expected = max(capabilities, key=lambda entry: len(entry.get("statement", "")))
        candidates.append(("What services do you offer?", expected))
    natural_templates = {
        "interior repairs": "What interior repairs do you handle?",
        "carpentry": "What carpentry repair work do you handle?",
        "flooring": "What flooring repair or installation work do you handle?",
        "kitchens": "What kitchen repair or remodeling work do you handle?",
        "bathrooms": "What bathroom repair or remodeling work do you handle?",
        "exterior repairs": "What exterior repairs do you handle?",
        "electrical": "What electrical repair or installation work do you handle?",
    }
    for entry in entries:
        title_key = " ".join(str(entry.get("title") or "").casefold().split()).strip(" .")
        if title_key in natural_templates:
            candidates.append((natural_templates[title_key], entry))
    for entry in entries:
        title = " ".join(str(entry.get("title") or "").split()).strip(" .")
        if not title or len(title) > 70 or title.casefold() not in natural_templates and entry.get("kind") not in {"FAQ", "POLICY"}:
            continue
        if title.endswith("?"):
            candidates.append((f"Regarding {title[:-1]}, what is the approved answer?", entry))
        else:
            candidates.append((f"What is included under {title}?", entry))
    suggestions: list[dict[str, str]] = []
    seen: set[str] = set()
    for question, expected in candidates:
        if question.casefold() in seen:
            continue
        match, reason = match_approved_entry(entries, question)
        if match and match["entry_id"] == expected["entry_id"] and reason != "EXACT_APPROVED_TITLE":
            suggestions.append({"question": question, "expected_entry_id": expected["entry_id"], "match_reason": reason})
            seen.add(question.casefold())
        if len(suggestions) >= limit:
            break
    return suggestions
