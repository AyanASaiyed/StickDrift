"""Turn a resident's session history into measured findings and potential concerns.

Everything here is deterministic and computed from the resident's own sessions:
the latest results are compared with the median of their earlier ones. Concerns
describe a *functional* change worth checking (e.g. "one-sided slowing") with
possible everyday contributors and recommended caregiver checks. They never
name a disease: joystick data cannot support a diagnosis.
"""
from statistics import median
from typing import Dict, List, Optional

# How far a measurement must move from the personal baseline to count.
LATENCY_RISE_MS = 150.0
ACCURACY_DROP = 0.15  # share of prompts, ~2 of 12
GAP_CHANGE_MS = 150.0
ENJOYMENT_DROP = 2
MIN_USABLE = 4

REFERENCES = {
    "der_deary": "Der G, Deary IJ. Age and sex differences in reaction time in adulthood: results from the "
                 "United Kingdom Health and Lifestyle Survey. Psychol Aging. 2006;21(1):62-73.",
    "macdonald": "MacDonald SWS, Hultsch DF, Dixon RA. Performance variability is related to change in "
                 "cognition: evidence from the Victoria Longitudinal Study. Psychol Aging. 2003;18(3):510-523.",
    "ranganathan": "Ranganathan VK, Siemionow V, Sahgal V, Yue GH. Effects of aging on hand function. "
                   "J Am Geriatr Soc. 2001;49(11):1478-1484.",
    "beers": "2023 American Geriatrics Society Beers Criteria Update Expert Panel. American Geriatrics Society "
             "2023 updated AGS Beers Criteria for potentially inappropriate medication use in older adults. "
             "J Am Geriatr Soc. 2023;71(7):2052-2081.",
    "cam": "Inouye SK, et al. Clarifying confusion: the Confusion Assessment Method. "
           "Ann Intern Med. 1990;113(12):941-948.",
    "steadi": "Centers for Disease Control and Prevention. STEADI: Stopping Elderly Accidents, Deaths & "
              "Injuries - older adult fall prevention toolkit.",
}

DISCLAIMER = ("A prompt to check in, not a diagnosis. Changes can come from tiredness, pain, medication, "
              "vision, mood or an unfamiliar setup.")


def _acc(correct: Optional[int], valid: Optional[int]) -> Optional[float]:
    return correct / valid if correct is not None and valid else None


def _metrics(s: dict) -> Dict[str, Optional[float]]:
    left, right = s.get("left_median_latency_ms"), s.get("right_median_latency_ms")
    return {
        "left_latency": left,
        "right_latency": right,
        "left_accuracy": _acc(s.get("left_correct"), s.get("left_valid")),
        "right_accuracy": _acc(s.get("right_correct"), s.get("right_valid")),
        "both_accuracy": _acc(s.get("both_correct"), s.get("both_valid")),
        "lr_gap": left - right if left is not None and right is not None else None,
        "enjoyment": s.get("enjoyment"),
    }


# key -> (label, hand, kind). kind decides formatting and which direction is worse.
MEASURES = {
    "left_latency": ("Left-hand response time", "left", "latency"),
    "right_latency": ("Right-hand response time", "right", "latency"),
    "left_accuracy": ("Left-hand accuracy", "left", "accuracy"),
    "right_accuracy": ("Right-hand accuracy", "right", "accuracy"),
    "both_accuracy": ("Both-hands accuracy", "both", "accuracy"),
    "lr_gap": ("Left minus right response time", None, "gap"),
    "enjoyment": ("Enjoyment rating", None, "enjoyment"),
}


def fmt(kind: str, v: float) -> str:
    if kind == "latency":
        return f"{v / 1000:.2f} s"
    if kind == "gap":
        return f"{v / 1000:+.2f} s"
    if kind == "accuracy":
        return f"{round(v * 100)}%"
    return f"{v:.0f}/5" if float(v).is_integer() else f"{v:.1f}/5"


def _fmt_change(kind: str, delta: float) -> str:
    if kind in ("latency", "gap"):
        return f"{delta / 1000:+.2f} s"
    if kind == "accuracy":
        return f"{round(delta * 100):+d} pts"
    return f"{delta:+.1f}"


def _worse(kind: str, base: float, now: float) -> bool:
    if kind == "latency":
        return now - base >= LATENCY_RISE_MS
    if kind == "accuracy":
        return base - now >= ACCURACY_DROP - 1e-9
    if kind == "gap":
        return abs(now - base) >= GAP_CHANGE_MS
    return base - now >= ENJOYMENT_DROP


def _better(kind: str, base: float, now: float) -> bool:
    if kind == "latency":
        return base - now >= LATENCY_RISE_MS
    if kind == "accuracy":
        return now - base >= ACCURACY_DROP - 1e-9
    if kind == "gap":
        return False
    return now - base >= ENJOYMENT_DROP


def _finding(key: str, baseline: List[dict], recent: List[dict]) -> Optional[dict]:
    label, hand, kind = MEASURES[key]
    base_vals = [m[key] for m in baseline if m[key] is not None]
    latest = recent[0]
    now = latest[key]
    if not base_vals or now is None:
        return None
    base = median(base_vals)
    flagged_ids = [m["session_id"] for m in recent if m[key] is not None and _worse(kind, base, m[key])]
    worse = _worse(kind, base, now)
    direction = "worse" if worse else "better" if _better(kind, base, now) else "steady"
    text = f"{label}: {fmt(kind, now)} vs usual {fmt(kind, base)} ({_fmt_change(kind, now - base)})."
    return {
        "key": key, "label": label, "hand": hand, "kind": kind,
        "baseline": base, "latest": now, "change": now - base,
        "baseline_text": fmt(kind, base), "latest_text": fmt(kind, now),
        "change_text": _fmt_change(kind, now - base),
        "direction": direction, "flagged": worse,
        "persistent": worse and len(flagged_ids) == len(recent) and len(recent) > 1,
        "flagged_session_ids": flagged_ids if worse else [],
        "text": text,
    }


def _concern(cid, title, level, summary, evidence, contributors, checks, refs, keys):
    return {
        "id": cid, "title": title, "level": level, "summary": summary,
        "evidence": evidence, "possible_contributors": contributors,
        "recommended_checks": checks, "references": [REFERENCES[r] for r in refs],
        "measurements": keys,
    }


def _concerns(f: Dict[str, dict], recent_abandoned: int) -> List[dict]:
    def worse(k):
        return k in f and f[k]["flagged"]

    def level(keys):
        hits = [f[k] for k in keys if worse(k)]
        return "check" if len(hits) >= 2 or any(h["persistent"] for h in hits) else "watch"

    out: List[dict] = []
    general = (worse("left_latency") and worse("right_latency")) or (
        worse("left_accuracy") and worse("right_accuracy"))

    if general:
        keys = [k for k in ("left_latency", "right_latency", "left_accuracy", "right_accuracy",
                            "both_accuracy") if worse(k)]
        out.append(_concern(
            "general_slowing", "Slower or less accurate in both hands", level(keys),
            "Both hands changed together, which points to something affecting the whole person rather than "
            "one hand.",
            [f[k]["text"] for k in keys],
            ["Tiredness or poor sleep", "Acute illness, infection or dehydration",
             "A new or changed medication, especially a sedating one", "Pain, low mood or distraction"],
            ["Ask how they slept and how they are feeling today.",
             "Check temperature, fluid intake and any signs of infection.",
             "Review medication changes from the last two weeks with the pharmacist or prescriber.",
             "Watch for new confusion or a drop in alertness. If it is sudden, escalate to the nurse the same day.",
             "Consider a falls-risk check, since slower reactions can raise fall risk.",
             "Repeat the activity at the usual time in 1-2 days. If the change persists, request a nursing or "
             "physician assessment."],
            ["der_deary", "beers", "cam", "steadi"], keys))
    else:
        for hand, other in (("left", "right"), ("right", "left")):
            keys = [k for k in (f"{hand}_latency", f"{hand}_accuracy") if worse(k)]
            if not keys:
                continue
            keys += [k for k in ("lr_gap", "both_accuracy") if worse(k)]
            steady = [f[k]["text"] for k in (f"{other}_latency", f"{other}_accuracy") if k in f]
            out.append(_concern(
                f"one_sided_{hand}", f"One-sided change: {hand} hand", level(keys),
                f"The {hand} hand changed while the {other} hand stayed close to usual. Tiredness and "
                "attention usually affect both hands, so a one-sided change is worth a closer look.",
                [f[k]["text"] for k in keys] + [f"Unchanged for comparison - {t}" for t in steady],
                [f"Pain, stiffness or injury in the {hand} hand, wrist or thumb",
                 "An arthritis flare or swelling",
                 f"New numbness, tingling, weakness or clumsiness on the {hand} side",
                 f"Difficulty seeing the {hand} side of the screen",
                 "A change in how the controller was held or placed"],
                [f"Ask about pain, stiffness or injury in the {hand} hand, wrist or thumb, and look for swelling.",
                 "Compare grip and finger movement between both hands (for example, ask them to squeeze both "
                 "of your hands).",
                 f"Ask about new numbness, tingling or clumsiness on the {hand} side. If weakness, facial droop "
                 "or speech difficulty is new or sudden, follow your facility's urgent escalation protocol now.",
                 "Check the setup: glasses, seating and screen position, and how the controller was held.",
                 "Repeat the activity in 1-2 days. If the change persists, request a nursing or physician "
                 "assessment, and consider an occupational therapy hand-function review."],
                ["ranganathan", "der_deary"], keys))

    if worse("both_accuracy") and not general and not out:
        keys = ["both_accuracy"]
        out.append(_concern(
            "coordination", "Lower two-hand coordination", level(keys),
            "Using both sticks together got harder while each hand on its own stayed close to usual.",
            [f["both_accuracy"]["text"]],
            ["Reduced concentration or divided attention", "Tiredness",
             "A noisy or distracting setting", "Feeling unwell"],
            ["Note anything distracting in the room during the session.",
             "Ask about concentration, sleep and how they are feeling.",
             "Repeat the activity in a quiet setting in 1-2 days.",
             "If it persists alongside changes in memory or daily routines, raise it with the care team and "
             "consider a cognitive screen under your facility's process."],
            ["macdonald"], keys))

    if worse("enjoyment") or recent_abandoned >= 2:
        keys = ["enjoyment"] if worse("enjoyment") else []
        evidence = [f["enjoyment"]["text"]] if worse("enjoyment") else []
        if recent_abandoned >= 2:
            evidence.append(f"{recent_abandoned} of the last 3 sessions were stopped early.")
        out.append(_concern(
            "engagement", "Less engagement than usual", "watch",
            "The resident is enjoying or finishing the activity less than usual.",
            evidence,
            ["Low mood", "Pain or discomfort", "Tiredness", "Frustration with the activity"],
            ["Ask how they are feeling and what they thought of the activity.",
             "Check for pain or discomfort.",
             "Offer the activity at a different time of day.",
             "If low mood continues, mention it at the next care-team review."],
            ["macdonald"], keys))

    return out


def analyze(sessions: List[dict]) -> dict:
    """Sessions come newest-first, as returned by views._fetch_sessions."""
    usable = [s for s in sessions if s["status"] == "completed" and s["quality"] in ("good", "flagged")]
    synthetic = any(s.get("is_synthetic") for s in sessions)
    recent_abandoned = sum(1 for s in sessions[:3] if s["status"] == "abandoned")
    base = {"usable_sessions": len(usable), "synthetic": synthetic, "disclaimer": DISCLAIMER}

    if len(usable) < MIN_USABLE:
        return {**base, "status": "insufficient", "risk": "none", "baseline_sessions": 0,
                "recent_session_ids": [], "findings": [], "concerns": [],
                "summary": f"Not enough completed sessions yet to set a personal baseline "
                           f"({len(usable)} of {MIN_USABLE})."}

    # With enough history, compare the last two sessions so a persisting change is visible
    # and the baseline isn't contaminated by it.
    recent_n = 2 if len(usable) >= 5 else 1
    recent = [{"session_id": s["session_id"], **_metrics(s)} for s in usable[:recent_n]]
    baseline = [{"session_id": s["session_id"], **_metrics(s)} for s in usable[recent_n:]]

    findings = [x for x in (_finding(k, baseline, recent) for k in MEASURES) if x]
    by_key = {x["key"]: x for x in findings}
    concerns = _concerns(by_key, recent_abandoned)

    risk = "check" if any(c["level"] == "check" for c in concerns) else "watch" if concerns else "none"
    if concerns:
        summary = "; ".join(c["title"] for c in concerns) + "."
    else:
        summary = "Recent sessions are in line with this resident's usual pattern."
    return {**base, "status": "ok", "risk": risk, "baseline_sessions": len(baseline),
            "recent_session_ids": [m["session_id"] for m in recent], "findings": findings, "concerns": concerns, "summary": summary}


def review_from(insights: dict) -> dict:
    """Short card form used in lists: flagged + the measurements that moved."""
    concerns = insights["concerns"]
    keys = {k for c in concerns for k in c["measurements"]}
    reasons = [f["text"] for f in insights["findings"] if f["key"] in keys]
    if concerns and not reasons:
        reasons = [e for c in concerns for e in c["evidence"]]
    return {"flagged": bool(concerns), "reasons": reasons}
