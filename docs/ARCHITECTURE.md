# Arquitectura

## Componentes

| Archivo | Rol |
|---|---|
| `agent/llm.py` | Interfaz `LLMProvider` + implementaciones Anthropic, OpenAI y Offline. Patrón *Strategy*. |
| `agent/guardrails.py` | Política de seguridad del SQL. Función pura, 100% testeable. |
| `agent/semantic.py` | Carga `semantic_layer.yaml`, describe las métricas al LLM y compila preguntas simples sin IA. |
| `agent/insights.py` | Recomienda gráfico y redacta hallazgos a partir de las filas. |
| `agent/web.py` | Servidor web stdlib + `static/index.html`. |
| `agent/core.py` | Bucle del agente: generar → validar → ejecutar → corregir → resumir → auditar. |
| `agent/__main__.py` | CLI. |
| `evals/` | Casos con SQL de referencia y ataques. Se ejecutan en CI. |

## Modelo de amenazas

| Riesgo | Mitigación |
|---|---|
| El modelo genera `DELETE` / `DROP` | Guardrails (solo lectura), conexión `mode=ro` **y** autorizador del motor |
| Tablas en `FROM a, b` que el validador de texto no ve | El autorizador del motor solo permite leer tablas de la lista blanca |
| Consulta descontrolada (producto cartesiano, recursión) | `set_progress_handler` corta tras `timeout_s` |
| Pregunta sobre datos inexistentes | Abstención por capa semántica y por instrucción `NO_ANSWER` al LLM |
| Inyección de varias sentencias (`; DELETE`) | Rechazo de `;` intermedios |
| Acceso a tablas internas o sensibles | Lista blanca de tablas obtenida del esquema |
| Consultas que devuelven millones de filas | `LIMIT 200` automático |
| Respuestas inventadas | El resumen se genera **a partir de las filas reales**; evals con valores de referencia |
| Falta de trazabilidad | `audit_log.jsonl` con cada interacción |

## Por qué un proveedor offline

Permite correr tests y evaluaciones en GitHub Actions **sin claves ni costo**, y demostrar el proyecto a cualquier persona en segundos. En producción se usa Claude u OpenAI.
