# Changelog

## [1.1.0] - 2026-11-23
### Added
- Capa semántica (`semantic_layer.yaml`): métricas oficiales, sinónimos, dimensiones, reglas de negocio.
- Compilador semántico para el modo offline: métrica × dimensión × filtros × top/peores N.
- Abstención: el agente responde "no lo sé" ante conceptos que la base no tiene (también el LLM vía `NO_ANSWER`).
- Autorizador del motor SQLite (tercera capa de defensa) y tiempo límite por consulta.
- Recomendación de gráfico e insights calculados desde las filas reales.
- Interfaz web sin dependencias (`python -m agent.web`).
- 8 casos de evaluación nuevos (15 en total) y 5 de abstención.
- Tests del proveedor Claude con cliente simulado (sin red ni costo).
### Fixed
- El validador no reconocía CTE con lista de columnas (`n(x) AS (...)`).

## [1.0.0] - 2026-11-23
### Added
- Proveedores Claude, OpenAI y offline
- Guardrails de solo lectura
- Bucle de autocorrección
- Registro de auditoría
- Evaluaciones y CI
