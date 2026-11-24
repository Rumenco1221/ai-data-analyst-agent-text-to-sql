"""Capa semántica: carga las definiciones de negocio y compila preguntas simples a SQL de forma determinista.

- `SemanticLayer.describe()` produce el contexto que se le da al LLM (métricas, dimensiones y reglas).
- `SemanticLayer.compile(question)` resuelve sin IA preguntas del tipo métrica × dimensión × filtros × top N.
"""
from __future__ import annotations

import re
import sqlite3
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import yaml

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "semantic_layer.yaml"
MONTHS = {"enero": "01", "febrero": "02", "marzo": "03", "abril": "04", "mayo": "05", "junio": "06",
          "julio": "07", "agosto": "08", "septiembre": "09", "setiembre": "09", "octubre": "10",
          "noviembre": "11", "diciembre": "12"}


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text).lower()).encode("ascii", "ignore").decode()
    return re.sub(r"[^\w\s-]", " ", text)


def _mentions(question: str, phrase: str) -> bool:
    return re.search(rf"\b{re.escape(norm(phrase).strip())}\b", question) is not None


@dataclass
class CompiledQuery:
    sql: str
    metric: str
    dimension: str | None = None
    filters: list[str] = field(default_factory=list)


class NotAnswerableError(ValueError):
    """La pregunta pide algo que los datos no contienen: mejor decirlo que inventar."""


class SemanticLayer:
    def __init__(self, path: str | Path = DEFAULT_PATH):
        self.spec = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        self.metrics: dict = self.spec["metrics"]
        self.dimensions: dict = self.spec["dimensions"]
        self.values: dict[str, list[str]] = {}

    # ---------- contexto para el LLM ----------
    def describe(self) -> str:
        lines = ["Métricas oficiales (usá EXACTAMENTE esta fórmula):"]
        lines += [f"- {k}: {m['description']} SQL: {m['sql']}" for k, m in self.metrics.items()]
        lines.append(f"Tabla base: {self.spec['base_table']}. Joins: " + "; ".join(self.spec["joins"].values()))
        lines.append("Dimensiones: " + ", ".join(f"{k} = {d['sql']}" for k, d in self.dimensions.items()))
        lines += [f"Regla: {r}" for r in self.spec.get("business_rules", [])]
        return "\n".join(lines)

    # ---------- valores para filtros ("en CABA", "de Tecnología") ----------
    def bind(self, con: sqlite3.Connection) -> "SemanticLayer":
        base, joins = self.spec["base_table"], self.spec["joins"]
        for key, dim in self.dimensions.items():
            if dim.get("time"):
                continue
            sql = f"SELECT DISTINCT {dim['sql']} FROM {base} {joins[dim['join']]}"
            self.values[key] = [r[0] for r in con.execute(sql) if r[0] is not None]
        return self

    # ---------- compilador determinista ----------
    def _find_metric(self, q: str) -> str:
        scored = [(max(len(s) for s in m["synonyms"] if _mentions(q, s)), k)
                  for k, m in self.metrics.items() if any(_mentions(q, s) for s in m["synonyms"])]
        return max(scored)[1] if scored else "ingreso"

    def _find_dimension(self, q: str) -> str | None:
        hits = [(q.find(norm(s)), k) for k, d in self.dimensions.items() for s in d["synonyms"] if _mentions(q, s)]
        return min(hits)[1] if hits else None

    def _find_filters(self, q: str) -> tuple[list[str], set[str]]:
        where, joins = [], set()
        for key, values in self.values.items():
            for v in values:
                if _mentions(q, v):
                    dim = self.dimensions[key]
                    where.append(f"{dim['sql']} = '{str(v).replace(chr(39), chr(39) * 2)}'")
                    joins.add(dim["join"])
        col = self.spec["date_column"]
        for name, num in MONTHS.items():
            if _mentions(q, name):
                where.append(f"strftime('%m', {col}) = '{num}'")
        year = re.search(r"\b(20\d\d)\b", q)
        if year:
            where.append(f"strftime('%Y', {col}) = '{year.group(1)}'")
        return where, joins

    def compile(self, question: str) -> CompiledQuery:
        q = norm(question)
        for concept, reason in self.spec.get("unsupported", {}).items():
            if _mentions(q, concept):
                raise NotAnswerableError(f"No puedo responder eso con estos datos: {reason}")
        known = [s for m in self.metrics.values() for s in m["synonyms"]]
        known += [s for d in self.dimensions.values() for s in d["synonyms"]]
        known += [v for vals in self.values.values() for v in vals] + ["total", "cuanto", "cuantas", "cuantos"]
        if not any(_mentions(q, k) for k in known):
            raise NotAnswerableError("No reconozco ninguna métrica ni dimensión en la pregunta. "
                                     "Probá con: ingreso, unidades, ticket promedio, por región, por mes...")
        metric_key = self._find_metric(q)
        metric = self.metrics[metric_key]
        dim_key = self._find_dimension(q)
        where, joins = self._find_filters(q)

        select, group, order = [], "", ""
        if dim_key:
            dim = self.dimensions[dim_key]
            select.append(f"{dim['sql']} AS {dim_key}")
            if dim.get("join"):
                joins.add(dim["join"])
            group = f"GROUP BY {dim['sql']}"
            if dim.get("time"):
                order = f"ORDER BY {dim_key}"
            else:
                direction = "ASC" if re.search(r"\b(peor|peores|menos|menor|menores)\b", q) else "DESC"
                order = f"ORDER BY {metric_key} {direction}"
        select.append(f"{metric['sql']} AS {metric_key}")

        sql = f"SELECT {', '.join(select)} FROM {self.spec['base_table']}"
        for j in sorted(joins):
            sql += f" {self.spec['joins'][j]}"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += f" {group} {order}".rstrip()
        top = re.search(r"\b(?:top|mejores|primeros|primeras|peores)\s+(\d+)\b", q)
        if top and dim_key:
            sql += f" LIMIT {int(top.group(1))}"
        return CompiledQuery(sql=" ".join(sql.split()), metric=metric_key, dimension=dim_key, filters=where)
