import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent import DataAnalystAgent  # noqa: E402
from agent.insights import describe, recommend_chart  # noqa: E402
from agent.llm import AnthropicProvider  # noqa: E402
from agent.semantic import NotAnswerableError, SemanticLayer  # noqa: E402
from data.build_demo_db import build  # noqa: E402


@pytest.fixture(scope="module")
def db(tmp_path_factory):
    return build(tmp_path_factory.mktemp("db") / "sales.db")


@pytest.fixture(scope="module")
def layer(db):
    with sqlite3.connect(db) as con:
        return SemanticLayer().bind(con)


def test_metric_synonyms_resolve_to_official_formula(layer):
    for q in ("facturación por región", "ingresos por región", "ventas por región"):
        assert "SUM(f.quantity * f.unit_price)" in layer.compile(q).sql


def test_filters_from_real_values(layer):
    c = layer.compile("top 3 productos de Tecnología en CABA")
    assert "s.region = 'CABA'" in c.sql and "p.category = 'Tecnología'" in c.sql and c.sql.endswith("LIMIT 3")


def test_worst_inverts_order(layer):
    assert "ASC" in layer.compile("¿qué categoría vende menos?").sql


@pytest.mark.parametrize("q", ["margen por categoría", "¿cómo está el clima?"])
def test_abstains_when_data_does_not_exist(layer, q):
    with pytest.raises(NotAnswerableError):
        layer.compile(q)


def test_chart_recommendation():
    assert recommend_chart([{"mes": "2026-01", "v": 1.0}, {"mes": "2026-02", "v": 2.0}])["type"] == "line"
    assert recommend_chart([{"region": "A", "v": 1.0}, {"region": "B", "v": 3.0}])["type"] == "bar"
    assert recommend_chart([{"total": 5.0}])["type"] == "kpi"


def test_insights_use_real_numbers():
    rows = [{"region": "A", "v": 300.0}, {"region": "B", "v": 100.0}, {"region": "C", "v": 100.0}]
    text = " ".join(describe(rows, recommend_chart(rows)))
    assert "Lidera A" in text and "60%" in text


class FakeAnthropicClient:
    """Simula la API de Claude: permite testear el proveedor sin red ni costo."""

    def __init__(self, replies):
        self.replies, self.calls = list(replies), []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(content=[SimpleNamespace(text=self.replies.pop(0))])


def test_anthropic_provider_receives_semantic_layer_and_self_corrects(db):
    client = FakeAnthropicClient(["SELECT bad_column FROM sales",
                                  "```sql\nSELECT COUNT(*) AS n FROM sales\n```",
                                  "Hubo muchas ventas."])
    agent = DataAnalystAgent(db, provider=AnthropicProvider(model="test", client=client), audit_log=None)
    r = agent.ask("¿cuántas ventas hubo?")
    assert r.ok and r.attempts == 2 and r.answer == "Hubo muchas ventas."
    assert "Métricas oficiales" in client.calls[0]["messages"][0]["content"]
    assert "no such column" in client.calls[1]["messages"][0]["content"]


def test_llm_can_abstain(db):
    client = FakeAnthropicClient(["NO_ANSWER: la base no tiene costos"])
    r = DataAnalystAgent(db, provider=AnthropicProvider(model="t", client=client), audit_log=None).ask("margen")
    assert not r.ok and "costos" in r.error
