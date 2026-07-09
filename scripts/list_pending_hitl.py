"""
CLI — Bandeja de HITL pendientes.

Lista las submissions que están esperando revisión humana en algún punto HITL,
agrupadas por punto. Read-only: no reanuda ni modifica nada.

Uso:
    python scripts/list_pending_hitl.py
    python scripts/list_pending_hitl.py --db checkpoints.db
    python scripts/list_pending_hitl.py --pattern "^SUB-\\d+$"
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.agent.hitl_inbox import (  # noqa: E402
    DEFAULT_DB_PATH,
    DEFAULT_REAL_THREAD_PATTERN,
    list_pending_hitl,
)

_PUNTO_LABEL = {
    1: "HITL-1 · Datos incompletos",
    2: "HITL-2 · Revisión de apetito",
    3: "HITL-3 · Revisión senior de riesgo",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Lista submissions esperando en HITL.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="Ruta del checkpointer SQLite")
    parser.add_argument(
        "--pattern",
        default=DEFAULT_REAL_THREAD_PATTERN,
        help="Regex de thread_id para submissions reales",
    )
    args = parser.parse_args()

    pending = list_pending_hitl(db_path=args.db, real_thread_pattern=args.pattern)

    total = len(pending)
    print()
    print("=" * 72)
    print(f"  BANDEJA DE REVISIÓN — {total} submission(s) esperando tu revisión")
    print("=" * 72)

    if total == 0:
        print("\n  (No hay submissions pendientes en ningún punto HITL.)\n")
        return

    for punto in (1, 2, 3):
        grupo = [p for p in pending if p["hitl_point"] == punto]
        if not grupo:
            continue
        print(f"\n▸ {_PUNTO_LABEL[punto]}  ({len(grupo)})")
        print(f"  {'SUBMISSION':<12} {'LÍNEA':<10} {'TOMADOR':<24} {'BROKER':<18} MOTIVO")
        print(f"  {'-'*12} {'-'*10} {'-'*24} {'-'*18} {'-'*30}")
        for p in grupo:
            print(
                f"  {p['submission_id']:<12} "
                f"{(p['line_of_business'] or '-'):<10} "
                f"{p['company_name'][:23]:<24} "
                f"{p['broker'][:17]:<18} "
                f"{p['waiting_reason']}"
            )

    print()


if __name__ == "__main__":
    main()
