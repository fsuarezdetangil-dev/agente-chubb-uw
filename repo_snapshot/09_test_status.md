# 09 — Estado de tests y resultados de evals

## Estado de git

**No es un repositorio git.** No existe carpeta `.git` en la raíz ni en directorios
superiores. `git status` y `git log` devuelven:

```
fatal: not a git repository (or any of the parent directories): .git
```

Consecuencias:
- No hay historial de commits que revisar.
- El proyecto vive dentro de una carpeta sincronizada por OneDrive (hay un archivo marcador
  `.849C9593-D756-4E56-8D6E-42412F2A707B` de 63 bytes en la raíz).
- Aunque `.gitignore` existe y está bien redactado, hoy no protege nada porque no hay repo.

---

## Tests unitarios: NO existen

La carpeta `tests/` (con subcarpetas `test_agents/`, `test_flows/`, `test_tools/`) está
**completamente vacía**. Lo que hay son scripts manuales de prueba por fase en `scripts/`:
`smoke_test.py`, `smoke_test_hitl.py`, `test_fase3a.py`…`test_fase3e.py`, `probe_sub001.py`,
`inspect_gt.py`, `fix_gt_incompleto.py`. No hay `pytest`/`unittest` ni runner de tests.

---

## Resultados de evals ejecutados (runner local, NO LangSmith)

Hay 9 ficheros de resultados en `evals/results/` (`e2e_YYYYMMDD_HHMMSS.json`, entre 49 KB y
67 KB cada uno) más un `e2e_progress.log`. Cada JSON es un dict con las claves
`{records, errors, timestamp, n_submissions}`. El más reciente es
**`e2e_20260701_090140.json`** (n_submissions=72).

### Últimas líneas de `evals/results/e2e_progress.log` (resumen de la última pasada)

```
=================================================================
RESULTADOS E2E -- 55/72 submissions completadas sin error
=================================================================
CA-01 LOB accuracy:            52/55 = 95%
CA-02 Extraction avg accuracy: 0.98
CA-03 Missing fields detect:   44/55 = 80%
CA-04 Appetite verdict:        50/55 = 91%
CA-05 RAG citations:           55/55 = 100%
CA-06 HITL correcto:           40/55 = 73%
CA-07 LLM-Judge >=85:          55/55 = 100% | avg score: 98.09
CA-08 Time-to-quote <4min:     55/55 = 100% | avg: 23.29s

Errores: 17
  SUB-056 … SUB-071: "Connection error."   (16 casos)
  SUB-072: Error code: 403 - "A Virtual Network is configured for this resource.
           Please use the correct endpoint for making requests."

Distribucion veredictos apetito: {'dentro': 31, 'fuera': 8, 'revision': 16}
Distribucion HITL esperado:      {'HITL-1': 11, 'STP': 24, 'HITL-2': 8, 'HITL-3': 12}

Resultados guardados en: evals\results\e2e_20260701_090140.json
```

### Lectura de los resultados

| CA | Métrica | Resultado (55 OK de 72) | Target | ¿Pasa? |
|----|---------|------------------------|--------|--------|
| CA-01 | LOB accuracy | 95% (52/55) | ≥95% | ✅ justo |
| CA-02 | Extraction accuracy | 0.98 | ≥80% (docstring) / ≥92% (README) | ✅ |
| CA-03 | Missing fields | 80% (44/55) | ≥90% | ❌ |
| CA-04 | Appetite verdict | 91% (50/55) | ≥85% (docstring) / ≥90% (README) | ✅ / límite |
| CA-05 | RAG citations | 100% (55/55) | 100% | ✅ |
| CA-06 | HITL routing | 73% (40/55) | ≥95% | ❌ (el más flojo) |
| CA-07 | LLM-Judge ≥85 | 100%, avg 98.09 | ≥85 en ≥90% | ✅ |
| CA-08 | Time-to-quote | 100%, avg 23.3s | <4min en ≥95% | ✅ holgado |

### Puntos importantes
- **La pasada nunca terminó completa:** solo 55/72 submissions se procesaron. Las 17 restantes
  (SUB-056 a SUB-072, incluidos TODOS los edge cases SUB-061..SUB-072) fallaron por errores de
  conexión / VNet de Azure. Las métricas son sobre 55, no sobre las 72 → **no representan el
  dataset completo**, y precisamente faltan los casos límite más difíciles.
- **CA-06 (HITL routing) al 73% es el mayor problema funcional.** Muy por debajo del ≥95%
  requerido. Es el criterio más crítico ("nunca saltar un HITL requerido") y el que peor va.
- **CA-03 (missing fields) al 80%** también por debajo del ≥90%.
- CA-07 saliendo 98/100 de media es sospechosamente alto: el mismo modelo genera y se
  autoevalúa (reflection con el mismo LLM) → sesgo de autocomplacencia probable.
- El `time-to-quote` de ~23s es del agente en modo local secuencial; realista y muy por debajo
  del umbral.

### Estado declarado en los docs de contexto
- `DEVELOPMENT_PLAN.md`: Fases 0–3E COMPLETADAS; Fase E2E "EN CURSO"; Fase 4 "PARCIAL"
  (bloqueada por LangSmith 403); Fase 5 (demo) PENDIENTE.
- `checkpoints.db` pesa **185 MB** (SQLite del checkpointer LangGraph, acumulado de todas las
  ejecuciones). Candidato a purga; está bien que `.gitignore` incluya `*.db`.
