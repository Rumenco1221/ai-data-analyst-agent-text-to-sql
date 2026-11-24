"""CLI interactiva:  python -m agent --db data/sales.db  [--provider anthropic|openai|offline]"""
import argparse

from .core import DataAnalystAgent
from .llm import get_provider


def main() -> None:
    ap = argparse.ArgumentParser(description="Preguntale a tus datos en lenguaje natural.")
    ap.add_argument("--db", default="data/sales.db")
    ap.add_argument("--provider", default=None)
    ap.add_argument("-q", "--question", help="Pregunta única (modo no interactivo)")
    args = ap.parse_args()
    agent = DataAnalystAgent(args.db, provider=get_provider(args.provider))
    print(f"🤖 Agente listo · proveedor: {agent.provider.name} · tablas: {', '.join(sorted(agent.tables))}")

    questions = [args.question] if args.question else iter(lambda: input("\n❓ Pregunta (enter para salir): "), "")
    for q in questions:
        r = agent.ask(q)
        if r.ok:
            print(f"\n🧾 SQL ({r.attempts} intento/s, {r.latency_ms} ms):\n{r.sql}\n")
            for row in r.rows[:10]:
                print("   ", row)
            print(f"\n💬 {r.answer}")
        else:
            print(f"\n⚠️  No pude responder: {r.error}")


if __name__ == "__main__":
    main()
