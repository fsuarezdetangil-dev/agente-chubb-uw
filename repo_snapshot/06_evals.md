# 06 — Evaluación (evals + scripts LangSmith)

Los 8 criterios de aceptación (CA-01 a CA-08) están implementados con **doble firma**: una
versión standalone (`eval_ca0X(result, reference)`) para el runner local, y una versión
LangSmith (`langsmith_ca0X(run, example)`) para `evaluate()`. Solo el camino local se ha
ejecutado realmente; el camino LangSmith está codificado pero nunca se corrió (key 403).

> Discrepancia de targets: `evals/README.md` (redactado en Fase 0) dice targets como
> CA-01 >90%, CA-02 >92%. El docstring de `evaluators.py` y `DEVELOPMENT_PLAN.md` usan otros
> umbrales (CA-01 ≥95%, CA-02 ≥80%). No están alineados entre sí.

---

## `evals/evaluators.py` — 206 líneas

```python
"""
Evaluadores CA-01 a CA-08 para el agente UW de Chubb EMEA.

Cada evaluador tiene firma compatible con LangSmith:
    evaluator(run: Run, example: Example) -> EvaluationResult

También exporta versiones standalone para uso en scripts locales:
    eval_ca0X(result: dict, reference: dict) -> bool | float | None

Criterios de aceptación:
    CA-01  LOB accuracy         ≥ 95 %
    CA-02  Extraction accuracy  ≥ 80 % de campos críticos
    CA-03  Missing-fields detection  ≥ 90 %
    CA-04  Appetite verdict     ≥ 85 %
    CA-05  RAG citations presentes  100 %
    CA-06  HITL routing correcto    ≥ 95 %
    CA-07  LLM-Judge score      ≥ 85/100 en ≥ 90 % de submissions
    CA-08  Time-to-quote        < 4 min en ≥ 95 %
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

# Campos evaluados en CA-02: solo los extraíbles del email body.
# cnae_code y loss_history se excluyen porque vienen de adjuntos (DUDA-004, sin pdf_parser).
CAMPOS_CRITICOS = [
    "company_name", "activity_description",
    "province", "sum_insured_eur", "requested_coverages", "renewal",
]


# ── helpers ───────────────────────────────────────────────────────────────────

def _get_output(run_or_result) -> dict:
    """Extrae el dict de outputs tanto de un Run de LangSmith como de un dict directo."""
    if hasattr(run_or_result, "outputs"):          # LangSmith Run object
        return run_or_result.outputs or {}
    return run_or_result or {}                      # dict directo (uso local)


def _get_reference(example_or_ref) -> dict:
    """Extrae el dict de referencia tanto de un Example de LangSmith como de un dict directo."""
    if hasattr(example_or_ref, "outputs"):         # LangSmith Example object
        return example_or_ref.outputs or {}
    return example_or_ref or {}                    # dict directo (uso local)


# ── evaluadores locales (standalone) ─────────────────────────────────────────

def eval_ca01(result: dict, reference: dict) -> bool:
    """CA-01: LOB clasificada correctamente."""
    return result.get("line_of_business") == reference.get("line_of_business")


def eval_ca02(result: dict, reference: dict) -> float | None:
    """CA-02: Fracción de campos críticos extraídos correctamente (0.0–1.0)."""
    gt = reference.get("extracted_data_ground_truth", {})
    ext = result.get("extracted_data", {})
    hits, total = 0, 0
    for campo in CAMPOS_CRITICOS:
        gt_val = gt.get(campo)
        if gt_val is None:
            continue
        total += 1
        ex_val = ext.get(campo)
        if isinstance(gt_val, list) and gt_val and isinstance(gt_val[0], dict):
            ok = len(gt_val) == len(ex_val or [])
        elif isinstance(gt_val, list):
            ok = set(str(x).lower() for x in gt_val) == set(str(x).lower() for x in (ex_val or []))
        else:
            ok = str(gt_val).lower().strip() == str(ex_val).lower().strip()
        hits += int(ok)
    return hits / total if total else None


def eval_ca03(result: dict, reference: dict) -> bool:
    """CA-03: Campos faltantes detectados correctamente."""
    gt_missing = set(reference.get("missing_fields_expected", []))
    detected   = set(result.get("missing_fields", []))
    if not gt_missing:
        return len(detected) == 0
    return gt_missing.issubset(detected)


def eval_ca04(result: dict, reference: dict) -> bool:
    """CA-04: Veredicto de apetito correcto."""
    expected = reference.get("appetite_expected", "")
    actual   = result.get("appetite_result", {}).get("verdict", "")
    return actual == expected


def eval_ca05(result: dict, _reference: dict | None = None) -> bool:
    """CA-05: Al menos una cita RAG en el resultado de apetito."""
    cits = result.get("appetite_result", {}).get("rag_citations", [])
    return len(cits) >= 1


def eval_ca06(result: dict, reference: dict, hitl_triggered: list[str] | None = None) -> bool:
    """CA-06: El punto HITL correcto fue activado (o STP sin HITL)."""
    expected = reference.get("expected_hitl_trigger", "")
    triggered = hitl_triggered or result.get("_hitl_triggered", [])
    if expected == "STP_dentro_apetito":
        return len(triggered) == 0
    elif expected == "HITL-1_datos_incompletos":
        return "hitl_point_1" in triggered
    elif expected == "HITL-2_declinar":
        return "hitl_point_2" in triggered
    elif expected == "HITL-3_referir_senior":
        return "hitl_point_3" in triggered
    return True


def eval_ca07(result: dict, _reference: dict | None = None) -> tuple[bool, int]:
    """CA-07: LLM-Judge score >= 85/100. Devuelve (ok, score)."""
    score = result.get("outputs", {}).get("_quality", {}).get("llm_judge_score", 0)
    return score >= 85, score


def eval_ca08(result: dict, _reference: dict | None = None) -> tuple[bool | None, float | None]:
    """CA-08: Time-to-quote < 4 min. Devuelve (ok, segundos)."""
    log = result.get("audit_log", [])
    if len(log) < 2:
        return None, None
    t0 = datetime.fromisoformat(log[0]["timestamp"])
    t1 = datetime.fromisoformat(log[-1]["timestamp"])
    elapsed = (t1 - t0).total_seconds()
    return elapsed < 240, round(elapsed, 1)


# ── evaluadores LangSmith (firma Run, Example → EvaluationResult) ─────────────

def _make_result(key: str, score: float | None, comment: str = "") -> dict:
    """Crea un EvaluationResult compatible con LangSmith."""
    return {"key": key, "score": score, "comment": comment}


def langsmith_ca01(run: Any, example: Any) -> dict:
    result    = _get_output(run)
    reference = _get_reference(example)
    ok = eval_ca01(result, reference)
    return _make_result("ca01_lob_accuracy", float(ok),
                        f"got={result.get('line_of_business')} expected={reference.get('line_of_business')}")


def langsmith_ca02(run: Any, example: Any) -> dict:
    result    = _get_output(run)
    reference = _get_reference(example)
    score = eval_ca02(result, reference)
    return _make_result("ca02_extraction_accuracy", score,
                        f"fraccion_campos_criticos={score:.2f}" if score is not None else "sin gt")


def langsmith_ca03(run: Any, example: Any) -> dict:
    result    = _get_output(run)
    reference = _get_reference(example)
    ok = eval_ca03(result, reference)
    detected  = result.get("missing_fields", [])
    expected  = reference.get("missing_fields_expected", [])
    return _make_result("ca03_missing_fields", float(ok),
                        f"detected={detected} expected={expected}")


def langsmith_ca04(run: Any, example: Any) -> dict:
    result    = _get_output(run)
    reference = _get_reference(example)
    ok = eval_ca04(result, reference)
    return _make_result("ca04_appetite_verdict", float(ok),
                        f"got={result.get('appetite_result',{}).get('verdict')} expected={reference.get('appetite_expected')}")


def langsmith_ca05(run: Any, example: Any) -> dict:
    result = _get_output(run)
    ok = eval_ca05(result)
    n_cits = len(result.get("appetite_result", {}).get("rag_citations", []))
    return _make_result("ca05_rag_citations", float(ok), f"n_citations={n_cits}")


def langsmith_ca06(run: Any, example: Any) -> dict:
    result    = _get_output(run)
    reference = _get_reference(example)
    ok = eval_ca06(result, reference)
    return _make_result("ca06_hitl_routing", float(ok),
                        f"expected={reference.get('expected_hitl_trigger')}")


def langsmith_ca07(run: Any, example: Any) -> dict:
    result = _get_output(run)
    ok, score = eval_ca07(result)
    return _make_result("ca07_llm_judge", float(ok), f"score={score}/100")


def langsmith_ca08(run: Any, example: Any) -> dict:
    result = _get_output(run)
    ok, secs = eval_ca08(result)
    if ok is None:
        return _make_result("ca08_time_to_quote", None, "audit_log insuficiente")
    return _make_result("ca08_time_to_quote", float(ok), f"{secs}s")


ALL_EVALUATORS = [
    langsmith_ca01, langsmith_ca02, langsmith_ca03, langsmith_ca04,
    langsmith_ca05, langsmith_ca06, langsmith_ca07, langsmith_ca08,
]
```

---

## `scripts/upload_dataset.py` — 102 líneas

```python
"""
Carga el golden dataset de las 72 submissions a LangSmith.
Ejecutar desde la raíz: python scripts/upload_dataset.py

Requiere LANGCHAIN_API_KEY válida en .env.
Crea (o actualiza) el dataset "chubb-uw-golden-72" en LangSmith.
"""

import sys, os, json, warnings, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
warnings.filterwarnings("ignore")
logging.getLogger("langsmith").setLevel(logging.WARNING)

from dotenv import load_dotenv
load_dotenv()

from langsmith import Client

DATASET_NAME = "chubb-uw-golden-72"
DATASET_DESC = (
    "Golden dataset PoC UW Agent Chubb EMEA — 72 submissions sintéticas "
    "(36 Property + 36 Casualty, incluidos 12 edge cases). "
    "Cubre escenarios STP, HITL-1/2/3 y casos límite."
)

# Campos que se pasan como inputs al agente
INPUT_KEYS = ["submission_id", "channel", "line_of_business", "broker",
              "received_at", "email_raw", "attachments"]

# Campos que se usan como referencia (ground truth) en los evaluadores
OUTPUT_KEYS = ["extracted_data_ground_truth", "missing_fields_expected",
               "appetite_expected", "expected_hitl_trigger",
               "expected_hitl_trigger_reason", "scenario_tag"]


def load_submissions() -> list[dict]:
    with open("data/samples/submissions_synthetic_all_70.json", encoding="utf-8") as f:
        subs = json.load(f)
    with open("data/samples/submissions_edge_cases_12.json", encoding="utf-8") as f:
        edges = json.load(f)
    seen = {s["submission_id"] for s in subs}
    for e in edges:
        if e["submission_id"] not in seen:
            subs.append(e)
    return subs


def main():
    client = Client()

    # Verificar conexión
    try:
        me = client.list_datasets(limit=1)
        list(me)  # forzar consumo del generador
        print("Conexion LangSmith OK")
    except Exception as e:
        print(f"Error al conectar con LangSmith: {e}")
        print("Verifica LANGCHAIN_API_KEY en .env")
        sys.exit(1)

    subs = load_submissions()
    print(f"Submissions cargadas: {len(subs)}")

    # Crear o recuperar dataset
    existing = [d for d in client.list_datasets() if d.name == DATASET_NAME]
    if existing:
        dataset = existing[0]
        print(f"Dataset existente encontrado: {dataset.id}")
        answer = input("Sobreescribir ejemplos? [s/N]: ").strip().lower()
        if answer != "s":
            print("Cancelado.")
            return
        for ex in client.list_examples(dataset_id=dataset.id):
            client.delete_example(ex.id)
        print("Ejemplos anteriores eliminados.")
    else:
        dataset = client.create_dataset(
            dataset_name=DATASET_NAME,
            description=DATASET_DESC,
        )
        print(f"Dataset creado: {dataset.id}")

    # Subir ejemplos
    uploaded = 0
    for sub in subs:
        inputs  = {k: sub.get(k) for k in INPUT_KEYS}
        outputs = {k: sub.get(k) for k in OUTPUT_KEYS}
        client.create_example(
            inputs=inputs,
            outputs=outputs,
            dataset_id=dataset.id,
        )
        uploaded += 1
        if uploaded % 10 == 0:
            print(f"  {uploaded}/{len(subs)} subidos...")

    print(f"\nDataset '{DATASET_NAME}' listo con {uploaded} ejemplos.")
    print(f"URL: https://smith.langchain.com/datasets/{dataset.id}")


if __name__ == "__main__":
    main()
```

> Bug latente: `upload_dataset.py` pone la referencia (ground truth) en `outputs` del Example,
> pero `run_langsmith_eval.py` la espera en `inputs["__reference"]` (ver comentario "workaround
> LangSmith" en la línea 87). Los evaluadores LangSmith sí leen de `example.outputs`, así que
> hay una inconsistencia de contrato entre los dos scripts que nunca llegó a probarse en vivo.

---

## `scripts/run_langsmith_eval.py` — 129 líneas

```python
"""
Ejecuta la evaluación formal del agente contra el golden dataset en LangSmith.
Ejecutar desde la raíz: python scripts/run_langsmith_eval.py

Prerequisitos:
  1. LANGCHAIN_API_KEY válida en .env (sin error 403)
  2. Dataset "chubb-uw-golden-72" subido (python scripts/upload_dataset.py)

Qué hace:
  - Carga el grafo con checkpointer SQLite temporal (thread_id único por run)
  - Para cada ejemplo del dataset invoca el agente y auto-reanuda HITL
  - Evalúa CA-01 a CA-08 con los evaluadores de evals/evaluators.py
  - Publica resultados en LangSmith Experiments
"""

import sys, os, json, warnings, logging, sqlite3
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
warnings.filterwarnings("ignore")
logging.getLogger("langsmith").setLevel(logging.WARNING)

from dotenv import load_dotenv
load_dotenv()
os.environ["LANGCHAIN_TRACING_V2"] = "true"

from langsmith import Client, evaluate
from backend.agent.graph import build_graph
from backend.agent.state import AgentState
from evals.evaluators import ALL_EVALUATORS
from langgraph.checkpoint.sqlite import SqliteSaver

DATASET_NAME = "chubb-uw-golden-72"


def _build_state(inputs: dict) -> AgentState:
    broker = inputs.get("broker", "")
    if isinstance(broker, dict):
        broker = broker.get("name", "")
    return {
        "submission_id":    inputs.get("submission_id", ""),
        "submission_raw":   inputs,
        "channel":          inputs.get("channel", "email"),
        "line_of_business": inputs.get("line_of_business", "property"),
        "metadata":         {"broker_name": broker},
        "extracted_data":   {},
        "missing_fields":   [],
        "appetite_result":  {},
        "risk_score":       0,
        "risk_flags":       [],
        "pricing_output":   {},
        "outputs":          {},
        "audit_log":        [],
        "hitl_status":      "none",
        "hitl_point":       "none",
        "plan_json":        [],
    }


def _resume_hitl(graph, result, config, reference: dict) -> tuple[dict, list[str]]:
    """Auto-reanuda HITL inyectando ground truth en HITL-1."""
    snapshot = graph.get_state(config)
    hitl_nodes = []
    count = 0
    while snapshot.next and count < 3:
        node = snapshot.next[0]
        hitl_nodes.append(node)
        updates = {"hitl_status": "approved"}
        if node == "hitl_point_1":
            updates["extracted_data"] = reference.get("extracted_data_ground_truth", {})
            updates["missing_fields"] = []
        graph.update_state(config, updates)
        result = graph.invoke(None, config=config)
        snapshot = graph.get_state(config)
        count += 1
    return result, hitl_nodes


def agent_fn(inputs: dict) -> dict:
    """Función del agente para LangSmith evaluate(). Incluye _hitl_triggered en outputs."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    graph = build_graph(checkpointer=SqliteSaver(conn))

    sid = inputs.get("submission_id", "unknown")
    config = {"configurable": {"thread_id": sid + "-ls"}}
    state = _build_state(inputs)

    # La referencia se pasa en inputs bajo la clave "__reference" (workaround LangSmith)
    reference = inputs.get("__reference", {})

    result = graph.invoke(state, config=config)
    result, hitl_triggered = _resume_hitl(graph, result, config, reference)

    conn.close()
    result["_hitl_triggered"] = hitl_triggered
    return result


def main():
    client = Client()

    # Verificar conexión y dataset
    datasets = [d for d in client.list_datasets() if d.name == DATASET_NAME]
    if not datasets:
        print(f"Dataset '{DATASET_NAME}' no encontrado.")
        print("Ejecuta primero: python scripts/upload_dataset.py")
        sys.exit(1)

    print(f"Dataset encontrado: {datasets[0].id}")
    print("Lanzando evaluacion en LangSmith...\n")

    results = evaluate(
        agent_fn,
        data=DATASET_NAME,
        evaluators=ALL_EVALUATORS,
        experiment_prefix="chubb-uw-e2e",
        description="Pasada E2E automatica — CA-01 a CA-08",
        max_concurrency=1,         # llamadas secuenciales para evitar rate limit Azure
    )

    print("\n=== RESUMEN ===")
    for r in results:
        scores = {e["key"]: e["score"] for e in (r.evaluation_results or {}).get("results", [])}
        print(f"  {r.run.name}: {scores}")

    print(f"\nResultados publicados en LangSmith Experiments.")
    print(f"URL: https://smith.langchain.com")


if __name__ == "__main__":
    main()
```

---

## `evals/README.md` — 76 líneas (íntegro)

```markdown
# EVALS — Criterios de aceptación

Criterios de aceptación técnicos de la PoC. Cada CA corresponde a un nodo o comportamiento del agente y define el evaluador que se usará en Fase 4.

---

## CA-01 — Clasificación de línea de negocio (Node 1)
**Qué mide:** Node 1 (Submission Intake) clasifica correctamente la línea de negocio.
**Target:** > 90 % de los casos del golden dataset correctamente clasificados.
**Evaluador:** Code-based — comparación directa con etiqueta ground-truth del golden dataset.

## CA-02 — Extracción de campos críticos (Node 2)
**Qué mide:** Node 2 (Data Extraction) extrae los campos críticos con alta accuracy.
**Target:** > 92 % de accuracy campo a campo sobre el golden dataset.
**Evaluador:** Code-based con comparación campo a campo entre `extracted_data` y ground-truth.

## CA-03 — Detección de campos faltantes (Node 2)
**Qué mide:** Node 2 detecta correctamente todos los campos faltantes en submissions incompletas.
**Target:** 100 % de recall sobre los casos del golden dataset marcados como incompletos.
**Evaluador:** Code-based — verificar que `missing_fields` contiene exactamente los campos ausentes.

## CA-04 — Veredicto de apetito (Node 3)
**Qué mide:** Node 3 (Appetite & Validation) produce el veredicto correcto (accept / refer / decline).
**Target:** > 90 % de los casos del golden dataset con veredicto correcto.
**Evaluador:** LLM-Judge + validación humana de UW experto.

## CA-05 — RAG Faithfulness (Node 3)
**Qué mide:** Las citas del RAG son fieles a los guidelines de apetito recuperados.
**Target:** RAGAS Faithfulness > 0.90.
**Evaluador:** RAGAS Faithfulness score sobre el conjunto de evaluación RAG.

## CA-06 — Activación correcta de puntos HITL
**Qué mide:** Los tres puntos HITL se activan en exactamente los casos que los requieren.
**Target:** 100 % de activación correcta — sin falsos negativos (nunca saltar un HITL requerido).
**Evaluador:** Code-based — comparar `hitl_point` en el estado final con ground-truth.

## CA-07 — Calidad de outputs finales (Node 5)
**Qué mide:** Node 5 (Output Generation) produce un risk summary de calidad suficiente.
**Target:** LLM-Judge score > 85 / 100.
**Evaluador:** LLM-Judge con rúbrica de 5 dimensiones.

## CA-08 — Time-to-quote en modo STP
**Qué mide:** El tiempo de procesamiento del agente en el camino feliz (sin HITL).
**Target:** < 4 minutos de procesamiento del agente (excluido tiempo de revisión del UW).
**Evaluador:** Code-based con timestamps de `audit_log`.

## Golden dataset
Localización: `evals/golden_dataset/`  (⚠️ VACÍA — el dataset real vive en data/samples/)
Formato: JSON con schema definido en Fase 1.
Composición objetivo: 50-100 submissions (30 Property + 30 Casualty + 10 edge cases).
```

> ⚠️ `evals/README.md` apunta a `evals/golden_dataset/` como localización del dataset, pero esa
> carpeta está **vacía**. El dataset real está en `data/samples/*.json`. Además menciona
> "RAGAS Faithfulness" para CA-05, pero el evaluador implementado solo comprueba que exista
> ≥1 cita (no calcula faithfulness). El código y el README divergen.
