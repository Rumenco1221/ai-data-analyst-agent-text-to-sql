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
    questions = json.loads((ROOT / "evals" / "abstentions.json").read_text(encoding="utf-8"))
    abstained = 0
    for q in questions:
        r = agent.ask(q)
        abstained += not r.ok
        print(f"{'✅' if not r.ok else '❌'} (debe abstenerse) {q:<38} → {r.error or 'respondió'}")
    report = {"accuracy": f"{passed}/{len(cases)}", "abstention": f"{abstained}/{len(questions)}",
              "attacks_blocked": blocked, "provider": agent.provider.name}
    (ROOT / "evals" / "last_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nAbstención correcta: {abstained}/{len(questions)}")
    print(f"Precisión: {passed}/{len(cases)} · Ataques bloqueados por guardrails: {blocked}/{len(json.loads((ROOT / 'evals' / 'attacks.json').read_text()))}")
    return 0 if passed == len(cases) and abstained == len(questions) else 1


if __name__ == "__main__":
    raise SystemExit(main())
