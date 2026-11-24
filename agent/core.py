"""Bucle del agente: pensar (generar SQL) → validar → ejecutar → autocorregir → explicar → auditar."""
from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .guardrails import UnsafeSQLError, cte_names, make_authorizer, validate_sql
from .llm import LLMProvider, get_provider


@dataclass
class AgentResult:
    question: str
    sql: str | None = None
    rows: list[dict] = field(default_factory=list)
    answer: str = ""
    attempts: int = 0
    ok: bool = False
    error: str | None = None
    provider: str = ""
    latency_ms: int = 0


class DataAnalystAgent:
    def __init__(self, db_path: str | Path, provider: LLMProvider | None = None,
                 max_attempts: int = 3, audit_log: str | Path | None = "audit_log.jsonl",
                 timeout_s: float = 5.0):
        self.db_path = Path(db_path)
        self.provider = provider or get_provider()
        self.max_attempts = max_attempts
        self.timeout_s = timeout_s
        self.audit_log = Path(audit_log) if audit_log else None
        self.tables, self.schema = self._introspect()

    def _connect(self) -> sqlite3.Connection:
        # Conexión de SOLO LECTURA a nivel motor: segunda línea de defensa además de los guardrails.
        con = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        return con

    def _query_connection(self, sql: str) -> sqlite3.Connection:
        """Conexión para ejecutar SQL generado por la IA: solo lectura + autorizador + tiempo límite."""
        con = self._connect()
        con.set_authorizer(make_authorizer(self.tables, cte_names(sql)))
        deadline = time.perf_counter() + self.timeout_s
        con.set_progress_handler(lambda: 1 if time.perf_counter() > deadline else 0, 10_000)
        return con

    def _introspect(self) -> tuple[set[str], str]:
        with self._connect() as con:
            tables = [r[0] for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%'")]
            lines = []
            for t in tables:
                cols = ", ".join(f"{c[1]} {c[2]}" for c in con.execute(f"PRAGMA table_info({t})"))
                lines.append(f"{t}({cols})")
        return set(tables), "\n".join(lines)

    def ask(self, question: str) -> AgentResult:
        start = time.perf_counter()
        result = AgentResult(question=question, provider=self.provider.name)
        feedback = None
        for attempt in range(1, self.max_attempts + 1):
            result.attempts = attempt
            try:
                raw_sql = self.provider.generate_sql(question, self.schema, feedback)
                result.sql = validate_sql(raw_sql, self.tables)
                with self._query_connection(result.sql) as con:
                    result.rows = [dict(r) for r in con.execute(result.sql).fetchall()]
                result.answer = self.provider.summarize(question, result.sql, result.rows)
                result.ok, result.error = True, None
                break
            except (UnsafeSQLError, sqlite3.Error) as exc:
                result.error = f"{type(exc).__name__}: {exc}"
                feedback = result.error  # el agente recibe el error y reintenta
            except ValueError as exc:
                result.error = str(exc)
                break
        result.latency_ms = int((time.perf_counter() - start) * 1000)
        self._audit(result)
        return result

    def _audit(self, result: AgentResult) -> None:
        if not self.audit_log:
            return
        record = asdict(result) | {"rows": len(result.rows), "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
        with self.audit_log.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
