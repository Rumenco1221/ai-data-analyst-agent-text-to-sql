"""Proveedores de LLM intercambiables.

- AnthropicProvider: usa la API de Claude (requiere `pip install anthropic` y ANTHROPIC_API_KEY).
- OpenAIProvider: usa la API de OpenAI (requiere `pip install openai` y OPENAI_API_KEY).
- OfflineProvider: plantillas por palabras clave; permite probar el agente sin claves ni costo.
"""
from __future__ import annotations

import os
import re
import unicodedata
from typing import Protocol

SYSTEM_PROMPT = """Sos un analista de datos senior. Convertís preguntas de negocio en UNA consulta SQLite de solo lectura.
Reglas: usá solo las tablas y columnas del esquema; devolvé únicamente el SQL, sin explicación ni ```;
usá alias legibles; redondeá importes a 2 decimales; ordená los resultados de forma útil."""


class LLMProvider(Protocol):
    name: str

    def generate_sql(self, question: str, schema: str, feedback: str | None = None) -> str: ...

    def summarize(self, question: str, sql: str, rows: list[dict]) -> str: ...


def _user_prompt(question: str, schema: str, feedback: str | None) -> str:
    msg = f"Esquema:\n{schema}\n\nPregunta: {question}"
    if feedback:
        msg += f"\n\nTu intento anterior falló con este error, corregilo:\n{feedback}"
    return msg


def _summary_prompt(question: str, sql: str, rows: list[dict]) -> str:
    return (f"Pregunta: {question}\nSQL: {sql}\nResultado (primeras filas): {rows[:20]}\n"
            "Respondé en 2-3 frases en español, con los números clave y una recomendación de negocio.")


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, model: str | None = None):
        import anthropic  # import diferido: solo si se usa
        self.client = anthropic.Anthropic()
        self.model = model or os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")

    def _ask(self, system: str, user: str) -> str:
        msg = self.client.messages.create(model=self.model, max_tokens=800, system=system,
                                          messages=[{"role": "user", "content": user}])
        return msg.content[0].text.strip()

    def generate_sql(self, question, schema, feedback=None):
        return self._ask(SYSTEM_PROMPT, _user_prompt(question, schema, feedback))

    def summarize(self, question, sql, rows):
        return self._ask("Sos un analista de negocio claro y conciso.", _summary_prompt(question, sql, rows))


class OpenAIProvider:
    name = "openai"

    def __init__(self, model: str | None = None):
        from openai import OpenAI
        self.client = OpenAI()
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    def _ask(self, system: str, user: str) -> str:
        r = self.client.chat.completions.create(model=self.model, messages=[
            {"role": "system", "content": system}, {"role": "user", "content": user}])
        return r.choices[0].message.content.strip()

    def generate_sql(self, question, schema, feedback=None):
        return self._ask(SYSTEM_PROMPT, _user_prompt(question, schema, feedback))

    def summarize(self, question, sql, rows):
        return self._ask("Sos un analista de negocio claro y conciso.", _summary_prompt(question, sql, rows))


def _norm(text: str) -> str:
    return unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode()


class OfflineProvider:
    """Motor determinista por intención. No reemplaza a un LLM: sirve para demos, tests y CI sin costo."""
    name = "offline"

    INTENTS: list[tuple[str, str]] = [
        (r"(?=.*(ingreso|venta|factur|vende))(?=.*region)",
         "SELECT s.region, ROUND(SUM(f.quantity * f.unit_price), 2) AS revenue FROM sales f "
         "JOIN stores s ON s.store_id = f.store_id GROUP BY s.region ORDER BY revenue DESC"),
        (r"(?=.*(top|mejores|mas vendid))(?=.*producto)",
         "SELECT p.product_name, SUM(f.quantity) AS units, ROUND(SUM(f.quantity * f.unit_price), 2) AS revenue "
         "FROM sales f JOIN products p ON p.product_id = f.product_id GROUP BY p.product_name "
         "ORDER BY revenue DESC LIMIT 5"),
        (r"\b(mes|meses|mensual|evolucion|tendencia)\b",
         "SELECT strftime('%Y-%m', f.sale_date) AS month, ROUND(SUM(f.quantity * f.unit_price), 2) AS revenue "
         "FROM sales f GROUP BY month ORDER BY month"),
        (r"(categoria)",
         "SELECT p.category, ROUND(SUM(f.quantity * f.unit_price), 2) AS revenue FROM sales f "
         "JOIN products p ON p.product_id = f.product_id GROUP BY p.category ORDER BY revenue DESC"),
        (r"(ticket|promedio)",
         "SELECT ROUND(SUM(quantity * unit_price) * 1.0 / COUNT(*), 2) AS avg_ticket FROM sales"),
        (r"(tienda|sucursal)",
         "SELECT s.store_name, ROUND(SUM(f.quantity * f.unit_price), 2) AS revenue FROM sales f "
         "JOIN stores s ON s.store_id = f.store_id GROUP BY s.store_name ORDER BY revenue DESC"),
        (r"(total|cuanto vendimos|ingreso total)",
         "SELECT ROUND(SUM(quantity * unit_price), 2) AS total_revenue FROM sales"),
    ]

    def generate_sql(self, question, schema, feedback=None):
        q = _norm(question)
        for pattern, sql in self.INTENTS:
            if re.search(pattern, q):
                return sql
        raise ValueError("El modo offline no reconoce esta pregunta. Configurá ANTHROPIC_API_KEY u OPENAI_API_KEY.")

    def summarize(self, question, sql, rows):
        if not rows:
            return "La consulta no devolvió resultados."
        first = rows[0]
        parts = ", ".join(f"{k} = {v:,.2f}" if isinstance(v, float) else f"{k} = {v}" for k, v in first.items())
        extra = f" (y {len(rows) - 1} filas más)" if len(rows) > 1 else ""
        return f"Resultado principal: {parts}{extra}."


def get_provider(name: str | None = None) -> LLMProvider:
    name = (name or os.getenv("LLM_PROVIDER") or "").lower()
    if name == "anthropic" or (not name and os.getenv("ANTHROPIC_API_KEY")):
        return AnthropicProvider()
    if name == "openai" or (not name and os.getenv("OPENAI_API_KEY")):
        return OpenAIProvider()
    return OfflineProvider()
