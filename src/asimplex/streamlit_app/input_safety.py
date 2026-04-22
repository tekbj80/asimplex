"""Rule-based input safety checks for chat prompts."""

from __future__ import annotations

import re
from typing import Any


_GAP = r".{0,40}"

# (rule_name, severity_score, patterns)
_RULES: tuple[tuple[str, int, tuple[str, ...]], ...] = (
    (
        "prompt_exfiltration",
        3,
        (
            rf"\b(show|reveal|print|display|tell)\b{_GAP}\b(system|developer)\s+prompt\b",
            rf"\b(what\s+is|give|share)\b{_GAP}\b(system|developer)\s+prompt\b",
            rf"\b(show|reveal|print|display)\b{_GAP}\b(hidden|internal|secret)\b{_GAP}\b(instructions?|prompt|policy)\b",
        ),
    ),
    (
        "instruction_override",
        2,
        (
            rf"\b(ignore|disregard|override)\b{_GAP}\b(previous|prior)\b{_GAP}\b(instructions?|rules?)\b",
            rf"\b(ignore|bypass|override)\b{_GAP}\b(system|developer)\b{_GAP}\b(instructions?|rules?|prompt)\b",
        ),
    ),
    (
        "tool_bypass",
        2,
        (
            rf"\b(bypass|skip|ignore)\b{_GAP}\b(validation|checks?|constraints?)\b",
            rf"\b(call|invoke|run)\b{_GAP}\btool\b{_GAP}\b(directly|without\s+checks?)\b",
        ),
    ),
)


_ALLOWLIST: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bwhat\s+is\s+a\s+system\s+prompt\b", re.IGNORECASE),
    re.compile(r"\bexplain\s+prompt\s+injection\b", re.IGNORECASE),
)


def _normalize_text(text: str) -> str:
    lowered = str(text or "").lower()
    lowered = re.sub(r"[\r\n\t]+", " ", lowered)
    lowered = re.sub(r"[^a-z0-9\s]", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered).strip()
    return lowered


def check_user_prompt_risk(message: str) -> dict[str, Any]:
    """Classify whether a user message should be blocked by safety rules."""
    text = str(message or "")
    normalized = _normalize_text(text)

    for allowed_pattern in _ALLOWLIST:
        if allowed_pattern.search(normalized):
            return {
                "allowed": True,
                "risk_level": "low",
                "matched_rules": [],
                "offending_phrases": [],
                "reason": "",
                "sanitized_message": text,
            }

    matched_rules: list[str] = []
    offending_phrases: list[str] = []
    risk_score = 0

    for rule_name, severity, patterns in _RULES:
        rule_hit = False
        for pattern in patterns:
            match = re.search(pattern, normalized, flags=re.IGNORECASE)
            if not match:
                continue
            rule_hit = True
            offending_phrases.append(match.group(0))
        if rule_hit:
            matched_rules.append(rule_name)
            risk_score += severity

    deduped_phrases = list(dict.fromkeys(offending_phrases))
    is_blocked = risk_score >= 3
    return {
        "allowed": not is_blocked,
        "risk_level": "high" if is_blocked else ("medium" if risk_score > 0 else "low"),
        "matched_rules": matched_rules,
        "offending_phrases": deduped_phrases,
        "reason": "Potential jailbreak or prompt-injection pattern detected." if is_blocked else "",
        "sanitized_message": text,
    }

