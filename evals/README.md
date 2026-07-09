# EVALS — Criterios de aceptación

Criterios de aceptación técnicos de la PoC. Cada CA corresponde a un nodo o comportamiento del agente y define el evaluador que se usará en Fase 4.

---

## CA-01 — Clasificación de línea de negocio (Node 1)

**Qué mide:** Node 1 (Submission Intake) clasifica correctamente la línea de negocio.  
**Target:** > 90 % de los casos del golden dataset correctamente clasificados.  
**Evaluador:** Code-based — comparación directa con etiqueta ground-truth del golden dataset.

---

## CA-02 — Extracción de campos críticos (Node 2)

**Qué mide:** Node 2 (Data Extraction) extrae los campos críticos con alta accuracy.  
**Target:** > 92 % de accuracy campo a campo sobre el golden dataset.  
**Evaluador:** Code-based con comparación campo a campo entre `extracted_data` y ground-truth.

---

## CA-03 — Detección de campos faltantes (Node 2)

**Qué mide:** Node 2 detecta correctamente todos los campos faltantes en submissions incompletas.  
**Target:** 100 % de recall sobre los casos del golden dataset marcados como incompletos.  
**Evaluador:** Code-based — verificar que `missing_fields` contiene exactamente los campos ausentes.

---

## CA-04 — Veredicto de apetito (Node 3)

**Qué mide:** Node 3 (Appetite & Validation) produce el veredicto correcto (accept / refer / decline).  
**Target:** > 90 % de los casos del golden dataset con veredicto correcto.  
**Evaluador:** LLM-Judge + validación humana de UW experto.

---

## CA-05 — RAG Faithfulness (Node 3)

**Qué mide:** Las citas del RAG son fieles a los guidelines de apetito recuperados.  
**Target:** RAGAS Faithfulness > 0.90.  
**Evaluador:** RAGAS Faithfulness score sobre el conjunto de evaluación RAG.

---

## CA-06 — Activación correcta de puntos HITL

**Qué mide:** Los tres puntos HITL se activan en exactamente los casos que los requieren.  
**Target:** 100 % de activación correcta — sin falsos negativos (nunca saltar un HITL requerido).  
**Evaluador:** Code-based — comparar `hitl_point` en el estado final con ground-truth del golden dataset.

---

## CA-07 — Calidad de outputs finales (Node 5)

**Qué mide:** Node 5 (Output Generation) produce un risk summary de calidad suficiente.  
**Target:** LLM-Judge score > 85 / 100.  
**Evaluador:** LLM-Judge con rúbrica de 5 dimensiones: precisión técnica, completitud, claridad, accionabilidad, ausencia de alucinaciones.

---

## CA-08 — Time-to-quote en modo STP

**Qué mide:** El tiempo de procesamiento del agente en el camino feliz (sin HITL).  
**Target:** < 4 minutos de procesamiento del agente (excluido tiempo de revisión del UW).  
**Evaluador:** Code-based con timestamps de `audit_log` — medir desde `submission_intake_start` hasta `output_generation_end`.

---

## Golden dataset

Localización: `evals/golden_dataset/`  
Formato: JSON con schema definido en Fase 1.  
Composición objetivo: 50-100 submissions (30 Property + 30 Casualty + 10 edge cases).
