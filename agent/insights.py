"""Del resultado a la decisión: recomienda un gráfico y redacta hallazgos a partir de las filas reales.

Todo número del texto sale de las filas: nada se inventa.
"""
from __future__ import annotations

import re

TIME_RE = re.compile(r"^\d{4}-\d{2}(-\d{2})?$")


def _fmt(v: float) -> str:
    """Formato es-AR: 1.234.567,89 (enteros sin decimales)."""
    text = f"{v:,.0f}" if float(v).is_integer() else f"{v:,.2f}"
    return text.replace(",", "X").replace(".", ",").replace("X", ".")


def _pct(v: float, signed: bool = False) -> str:
    return (f"{v:+.1%}" if signed else f"{v:.0%}").replace(".", ",")


def recommend_chart(rows: list[dict]) -> dict:
    if not rows:
        return {"type": "none"}
    cols = list(rows[0])
    numeric = [c for c in cols if all(isinstance(r[c], (int, float)) for r in rows)]
    labels = [c for c in cols if c not in numeric]
    if len(rows) == 1 and len(cols) == 1:
        return {"type": "kpi", "y": cols[0]}
    if not labels or not numeric:
        return {"type": "table"}
    x, y = labels[0], numeric[-1]
    if all(TIME_RE.match(str(r[x])) for r in rows):
        return {"type": "line", "x": x, "y": y}
    return {"type": "bar", "x": x, "y": y}


def describe(rows: list[dict], chart: dict) -> list[str]:
    if not rows:
        return ["La consulta no devolvió resultados."]
    kind = chart["type"]
    if kind == "kpi":
        return [f"{chart['y'].replace('_', ' ').capitalize()}: {_fmt(rows[0][chart['y']])}."]
    if kind not in ("bar", "line"):
        return [f"Se obtuvieron {len(rows)} filas."]
    x, y = chart["x"], chart["y"]
    values = [r[y] for r in rows]
    total = sum(values)
    out = []
    if kind == "bar":
        top = max(rows, key=lambda r: r[y])
        bottom = min(rows, key=lambda r: r[y])
        share = top[y] / total if total else 0
        ascending = len(rows) > 1 and rows[0][y] < rows[-1][y]
        if ascending:  # la pregunta pidió "menos / peor": responder primero por el más bajo
            out.append(f"El más bajo es {bottom[x]} con {_fmt(bottom[y])} ({_pct(bottom[y] / total)} del total mostrado).")
        out.append(f"Lidera {top[x]} con {_fmt(top[y])} ({_pct(share)} del total mostrado).")
        if len(rows) >= 3 and not ascending and bottom[y]:
            ratio = f"{top[y] / bottom[y]:.1f}".replace(".", ",")
            out.append(f"El último es {bottom[x]} con {_fmt(bottom[y])}; el líder lo supera {ratio} veces.")
        if share >= 0.5 and len(rows) > 2:
            out.append("Alta concentración: conviene reducir la dependencia del líder.")
    else:
        first, last = rows[0], rows[-1]
        change = (last[y] - first[y]) / first[y] if first[y] else 0
        best = max(rows, key=lambda r: r[y])
        out.append(f"De {first[x]} a {last[x]} la variación es {_pct(change, True)}.")
        out.append(f"El mejor período fue {best[x]} con {_fmt(best[y])}.")
        if len(rows) >= 2:
            prev = rows[-2][y]
            if prev:
                out.append(f"Último período vs. anterior: {_pct((last[y] - prev) / prev, True)}.")
    return [s for s in out if s]
