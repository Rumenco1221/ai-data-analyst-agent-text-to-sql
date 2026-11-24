"""Guardrails: el agente nunca ejecuta SQL que no haya pasado estas validaciones."""
from __future__ import annotations

import re

FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|replace|truncate|attach|detach|pragma|vacuum|reindex|grant|exec)\b",
    re.IGNORECASE,
)
MAX_ROWS = 200


class UnsafeSQLError(ValueError):
    """La consulta generada viola una política de seguridad."""


def _strip_comments(sql: str) -> str:
    sql = re.sub(r"--[^\n]*", " ", sql)
    return re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)


def validate_sql(sql: str, allowed_tables: set[str]) -> str:
    """Devuelve el SQL normalizado (con LIMIT) o lanza UnsafeSQLError explicando el motivo."""
    clean = _strip_comments(sql).strip().rstrip(";").strip()
    if not clean:
        raise UnsafeSQLError("Consulta vacía.")
    if ";" in clean:
        raise UnsafeSQLError("Solo se permite una sentencia por consulta.")
    if not re.match(r"^(select|with)\b", clean, re.IGNORECASE):
        raise UnsafeSQLError("Solo se permiten consultas de lectura (SELECT / WITH).")
    if FORBIDDEN.search(clean):
        raise UnsafeSQLError(f"Palabra clave no permitida: '{FORBIDDEN.search(clean).group(0)}'.")

    cte_names = {m.lower() for m in re.findall(r"(\w+)\s+as\s*\(", clean, re.IGNORECASE)}
    referenced = {t.lower() for t in re.findall(r"\b(?:from|join)\s+([A-Za-z_][\w]*)", clean, re.IGNORECASE)}
    unknown = referenced - {t.lower() for t in allowed_tables} - cte_names
    if unknown:
        raise UnsafeSQLError(f"Tablas no permitidas o inexistentes: {sorted(unknown)}.")

    if not re.search(r"\blimit\s+\d+\s*$", clean, re.IGNORECASE):
        clean = f"{clean}\nLIMIT {MAX_ROWS}"
    return clean
