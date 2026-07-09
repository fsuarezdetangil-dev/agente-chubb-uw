"""
HITL Inbox — consulta de submissions esperando revisión humana.

Lee el checkpointer SQLite del grafo (persistencia de LangGraph) y devuelve
las submissions que están pausadas en un punto HITL (interrupt_before). Es
READ-ONLY: no reanuda ni modifica ningún estado del grafo.

Pensado para consumo por polling desde un futuro frontend ("tienes N
submissions esperando tu revisión"). No requiere infraestructura en tiempo
real: los puntos HITL esperan a una persona, así que un refresco periódico
(cada 15-30 s) es más que suficiente.

Convención de threads reales
-----------------------------
El checkpointer acumula muchos threads de test/probe (p. ej. `SUB-001-3B`,
`SUB-006-px`, `SUB-002-e2e`, `TEST-HITL1`). Para distinguir una submission
"real" de una de prueba se usa una convención de nombre de `thread_id`:
un thread real tiene la forma `SUB-<dígitos>` EXACTAMENTE (ej. `SUB-063`),
sin sufijos. El patrón por defecto es `^SUB-\\d+$`. Es configurable por si
en producción se adopta otra convención (o una tabla-registro dedicada).
"""

import re
import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver

from .graph import build_graph

# Nodos HITL del grafo → número de punto para el frontend
_HITL_NODES = {"hitl_point_1": 1, "hitl_point_2": 2, "hitl_point_3": 3}

# Convención de thread_id para submissions reales (ver docstring del módulo)
DEFAULT_REAL_THREAD_PATTERN = r"^SUB-\d+$"

DEFAULT_DB_PATH = "checkpoints.db"


def _list_thread_ids(conn: sqlite3.Connection) -> list[str]:
    """Enumera los thread_id distintos persistidos en el checkpointer."""
    try:
        rows = conn.execute("SELECT DISTINCT thread_id FROM checkpoints").fetchall()
    except sqlite3.OperationalError:
        # La tabla no existe todavía (checkpointer vacío)
        return []
    return [r[0] for r in rows]


def _waiting_reason(point: int, values: dict) -> str:
    """Genera una descripción legible de por qué la submission está esperando."""
    if point == 1:
        missing = values.get("missing_fields") or []
        campos = ", ".join(missing) if missing else "campos por confirmar"
        return f"Datos incompletos — faltan: {campos}"
    if point == 2:
        verdict = (values.get("appetite_result") or {}).get("verdict", "sin veredicto")
        return f"Revisión de apetito — veredicto: {verdict}"
    if point == 3:
        score = values.get("risk_score")
        flags = values.get("risk_flags") or []
        flags_str = f" ({len(flags)} flags)" if flags else ""
        return f"Riesgo elevado — score {score}{flags_str}"
    return "Esperando revisión"


def _build_item(thread_id: str, point: int, values: dict) -> dict:
    """Construye el objeto que consumirá el frontend para una submission pendiente."""
    extracted = values.get("extracted_data") or {}
    metadata = values.get("metadata") or {}
    raw = values.get("submission_raw") or {}

    company_name = (
        extracted.get("company_name")
        or metadata.get("tomador")
        or raw.get("metadata", {}).get("tomador")
        or "(desconocido)"
    )
    broker = (
        metadata.get("broker_name")
        or (raw.get("broker") if isinstance(raw.get("broker"), str) else None)
        or raw.get("metadata", {}).get("broker")
        or "(desconocido)"
    )

    item = {
        "submission_id": values.get("submission_id", thread_id),
        "hitl_point": point,
        "company_name": company_name,
        "line_of_business": values.get("line_of_business", ""),
        "broker": broker,
        "waiting_reason": _waiting_reason(point, values),
        "thread_id": thread_id,
        # Campos específicos según el punto (el frontend usa el que aplique)
        "missing_fields": values.get("missing_fields") or [],
        "appetite_verdict": (values.get("appetite_result") or {}).get("verdict"),
        "risk_score": values.get("risk_score"),
        "risk_flags": values.get("risk_flags") or [],
    }
    return item


def list_pending_hitl(
    db_path: str = DEFAULT_DB_PATH,
    real_thread_pattern: str = DEFAULT_REAL_THREAD_PATTERN,
) -> list[dict]:
    """Devuelve las submissions reales pausadas en un punto HITL.

    Es read-only: abre el checkpointer, para cada thread que cumpla la
    convención de nombre consulta el estado del grafo y se queda con los que
    tienen `.next` apuntando a un nodo HITL. No reanuda ni escribe nada.

    Returns: lista de dicts (ver `_build_item`), ordenada por punto HITL y luego
    por submission_id.
    """
    pattern = re.compile(real_thread_pattern)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    try:
        graph = build_graph(checkpointer=SqliteSaver(conn))
        pending: list[dict] = []
        for thread_id in _list_thread_ids(conn):
            if not pattern.match(thread_id):
                continue  # thread de test/probe, se ignora
            config = {"configurable": {"thread_id": thread_id}}
            snapshot = graph.get_state(config)
            next_nodes = snapshot.next or ()
            # Buscar si el próximo nodo pendiente es un punto HITL
            point = next(
                (_HITL_NODES[n] for n in next_nodes if n in _HITL_NODES),
                None,
            )
            if point is None:
                continue  # o ya terminó, o no está en HITL
            pending.append(_build_item(thread_id, point, snapshot.values))
    finally:
        conn.close()

    pending.sort(key=lambda x: (x["hitl_point"], x["submission_id"]))
    return pending
