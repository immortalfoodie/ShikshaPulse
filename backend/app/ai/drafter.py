"""AI action drafting: from diagnosed signals to suggested, editable actions (never auto-ordered)."""

from __future__ import annotations

import logging
import re
from datetime import timedelta

from ..actions.service import library, track_record
from ..analytics import diagnose as dg
from ..analytics import radar as rd
from ..analytics.redistribution import suggestions
from ..config import today
from .guard import soften
from .llm import llm

log = logging.getLogger(__name__)
NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")

SIGNAL_TO_TRIGGER = {
    "maths_vacancy": "maths_vacancy",
    "student_attendance": "student_attendance",
    "teacher_attendance": "teacher_attendance",
    "infrastructure": "infrastructure",
}
RADAR_FLAG = {
    "maths_vacancy": "maths_vacancy",
    "student_attendance": "attendance_decline",
    "infrastructure": "infra_gap",
    "teacher_attendance": "teacher_attendance",
}


def draft_actions(unit_type: str, unit: str, schools: list[str] | None = None, max_items: int = 4) -> dict:
    d = dg.diagnose(unit_type, unit)
    lib = library()
    drafts = []
    period = d["period"]
    triggers = []
    for s in d["signals"]:
        if s["classification"] in ("HIGH", "MEDIUM") and d.get("direction") == "decline":
            triggers.append((SIGNAL_TO_TRIGGER[s["factor"]], s))
    if any("remainder_pp" in u for u in d["unresolved"]):
        triggers.append(("unexplained_decline", None))
    if d["verdict"] == "INSUFFICIENT_EVIDENCE" or any(
        s["classification"] == "INSUFFICIENT_EVIDENCE" for s in d["signals"]
    ):
        triggers.append(("insufficient_evidence", None))
    radar_schools = []
    if unit_type in ("block", "district"):
        radar_schools = rd.radar(unit_type, unit, min_flags=1, limit=100000)["schools"]
    for trig, s in triggers:
        iv = lib[trig]["actions"][0]
        target_schools = []
        if s and s["factor"] in RADAR_FLAG:
            flag = RADAR_FLAG[s["factor"]]
            target_schools = [x for x in radar_schools if flag in x["flags"]][:12]
        if schools:
            target_schools = [x for x in radar_schools if x["udise_code"] in schools] or target_schools
        evidence = []
        if s:
            evidence.append(
                {
                    "signal": s["factor"],
                    "label": s["label"],
                    "classification": s["classification"],
                    "baseline": s.get("baseline"),
                    "latest": s.get("latest"),
                    "change": s.get("change"),
                    "period": period,
                }
            )
            why = (
                f"{s['label']} moved from {s.get('baseline')} to {s.get('latest')} over {period} "
                f"({s['classification'].lower()} signal, associated with an estimated {s.get('contribution_pp')} pp "
                f"of the outcome change)."
            )
        elif trig == "unexplained_decline":
            why = (
                f"{abs(d['remainder_pp'])} pp of the change over {period} is not associated with tracked indicators; "
                "classroom-level evidence is needed."
            )
            evidence.append({"unresolved": True, "remainder_pp": d["remainder_pp"], "period": period})
        else:
            why = "Key supporting data is incomplete; complete the returns before deciding on a programme."
            evidence.append({"insufficient": True, "period": period})
        drafts.append(
            {
                "intervention_key": iv["key"],
                "trigger": trig,
                "title": f"{iv['title']} — {d['unit']}",
                "description": why,
                "owner_role": iv["owner_role"],
                "unit_type": unit_type,
                "unit": d["unit"],
                "priority": "High" if (s and s["classification"] == "HIGH") else "Medium",
                "due_date": (today() + timedelta(days=iv["days"])).isoformat(),
                "implementation": iv["implementation"],
                "learning": iv["learning"],
                "schools": [{"udise_code": x["udise_code"], "school_name": x["school_name"]} for x in target_schools],
                "alternatives": [{"key": a["key"], "title": a["title"]} for a in lib[trig]["actions"][1:]],
                "evidence": evidence,
                "issue_title": f"{d['unit']}: {lib[trig]['label']}",
            }
        )
    drafts = drafts[:max_items]
    for x in drafts:
        x["track_record"] = track_record(x["intervention_key"])
        x["alternatives"] = [{**alt, "track_record": track_record(alt["key"])} for alt in x["alternatives"]]
        if x["trigger"] == "maths_vacancy" and unit_type in ("block", "district"):
            x["sharing"] = suggestions(unit_type, d["unit"], schools, limit=6)["pairs"]
    note = "Suggestions from the intervention library based on detected indicators. The officer decides."
    if drafts and llm().available:
        try:
            out = llm().complete_json(
                "You write one-sentence rationales for education officers. Use ONLY the numbers given. Never claim "
                "causation; say 'associated with' or 'coincided with'. Reply JSON {\"rationales\": [str, ...]}.",
                str([{"action": x["title"], "facts": x["description"]} for x in drafts]),
                timeout=8,
            )
            rationales = out.get("rationales", [])
            # The LLM may return fewer rationales than drafts; unmatched drafts keep the template text.
            for draft, rationale in zip(drafts, rationales, strict=False):
                if isinstance(rationale, str) and rationale.strip():
                    nums_ok = all(tok in draft["description"] for tok in NUMBER_RE.findall(rationale))
                    if nums_ok:
                        draft["description"] = soften(rationale.strip())[0]
                        draft["rationale_by"] = "ai"
            note += " Rationales drafted by AI and number-checked."
        except Exception:  # LLM is optional: fall back to deterministic rationales.
            log.warning("LLM rationale drafting failed; using template rationales", exc_info=True)
    return {"unit_type": unit_type, "unit": d["unit"], "verdict": d["verdict"], "drafts": drafts, "note": note}
