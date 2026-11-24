"""Proveedores de LLM intercambiables.

- AnthropicProvider: usa la API de Claude (requiere `pip install anthropic` y ANTHROPIC_API_KEY).
- OpenAIProvider: usa la API de OpenAI (requiere `pip install openai` y OPENAI_API_KEY).
- OfflineProvider: plantillas por palabras clave; permite probar el agente sin claves ni costo.
"""
from __future__ import annotations

import os
from typing import Protocol

SYSTEM_PROMPT = """Sos un analista de datos senior. Convertís preguntas de negocio en UNA consulta SQLite de solo lectura.
Reglas: usá solo las tablas y columnas del esquema; devolvé únicamente el SQL, sin explicación ni ```;
usá alias legibles; redondeá importes a 2 decimales; ordená los resultados de forma útil.
Usá SIEMPRE las fórmulas de las métricas oficiales de la capa semántica.
Si la pregunta pide datos que el esquema no tiene, respondé solo: NO_ANSWER: <motivo breve>. Nunca inventes."""


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

    def __init__(self, model: str | None = None, client=None):
        if client is None:
            import anthropic  # import diferido: solo si se usa
            client = anthropic.Anthropic()
        self.client = client
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


class OfflineProvider:
    """Modo sin IA: compila la pregunta con la capa semántica (métrica × dimensión × filtros × top N).

    No reemplaza a un LLM para preguntas complejas, pero responde gratis, al instante y de forma
    reproducible las preguntas frecuentes. Ideal para demos, tests y CI.
    """
    name = "offline"

    def __init__(self, semantic=None):
        self.semantic = semantic

    def use_semantic_layer(self, semantic) -> None:
        self.semantic = semantic

    def generate_sql(self, question, schema, feedback=None):
        if self.semantic is None:
            raise ValueError("El modo offline necesita la capa semántica (semantic_layer.yaml).")
        return self.semantic.compile(question).sql

    def summarize(self, question, sql, rows):
        from .insights import describe, recommend_chart
        return " ".join(describe(rows, recommend_chart(rows)))


def get_provider(name: str | None = None) -> LLMProvider:
    name = (name or os.getenv("LLM_PROVIDER") or "").lower()
    if name == "anthropic" or (not name and os.getenv("ANTHROPIC_API_KEY")):
        return AnthropicProvider()
    if name == "openai" or (not name and os.getenv("OPENAI_API_KEY")):
        return OpenAIProvider()
    return OfflineProvider()
