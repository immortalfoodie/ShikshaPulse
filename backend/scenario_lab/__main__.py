"""CLI: python -m scenario_lab generate <scenario> [--seed N] [--missing 0.1] ... | list"""
import argparse
import json

from . import OUT_ROOT
from .generator import generate, list_scenarios


def main() -> None:
    ap = argparse.ArgumentParser(prog="scenario_lab")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    g = sub.add_parser("generate")
    g.add_argument("scenario")
    g.add_argument("--seed", type=int)
    g.add_argument("--missing", type=float, help="missing_months_pct override")
    g.add_argument("--duplicates", type=float, help="duplicate_pct override")
    g.add_argument("--variants", type=float, help="name_variant_pct override")
    g.add_argument("--name", help="output scenario name override")
    a = ap.parse_args()
    if a.cmd == "list":
        print(json.dumps(list_scenarios(), indent=2))
        return
    mess = {k: v for k, v in {"missing_months_pct": a.missing, "duplicate_pct": a.duplicates,
                              "name_variant_pct": a.variants}.items() if v is not None}
    print(json.dumps(generate(a.scenario, OUT_ROOT, {"seed": a.seed, "mess": mess, "name": a.name}), indent=2))


if __name__ == "__main__":
    main()
