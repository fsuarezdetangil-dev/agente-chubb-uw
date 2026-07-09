# LangSmith — archivado (tracing migrado a Phoenix Arize)

La capa de **observabilidad y tracing** del agente fue migrada a Phoenix Arize el 2026-07-06.
`setup_langsmith.py` se conserva como referencia pero ya no se ejecuta en el arranque normal.

## Qué sigue usando LangSmith

El **harness de evaluación** sigue usando LangSmith para almacenar datasets y resultados:

- `scripts/run_langsmith_eval.py` — pasada E2E contra datasets LangSmith
- `scripts/upload_dataset.py` — subida del golden dataset a LangSmith
- `evals/evaluators.py` — funciones `langsmith_caXX` de evaluación

Estos scripts **no se tocan** en la migración de tracing.

## Nuevo punto de entrada de tracing

```python
from observability.phoenix.init_tracing import init_tracing
init_tracing()  # llamar antes de graph.invoke()
```

Ver `observability/phoenix/init_tracing.py` y `scripts/test_phoenix_connection.py`.
