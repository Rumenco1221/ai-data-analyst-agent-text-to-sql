import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent import DataAnalystAgent  # noqa: E402
from agent.guardrails import UnsafeSQLError, validate_sql  # noqa: E402
from agent.llm import OfflineProvider  # noqa: E402
from data.build_demo_db import build  # noqa: E402

TABLES = {"sales", "stores", "products"}


@pytest.fixture(scope="module")
def agent(tmp_path_factory):
    db = build(tmp_path_factory.mktemp("db") / "sales.db")
    return DataAnalystAgent(db, provider=OfflineProvider(), audit_log=None)


@pytest.mark.parametrize("attack", json.loads((ROOT / "evals" / "attacks.json").read_text(encoding="utf-8")))
def test_guardrails_block_attacks(attack):
    with pytest.raises(UnsafeSQLError):
        validate_sql(attack, TABLES)


def test_guardrails_add_limit():
    assert validate_sql("SELECT * FROM sales", TABLES).endswith("LIMIT 200")


def test_guardrails_allow_ctes():
    sql = "WITH t AS (SELECT * FROM sales) SELECT COUNT(*) FROM t"
    assert validate_sql(sql, TABLES).startswith("WITH")


def test_agent_answers_known_question(agent):
    r = agent.ask("¿Qué región tiene más ventas?")
    assert r.ok and r.rows and "region" in r.rows[0]


def test_agent_self_corrects_after_error(tmp_path):
    class FlakyProvider(OfflineProvider):
        calls = 0

        def generate_sql(self, question, schema, feedback=None):
            FlakyProvider.calls += 1
            return "SELECT nonexistent_col FROM sales" if feedback is None else "SELECT COUNT(*) AS n FROM sales"

    db = build(tmp_path / "s.db")
    r = DataAnalystAgent(db, provider=FlakyProvider(), audit_log=None).ask("¿cuántas ventas?")
    assert r.ok and r.attempts == 2


def test_audit_log_written(tmp_path):
    db = build(tmp_path / "s.db")
    log = tmp_path / "audit.jsonl"
    DataAnalystAgent(db, provider=OfflineProvider(), audit_log=log).ask("ingreso total")
    assert json.loads(log.read_text(encoding="utf-8").splitlines()[0])["ok"] is True


def test_authorizer_denies_what_text_rules_might_miss(tmp_path):
    """Aunque el validador de texto se saltee, el motor bloquea lecturas de tablas no permitidas."""
    import sqlite3
    from agent.guardrails import make_authorizer
    db = build(tmp_path / "s.db")
    con = sqlite3.connect(db)
    con.set_authorizer(make_authorizer({"sales"}))
    assert con.execute("SELECT COUNT(*) FROM sales").fetchone()[0] > 0
    for sql in ("SELECT * FROM stores", "SELECT name FROM sqlite_master", "DELETE FROM sales"):
        with pytest.raises(sqlite3.DatabaseError):
            con.execute(sql)


def test_runaway_query_is_interrupted(tmp_path):
    class SlowProvider(OfflineProvider):
        def generate_sql(self, question, schema, feedback=None):
            return ("WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM n) "
                    "SELECT COUNT(*) FROM n, sales")

    db = build(tmp_path / "s.db")
    r = DataAnalystAgent(db, provider=SlowProvider(), audit_log=None, timeout_s=0.3, max_attempts=1).ask("x")
    assert not r.ok and "interrupted" in r.error.lower()
