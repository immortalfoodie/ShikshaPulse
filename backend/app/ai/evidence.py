"""Per-request evidence store. Every analytics result the AI sees gets a citable id (E1, E2, ...)."""
from __future__ import annotations

from typing import Any


class EvidenceStore:
    def __init__(self) -> None:
        self.items: dict[str, dict] = {}
        self._n = 0

    def add(self, kind: str, title: str, data: dict, period: str | None = None, ev_type: str = "observed_fact",
            source: list[str] | str | None = None, link: dict | None = None) -> str:
        self._n += 1
        eid = f"E{self._n}"
        self.items[eid] = {"id": eid, "kind": kind, "title": title, "type": ev_type, "period": period,
                           "data": data, "source": source, "link": link}
        return eid

    def numbers(self) -> set[float]:
        out: set[float] = set()

        def walk(x: Any) -> None:
            if isinstance(x, bool):
                return
            if isinstance(x, (int, float)):
                out.add(float(x))
            elif isinstance(x, dict):
                for v in x.values():
                    walk(v)
            elif isinstance(x, (list, tuple)):
                out.add(float(len(x)))
                for v in x:
                    walk(v)
            elif isinstance(x, str):
                import re
                for m in re.findall(r"(?<![\w.])-?\d+(?:\.\d+)?", x):
                    try:
                        out.add(float(m))
                    except ValueError:
                        pass

        for it in self.items.values():
            walk(it["data"])
            if it.get("title"):
                walk(it["title"])
        return out

    def of_type(self, ev_type: str) -> list[dict]:
        return [e for e in self.items.values() if e["type"] == ev_type]

    def public(self) -> list[dict]:
        return list(self.items.values())
