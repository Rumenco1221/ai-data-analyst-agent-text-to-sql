"""Evaluación del agente: compara cada respuesta con el resultado de un SQL de referencia escrito a mano.

Uso:  python evals/run_evals.py [--provider anthropic|openai|offline]
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent import DataAnalystAgent  # noqa: E402
from agent.llm import get_provider  # noqa: E402
from data.build_demo_db import build  # noqa: E402


def first_value(rows):
    return round(float(list(rows[0].values())[-1] if isinstance(rows[0], dict) else rows[0][-1]), 2)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default=None)
    args = ap.parse_args()
    db = ROOT / "data" / "sales.db"
    if not db.exists():
        build(db)
    cases = json.loads((ROOT / "evals" / "cases.json").read_text(encoding="utf-8"))
    agent = DataAnalystAgent(db, provider=get_provider(args.provider), audit_log=None)
    con = sqlite3.connect(db)
    passed = 0
    for case in cases:
        expected = first_value(con.execute(case["reference_sql"]).fetchall())
        r = agent.ask(case["question"])
        got = first_value(r.rows) if r.ok and r.rows else None
        ok = got is not None and abs(got - expected) < 0.01
        passed += ok
        print(f"{'✅' if ok else '❌'} {case['question']:<55} esperado={expected:<14} obtenido={got}")
    blocked = 0
    for attack in json.loads((ROOT / "evals" / "attacks.json").read_text(encoding="utf-8")):
        from agent.guardrails import UnsafeSQLError, validate_sql
        try:
            validate_sql(attack, agent.tables)
        except UnsafeSQLError:
            blocked += 1
    print(f"\nPrecisión: {passed}/{len(cases)} · Ataques bloqueados por guardrails: {blocked}/{len(json.loads((ROOT / 'evals' / 'attacks.json').read_text()))}")
    return 0 if passed == len(cases) else 1


if __name__ == "__main__":
    raise SystemExit(main())
