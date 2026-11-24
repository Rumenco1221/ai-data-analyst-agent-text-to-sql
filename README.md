<div align="center">

# 🧠 AI Data Analyst Agent — Text-to-SQL con Guardrails

**Preguntale a tu base de datos en español. El agente escribe el SQL, lo valida, lo ejecuta en modo solo lectura, se autocorrige y te explica el resultado.**

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Claude](https://img.shields.io/badge/LLM-Claude_|_OpenAI_|_Offline-8B5CF6?style=for-the-badge)
![Guardrails](https://img.shields.io/badge/guardrails-9%2F9_attacks_blocked-16a34a?style=for-the-badge)
![Evals](https://img.shields.io/badge/evals-7%2F7-16a34a?style=for-the-badge)
![License](https://img.shields.io/badge/license-MIT-gray?style=for-the-badge)

</div>

---

## 🎯 Problema que resuelve

Los equipos de negocio dependen del analista para cada pregunta ("¿qué región vendió más?"). Los chatbots de IA prometen resolverlo, pero en producción aparecen tres miedos legítimos: **¿y si el modelo borra datos?, ¿y si inventa números?, ¿cómo sé qué hizo?** En 2026 la conversación ya no es si los agentes son capaces, sino si se pueden **probar, auditar y controlar**.

## 💡 Solución

Un agente de análisis de datos con arquitectura de producción:

| Capacidad | Cómo se implementa |
|---|---|
| 🗣️ Lenguaje natural → SQL | Proveedor de LLM intercambiable: **Claude**, OpenAI u **offline** (sin costo, para demos y CI) |
| 🛡️ Guardrails | Solo `SELECT`/`WITH`, una sentencia, lista blanca de tablas, palabras clave prohibidas, `LIMIT` automático |
| 🔒 Defensa en profundidad | Conexión a la base en modo **solo lectura** a nivel motor |
| 🔁 Autocorrección | Si el SQL falla, el error vuelve al modelo y reintenta (hasta 3 veces) |
| 💬 Explicación | Resumen de negocio de 2-3 frases con los números clave |
| 🧾 Auditoría | Cada pregunta queda registrada en `audit_log.jsonl` (SQL, intentos, latencia, éxito) |
| 🧪 Evaluación | Set de preguntas con SQL de referencia + set de ataques; corre en GitHub Actions |

## 🛠️ Tecnologías usadas

`Python 3.10+` · `SQLite` · `Anthropic API (Claude)` · `OpenAI API` · `pytest` · `GitHub Actions`

## ✅ Beneficios

- 🙋 Autonomía para el negocio sin abrir la base de datos a riesgos.
- 📏 Calidad medible: precisión y bloqueo de ataques visibles en cada *push*.
- 🔌 Sin lock-in: cambiar de proveedor de IA es cambiar una variable de entorno.

## 📸 Capturas

```
🤖 Agente listo · proveedor: offline · tablas: products, sales, stores

🧾 SQL (1 intento/s, 1 ms):
SELECT s.region, ROUND(SUM(f.quantity * f.unit_price), 2) AS revenue FROM sales f
JOIN stores s ON s.store_id = f.store_id GROUP BY s.region ORDER BY revenue DESC
LIMIT 200

    {'region': 'CABA', 'revenue': 650719.73}
    {'region': 'Cuyo', 'revenue': 318524.43}

💬 Resultado principal: region = CABA, revenue = 650,719.73 (y 3 filas más).
```

```
$ python evals/run_evals.py
✅ ¿Cuál es el ingreso total?        esperado=1589749.06  obtenido=1589749.06
✅ ¿Qué región tiene más ventas?     esperado=650719.73   obtenido=650719.73
...
Precisión: 7/7 · Ataques bloqueados por guardrails: 9/9
```

## ⚙️ Instalación

```bash
git clone https://github.com/estela-oviedo/ai-data-analyst-agent-text-to-sql.git
cd ai-data-analyst-agent-text-to-sql
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install anthropic            # opcional: para usar Claude
cp .env.example .env             # y completá tu clave (nunca la subas a GitHub)
```

## ▶️ Uso

```bash
python data/build_demo_db.py                       # base de demo
python -m agent                                    # modo interactivo
python -m agent -q "Top 5 productos más vendidos"  # una pregunta
python -m agent --provider anthropic               # forzar Claude
python evals/run_evals.py                          # evaluar precisión y seguridad
pytest -q
```

Con tu propia base SQLite: `python -m agent --db ruta/a/tu_base.db`. El agente lee el esquema automáticamente.

## 🏗️ Arquitectura

```
Pregunta ──► LLM Provider ──► SQL ──► Guardrails ──✖──► error → feedback → reintento
                                         │ ✔
                                         ▼
                             SQLite (mode=ro) ──► filas ──► LLM: resumen de negocio
                                                              │
                                                              ▼
                                               Respuesta + audit_log.jsonl
```

Detalle en [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## 🗺️ Roadmap

- [x] Núcleo del agente, guardrails, autocorrección, auditoría, evals
- [ ] Conector PostgreSQL / SQL Server (usuario de solo lectura)
- [ ] Servidor MCP para usarlo desde Claude y otros asistentes
- [ ] Interfaz web con gráficos automáticos
- [ ] Capa semántica (definiciones de métricas) para reducir ambigüedad

## 🤝 Contribuciones

Toda contribución debe sumar un caso a `evals/cases.json` o `evals/attacks.json`. Si no se puede medir, no se mergea.

## 📬 Contacto

**Estela Oviedo** — IA aplicada · Data Analytics · Automatización
[LinkedIn](https://www.linkedin.com/in/estela-oviedo) · [GitHub](https://github.com/estela-oviedo)

---
<sub>Licencia MIT · Datos de demo sintéticos.</sub>
