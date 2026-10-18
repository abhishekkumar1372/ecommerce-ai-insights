"""Check every number in generated text against the facts it cites.

The model is told to use only the facts it is given. This module enforces it:
each number written in a bullet must match (after unit handling and rounding)
one of the facts that bullet cites. Anything else is reported as unverified.
"""
import re
from dataclasses import dataclass, field

NUMBER = re.compile(
    r"(?P<prefix>R\$\s?|\$)?(?P<sign>[-+−])?(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
    r"\s?(?P<suffix>%|pp|k|K|M|m|mn|million|thousand)?(?![\w])"
)
SCALE = {"k": 1e3, "K": 1e3, "thousand": 1e3, "M": 1e6, "m": 1e6, "mn": 1e6, "million": 1e6}


@dataclass
class Mention:
    text: str
    value: float
    is_pct: bool


@dataclass
class CheckResult:
    verified: list[str] = field(default_factory=list)
    unverified: list[str] = field(default_factory=list)
    unknown_fact_ids: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.unverified and not self.unknown_fact_ids

    def as_dict(self) -> dict:
        return {"passed": self.passed, "verified": self.verified, "unverified": self.unverified,
                "unknown_fact_ids": self.unknown_fact_ids}


def extract_numbers(text: str) -> list[Mention]:
    out = []
    for m in NUMBER.finditer(text):
        raw = m.group("num").replace(",", "")
        value = float(raw)
        suffix = m.group("suffix") or ""
        if suffix in SCALE:
            value *= SCALE[suffix]
        if m.group("sign") in ("-", "−"):
            value = -value
        is_pct = suffix in ("%", "pp")
        # Skip years, and small bare integers used as counts of things in the text ("top 3", "2 actions").
        bare_integer = not is_pct and not m.group("prefix") and "." not in raw and not suffix
        if bare_integer and (1900 <= value <= 2100 or abs(value) <= 10):
            continue
        out.append(Mention(m.group(0).strip(), value, is_pct))
    return out


def _decimals(text: str) -> int:
    m = re.search(r"\.(\d+)", text)
    return len(m.group(1)) if m else 0


def matches(mention: Mention, fact: dict) -> bool:
    if not isinstance(fact["value"], (int, float)):
        return False
    target = float(fact["value"])
    if fact["unit"] == "pct":
        if not mention.is_pct:
            return False
        target *= 100
    elif mention.is_pct:
        return False
    written = abs(mention.value)
    # Allow the rounding a writer would naturally apply: to the decimals shown, or ~1% for scaled values (70.7k).
    tolerance = max(0.5 * 10 ** -_decimals(mention.text), 0.01 * abs(target) if abs(target) >= 1000 else 0)
    # A "down 22.5%" phrasing writes the magnitude of a negative fact.
    return abs(written - abs(target)) <= tolerance + 1e-9 and (mention.value >= 0 or target < 0)


def check_point(text: str, fact_ids: list[str], facts: dict[str, dict], result: CheckResult) -> None:
    unknown = [f for f in fact_ids if f not in facts]
    result.unknown_fact_ids.extend(unknown)
    cited = [facts[f] for f in fact_ids if f in facts]
    for mention in extract_numbers(text):
        if any(matches(mention, f) for f in cited):
            result.verified.append(mention.text)
        else:
            result.unverified.append(f"{mention.text} in: {text}")
