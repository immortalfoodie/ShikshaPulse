"""District Review Meeting Brief — one page an officer can take into the monthly review."""

from __future__ import annotations

import io
from datetime import datetime

from ..actions import service as actions
from ..analytics import diagnose as dg
from ..analytics import expected as ex
from ..analytics import peers as pr
from ..analytics import quality as q
from ..analytics import radar as rd
from ..analytics import trends as tr
from ..auth import clamp_school_scope
from ..config import settings
from .assistant import ask


def build_brief(unit_type: str, unit: str | None, user: dict, lang: str = "en") -> dict:
    o = tr.overview(unit_type, unit)
    unit = o["unit"]
    t = tr.trend("numeracy", unit_type, unit)
    d = dg.diagnose(unit_type, unit)
    qa = ask(f"Why did foundational numeracy change in {unit if unit_type != 'state' else 'the state'}?", user, lang)
    brief = {
        "title": f"Review Meeting Brief — {o['unit_label']}",
        "unit_type": unit_type,
        "unit": unit,
        "generated_at": datetime.now().strftime("%d %b %Y %H:%M"),
        "prepared_for": user["name"],
        "period": d["period"],
        "data_tier": "SYNTHETIC DEMO DATA" if settings()["mode"] == "demo" else "Department-uploaded data",
        "lang": lang,
        "data_confidence": d["data_confidence"],
        "data_confidence_label": d["data_confidence_label"],
        "summary": qa["answer"],
        "guard": qa["guard"],
        "engine": qa["engine"],
        "trend": [{"year": p["year"], "value": p["value"]} for p in t["points"]],
        "trend_change": t["change_pp"],
        "rank": o["rank"],
        "kpis": o["kpis"],
        "signals": [s for s in d["signals"] if s["classification"] != "NONE"],
        "context": d["context"],
        "unresolved": d["unresolved"],
        "verdict": d["verdict"],
        "verdict_reason": d["verdict_reason"],
    }
    if unit_type in ("state", "district"):
        kids = dg.children_reasons(unit_type, unit, limit=6)
        brief["concentration"] = kids
        if unit_type == "district":
            res = {r["unit"]: r for r in ex.residual_ranking("block")}
            brief["expected_vs_actual"] = [res[k["unit"]] for k in kids if k["unit"] in res]
        declining = [k for k in kids if k["change_pp"] is not None and k["change_pp"] < 0 and k["unit_type"] == "block"]
        if declining:
            brief["peers"] = pr.peers(declining[0]["unit"], election_only=True)
    elif unit_type == "block":
        brief["expected_vs_actual_block"] = ex.expected_vs_actual("block", unit)
        brief["peers"] = pr.peers(unit, election_only=True)
    rut, ru = clamp_school_scope(user, unit_type, unit)
    r = rd.radar(rut, ru)
    brief["radar"] = {
        "unit": r["unit"],
        "n_schools": r["n_schools"],
        "n_flagged": r["n_flagged"],
        "n_priority": r["n_priority"],
        "schools": r["schools"][:6],
    }
    acts = actions.list_actions(
        user, unit_type if unit_type != "state" else None, unit if unit_type != "state" else None
    )
    acts = actions.for_user(user, acts) if user else acts
    brief["actions"] = [
        {
            "id": a["id"],
            "title": a["title"],
            "intervention_key": a.get("intervention_key"),
            "unit": a["unit"],
            "owner": a["owner_name"],
            "due": a["due_date"],
            "status": a["status"],
            "outcome_status": a["outcome_status"],
            "overdue": a["overdue"],
            "simulated": a["is_simulated"],
        }
        for a in acts
    ]
    brief["actions_summary"] = actions.summary(acts)
    uq = q.unit_quality(unit_type, unit)
    brief["limitations"] = uq["warnings"] + d["data_gaps"]
    brief["limitation_items"] = uq.get("warning_items", [])
    brief["data_gap_keys"] = d.get("data_gap_keys", [])
    return brief


def brief_pdf(brief: dict) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title=brief["title"],
    )
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Heading1"], fontSize=16, spaceAfter=4, textColor=colors.HexColor("#1e1b4b"))
    h2 = ParagraphStyle(
        "h2", parent=ss["Heading2"], fontSize=11.5, spaceBefore=8, spaceAfter=3, textColor=colors.HexColor("#3730a3")
    )
    body = ParagraphStyle("b", parent=ss["BodyText"], fontSize=9, leading=12)
    small = ParagraphStyle("s", parent=body, fontSize=7.5, textColor=colors.HexColor("#6b7280"))
    tag = {"observed_fact": "FACT", "associated_signal": "SIGNAL", "unresolved_question": "OPEN QUESTION"}

    def esc(s) -> str:
        return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def table(rows, widths):
        t = Table(rows, colWidths=widths, repeatRows=1)
        t.setStyle(
            TableStyle(
                [
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2ff")),
                    ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#c7d2fe")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        return t

    el = [
        Paragraph(esc(brief["title"]), h1),
        Paragraph(
            f"{esc(brief['data_tier'])} · Period {esc(brief['period'])} · Generated {esc(brief['generated_at'])}"
            f" for {esc(brief['prepared_for'])} · Data confidence {brief['data_confidence']}/100 "
            f"({esc(brief['data_confidence_label'])})",
            small,
        ),
    ]
    if brief.get("lang", "en") != "en":
        el.append(
            Paragraph(
                "Hindi text is best printed from the web brief (browser print); this PDF uses English fonts.", small
            )
        )
    el += [Paragraph("Summary", h2), Paragraph(esc(brief["summary"].get("summary", "")), body)]
    for f in brief["summary"].get("findings", [])[:8]:
        el.append(
            Paragraph(
                f"<b>[{tag.get(f['label'], f['label'])}]</b> {esc(f['text'])} "
                f"<font color='#6b7280'>({', '.join(f.get('evidence', []))}; {esc(f.get('period') or '')})"
                f"</font>",
                body,
            )
        )
    el.append(Paragraph(f"<font color='#047857'>✓ {esc(brief['guard']['badge'])}</font>", small))
    el.append(Paragraph("Three-year trend (foundational numeracy, comparable instruments)", h2))
    el.append(
        table(
            [
                ["Year", *[p["year"] for p in brief["trend"]]],
                ["Numeracy %", *[str(p["value"]) if p["value"] is not None else "n/c" for p in brief["trend"]]],
            ],
            [30 * mm] + [30 * mm] * len(brief["trend"]),
        )
    )
    if brief.get("concentration"):
        el.append(Paragraph("Where the change is concentrated (with reasons — not a ranking)", h2))
        rows = [["Unit", "Baseline", "Latest", "Change (pp)", "Reasons"]]
        for k in brief["concentration"]:
            rows.append(
                [
                    k["name"],
                    str(k["baseline"]),
                    str(k["latest"]),
                    str(k["change_pp"]),
                    Paragraph(esc("; ".join(k["reasons"]) or "—"), body),
                ]
            )
        el.append(table(rows, [28 * mm, 20 * mm, 20 * mm, 22 * mm, 88 * mm]))
    if brief.get("peers") and brief["peers"].get("summary"):
        el.append(Paragraph("Peer comparison (election-affected similar blocks)", h2))
        el.append(Paragraph(esc(brief["peers"]["summary"]["text"]), body))
        if brief["peers"]["summary"].get("interpretation"):
            el.append(Paragraph(esc(brief["peers"]["summary"]["interpretation"]), body))
    rdr = brief["radar"]
    el.append(Paragraph("Schools needing support (multiple indicators)", h2))
    el.append(
        Paragraph(
            f"{rdr['n_flagged']} of {rdr['n_schools']} schools show 2+ deteriorating indicators; "
            f"{rdr['n_priority']} show 3+.",
            body,
        )
    )
    if rdr["schools"]:
        rows = [["School", "Block", "Reasons"]] + [
            [Paragraph(esc(s["school_name"]), body), s["block"], Paragraph(esc("; ".join(s["reasons"])), body)]
            for s in rdr["schools"]
        ]
        el.append(table(rows, [60 * mm, 25 * mm, 93 * mm]))
    el.append(Paragraph("Actions and accountability", h2))
    s = brief["actions_summary"]
    el.append(
        Paragraph(
            f"{s['total']} actions · {s['overdue']} overdue · {s['awaiting_verification']} awaiting "
            f"verification · {s['implemented_improved']} implemented with improvement · "
            f"{s['not_implemented']} not implemented",
            body,
        )
    )
    if brief["actions"]:
        rows = [["Action", "Owner", "Due", "Status"]]
        for a in brief["actions"][:10]:
            rows.append(
                [
                    Paragraph(esc(a["title"] + (" (simulated)" if a["simulated"] else "")), body),
                    a["owner"],
                    a["due"],
                    a["outcome_status"].replace("_", " "),
                ]
            )
        el.append(table(rows, [85 * mm, 35 * mm, 22 * mm, 36 * mm]))
    el.append(Paragraph("Data limitations", h2))
    for w in brief["limitations"]:
        el.append(Paragraph(f"• {esc(w)}", small))
    el.append(Spacer(1, 6))
    el.append(
        Paragraph(
            "Findings are associations from observational data, not proof of cause. Generated by ShikshaPulse.", small
        )
    )
    doc.build(el)
    return buf.getvalue()
