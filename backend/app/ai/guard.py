"""Evidence Guard — checks an AI answer before the officer sees it.

1. Numbers: every number must match a value in the tool outputs (rounding tolerance).
2. Citations: every finding must cite existing evidence ids and carry a reporting period.
3. Labels: findings are observed_fact / associated_signal / unresolved_question, and a finding that
   cites an associated signal cannot be presented as an observed fact.
4. Causal language: "caused", "due to", "because of", "led to" (and Hindi equivalents) are softened
   to associative wording — the platform only has observational evidence.
5. Honesty: if the evidence contains insufficient/conflicting/unexplained items, the answer must
   surface them as unresolved questions (the guard adds any the model omitted, and says so).

The badge shown is "Numbers verified against source calculations" — it certifies the numbers
and citations, not that every interpretation is proven.
"""
from __future__ import annotations

import re

from .evidence import EvidenceStore

LABELS = {"observed_fact", "associated_signal", "unresolved_question"}

CAUSAL_EN = [
    (r"\bwas caused by\b", "coincided with"), (r"\bis caused by\b", "is associated with"),
    (r"\bcaused by\b", "associated with"), (r"\bcaused\b", "coincided with"), (r"\bcauses\b", "is associated with"),
    (r"\bdue to\b", "alongside"), (r"\bbecause of\b", "alongside"), (r"\bowing to\b", "alongside"),
    (r"\bled to\b", "coincided with"), (r"\bleads to\b", "is associated with"),
    (r"\bresulted in\b", "coincided with"), (r"\bresulting in\b", "alongside"), (r"\bas a result of\b", "alongside"),
    (r"\bis responsible for\b", "is associated with"), (r"\bwas responsible for\b", "was associated with"),
    (r"\bdrove\b", "coincided with"), (r"\bdriven by\b", "associated with"), (r"\bthe reason (?:is|was)\b",
                                                                               "a possible contributing signal is"),
    (r"\bexplains why\b", "is associated with the fact that"),
]
CAUSAL_HI = [
    (r"के कारण", "के साथ-साथ"), (r"की वजह से", "के साथ-साथ"), (r"कारण बना", "से जुड़ा रहा"),
    (r"कारण है", "से जुड़ा संकेत है"), (r"कारण था", "से जुड़ा संकेत था"), (r"जिम्मेदार है", "से जुड़ा है"),
    (r"जिम्मेदार था", "से जुड़ा था"), (r"की वजह", "से जुड़ा"),
    (r"कारणामुळे", "सोबतच"), (r"मुळे", "सोबत"),            # Marathi
    (r"কারণে", "সঙ্গে"), (r"এর ফলে", "এর সঙ্গে"),         # Bengali
    (r"காரணமாக", "உடன்"), (r"ஏற்படுத்தியது", "உடன் நிகழ்ந்தது"),  # Tamil
    (r"కారణంగా", "తో పాటు"), (r"వల్ల", "తో పాటు"),          # Telugu
]
# A number: not glued to a preceding word/decimal/denominator, never split mid-decimal, and allowed to be
# followed by "/" (e.g. "66.7/100") or by Indic script suffixes (e.g. Bengali "45টি").
NUM_RE = re.compile(r"(?<![\w.\-/])[-−+]?\d+(?:,\d{2,3})*(?:\.\d+)?(?![.,]?\d)(?![A-Za-z_])")
SKIP_BEFORE = re.compile(r"\b(grade|class|std|standard)\s*$|कक्षा\s*$", re.I)
YEAR_RE = re.compile(r"\b20\d{2}(?:\s*[-–/]\s*\d{2,4})?\b")


def _numbers_in(text: str) -> list[tuple[str, float]]:
    masked = YEAR_RE.sub(lambda m: " " * len(m.group(0)), text)
    out = []
    for m in NUM_RE.finditer(masked):
        if SKIP_BEFORE.search(masked[max(0, m.start() - 12):m.start()]):
            continue
        raw = m.group(0).replace("−", "-").replace(",", "")  # thousands separators (1,168 / 1,16,800)
        try:
            out.append((m.group(0), float(raw)))
        except ValueError:
            continue
    return out


def _matches(x: float, allowed: set[float], text_token: str) -> bool:
    is_int_written = "." not in text_token and "," not in text_token
    for v in allowed:
        for cand in (v, -v, abs(v)):
            if abs(x - cand) <= 0.051:
                return True
            if is_int_written and abs(cand) >= 1 and abs(x - cand) < 0.5:
                return True
            if abs(cand) >= 10 and abs(x - cand) / abs(cand) <= 0.01:
                return True
    return False


def soften(text: str) -> tuple[str, int]:
    n = 0
    for pat, rep in CAUSAL_EN + CAUSAL_HI:
        text, k = re.subn(pat, rep, text, flags=re.I)
        n += k
    return text, n


def check(answer: dict, store: EvidenceStore, question: str = "") -> dict:
    """Validate and repair an answer in place. Returns the guard report."""
    allowed = store.numbers() | {float(n) for _, n in _numbers_in(question)}
    report = {"numbers_checked": 0, "numbers_verified": 0, "unverified_numbers": [], "citation_errors": [],
              "relabelled": 0, "causal_softened": 0, "periods_filled": 0, "unresolved_added": 0, "notes": []}
    findings = answer.get("findings") or []
    texts = [("summary", answer.get("summary", ""))]
    texts += [(f"finding {i + 1}", f.get("text", "")) for i, f in enumerate(findings)]
    texts += [(f"next step {i + 1}", s) for i, s in enumerate(answer.get("next_steps") or [])]
    for where, t in texts:
        for tok, x in _numbers_in(t or ""):
            report["numbers_checked"] += 1
            if _matches(x, allowed, tok):
                report["numbers_verified"] += 1
            else:
                report["unverified_numbers"].append({"value": tok, "where": where})

    for i, f in enumerate(findings):
        if f.get("label") not in LABELS:
            f["label"] = "associated_signal"
            report["relabelled"] += 1
        ev = [e for e in (f.get("evidence") or []) if e in store.items]
        bad = [e for e in (f.get("evidence") or []) if e not in store.items]
        if bad:
            report["citation_errors"].append({"finding": i + 1, "error": f"unknown evidence id(s) {bad}"})
        if not ev:
            report["citation_errors"].append({"finding": i + 1, "error": "no evidence cited"})
        f["evidence"] = ev
        types = {store.items[e]["type"] for e in ev}
        if f["label"] == "observed_fact" and "associated_signal" in types:
            f["label"] = "associated_signal"
            report["relabelled"] += 1
        if f["label"] != "unresolved_question" and types == {"unresolved_question"}:
            f["label"] = "unresolved_question"
            report["relabelled"] += 1
        if not f.get("period"):
            periods = [store.items[e]["period"] for e in ev if store.items[e].get("period")]
            if periods:
                f["period"] = periods[0]
                report["periods_filled"] += 1

    # Causal language is softened everywhere.
    if answer.get("summary"):
        answer["summary"], n = soften(answer["summary"])
        report["causal_softened"] += n
    for f in findings:
        f["text"], n = soften(f.get("text", ""))
        report["causal_softened"] += n
    answer["next_steps"] = [soften(s)[0] for s in answer.get("next_steps") or []]

    # Unresolved evidence must be surfaced.
    unresolved = store.of_type("unresolved_question")
    cited = {e for f in findings for e in f.get("evidence", [])}
    for u in unresolved:
        if u["id"] not in cited and u["kind"] in ("unresolved", "signal", "quality_warning", "comparability"):
            text = u["data"].get("text") or "; ".join(u["data"].get("warnings", []) or u["data"].get("caveats", [])) \
                or u["title"]
            findings.append({"label": "unresolved_question", "text": text, "evidence": [u["id"]],
                             "period": u.get("period"), "added_by_guard": True})
            report["unresolved_added"] += 1
    answer["findings"] = findings
    if report["unresolved_added"]:
        report["notes"].append(f"Guard added {report['unresolved_added']} unresolved question(s) the answer omitted.")
    if report["causal_softened"]:
        report["notes"].append(f"{report['causal_softened']} causal phrase(s) softened to associative wording.")
    if report["relabelled"]:
        report["notes"].append(f"{report['relabelled']} finding label(s) corrected to match their evidence.")
    report["passed"] = not report["unverified_numbers"] and not report["citation_errors"]
    report["badge"] = (f"Numbers verified against source calculations ({report['numbers_verified']}/"
                       f"{report['numbers_checked']})" if report["passed"] else "Verification failed")
    return report
