"""Guardrails: el agente nunca ejecuta SQL que no haya pasado estas validaciones."""
from __future__ import annotations

import re
import sqlite3

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


def cte_names(sql: str) -> set[str]:
    """Nombres de las CTE definidas en la consulta (incluye la forma con columnas: n(x) AS (...))."""
    return {m.lower() for m in re.findall(r"(\w+)\s*(?:\([^()]*\))?\s+as\s*\(", sql, re.IGNORECASE)}


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

    ctes = cte_names(clean)
    referenced = {t.lower() for t in re.findall(r"\b(?:from|join)\s+([A-Za-z_][\w]*)", clean, re.IGNORECASE)}
    unknown = referenced - {t.lower() for t in allowed_tables} - ctes
    if unknown:
        raise UnsafeSQLError(f"Tablas no permitidas o inexistentes: {sorted(unknown)}.")

    if not re.search(r"\blimit\s+\d+\s*$", clean, re.IGNORECASE):
        clean = f"{clean}\nLIMIT {MAX_ROWS}"
    return clean


def make_authorizer(allowed_tables: set[str], cte_aliases: set[str] = frozenset()):
    """Autorizador de SQLite: el MOTOR rechaza cualquier operación que no sea leer tablas permitidas.

    Es la tercera capa de defensa (después de las reglas de texto y de la conexión de solo lectura):
    aunque una consulta maliciosa engañara al validador de texto, SQLite se niega a ejecutarla.
    """
    allowed = {t.lower() for t in allowed_tables} | {c.lower() for c in cte_aliases}
    read_only_actions = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_RECURSIVE}

    def authorizer(action, arg1, arg2, db_name, source):
        if action in read_only_actions:
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_READ:
            return sqlite3.SQLITE_OK if (arg1 or "").lower() in allowed else sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_DENY

    return authorizer
