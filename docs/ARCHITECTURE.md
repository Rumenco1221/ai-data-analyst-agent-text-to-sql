# Arquitectura

## Componentes

| Archivo | Rol |
|---|---|
| `agent/llm.py` | Interfaz `LLMProvider` + implementaciones Anthropic, OpenAI y Offline. Patrón *Strategy*. |
| `agent/guardrails.py` | Política de seguridad del SQL. Función pura, 100% testeable. |
| `agent/core.py` | Bucle del agente: generar → validar → ejecutar → corregir → resumir → auditar. |
| `agent/__main__.py` | CLI. |
| `evals/` | Casos con SQL de referencia y ataques. Se ejecutan en CI. |

## Modelo de amenazas

| Riesgo | Mitigación |
|---|---|
| El modelo genera `DELETE` / `DROP` | Guardrails (solo lectura) **y** conexión `mode=ro` |
| Inyección de varias sentencias (`; DELETE`) | Rechazo de `;` intermedios |
| Acceso a tablas internas o sensibles | Lista blanca de tablas obtenida del esquema |
| Consultas que devuelven millones de filas | `LIMIT 200` automático |
| Respuestas inventadas | El resumen se genera **a partir de las filas reales**; evals con valores de referencia |
| Falta de trazabilidad | `audit_log.jsonl` con cada interacción |

## Por qué un proveedor offline

Permite correr tests y evaluaciones en GitHub Actions **sin claves ni costo**, y demostrar el proyecto a cualquier persona en segundos. En producción se usa Claude u OpenAI.
