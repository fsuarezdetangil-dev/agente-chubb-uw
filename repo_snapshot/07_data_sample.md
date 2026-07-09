# 07 — Muestra de datos (submissions sintéticas)

Las submissions sintéticas viven en `data/samples/` (NO en `data/base/`, que solo contiene los
guidelines y `schemas.py`). El conteo real es de **70 en el archivo "all"** + **12 edge cases**
= 72 tras deduplicar (así lo hace `upload_dataset.py`). Nota: el resumen de estratificación dice
"total 72" pero el archivo principal se llama `..._all_70.json`.

Ficheros:
- `submissions_property_30.json` — 30 Property
- `submissions_casualty_30.json` — 30 Casualty
- `submissions_edge_cases_12.json` — 12 edge cases
- `submissions_synthetic_all_70.json` — consolidado (70)
- `submissions_stratification_summary.json` — resumen de distribución
- `*_bak.json` — backups

---

## Estructura de carpetas `data/` (solo listado)

```
data/
├── base/
│   ├── schemas.py                                     (Pydantic models — abajo)
│   ├── appetite_guidelines_property_casualty.md       (duplicado de backend/kb/raw/)
│   └── pricing_guidelines_property_casualty.md        (duplicado de backend/kb/raw/)
└── samples/
    ├── submissions_property_30.json                   (30 submissions)
    ├── submissions_casualty_30.json                   (30 submissions)
    ├── submissions_edge_cases_12.json                 (12 submissions)
    ├── submissions_edge_cases_12_bak.json             (backup)
    ├── submissions_synthetic_all_70.json              (70 submissions consolidadas)
    ├── submissions_synthetic_all_70_bak.json          (backup)
    └── submissions_stratification_summary.json        (resumen de estratificación)
```

---

## Resumen de estratificación (`submissions_stratification_summary.json`)

```json
{
  "total": 72,
  "property": 30,
  "casualty": 30,
  "edge_cases": 12,
  "by_appetite": { "dentro": 41, "fuera": 10, "revision": 21 },
  "by_expected_hitl_trigger": {
    "HITL-1_datos_incompletos": 14,
    "STP_dentro_apetito": 27,
    "HITL-2_declinar": 10,
    "HITL-3_referir_senior": 21
  },
  "incomplete_data_count": 14,
  "complete_data_count": 58,
  "reflection_test_cases": 2,
  "renewal_count": 34,
  "new_business_count": 38
}
```

---

## Ejemplo de UNA submission completa (SUB-002, `submissions_property_30.json`)

Caso "camino feliz" (STP, dentro de apetito, datos completos):

```json
{
  "submission_id": "SUB-002",
  "line_of_business": "property",
  "scenario_tag": "property_dentro",
  "channel": "email",
  "broker": "Willis Towers Watson Iberia",
  "received_at": "2026-04-09T15:40:00Z",
  "email_raw": {
    "from": "suscripcion@willistowerswatsoniberia.es",
    "subject": "Renovación P&C — Clínica del Sur",
    "body": "Buenos días,\n\nLes remito nueva renovación para nuestro cliente Clínica del Sur, dedicado a la actividad de clínica dental privada, con sede en Barcelona.\n\nSolicitan cobertura de Responsabilidad Civil de explotación, Daños materiales con una suma asegurada aproximada de 1,347,117 EUR.\n\nAdjunto memoria de actividad y cuestionario de suscripción.\n\nQuedamos a su disposición para cualquier aclaración.\n\nUn saludo,\nWillis Towers Watson Iberia"
  },
  "attachments": [
    {
      "filename": "SUB-002_memoria_actividad.pdf",
      "type": "memoria_actividad",
      "extracted_text_summary": "Memoria de actividad de Clínica del Sur. CNAE 8623 — Clínica dental privada. Ubicación: Barcelona. Suma asegurada solicitada: 1347117 EUR. Histórico de siniestros declarados: 1 casos en los últimos 3 años. Loss ratio histórico estimado: 0.08."
    }
  ],
  "extracted_data_ground_truth": {
    "company_name": "Clínica del Sur",
    "cnae_code": "8623",
    "activity_description": "Clínica dental privada",
    "province": "Barcelona",
    "sum_insured_eur": 1347117,
    "requested_coverages": [
      "Responsabilidad Civil de explotación",
      "Daños materiales"
    ],
    "loss_history": [
      { "fecha": "2024-11-20", "tipo": "responsabilidad civil terceros", "importe_eur": 152849 }
    ],
    "loss_ratio": 0.08,
    "renewal": true
  },
  "missing_fields_expected": [],
  "appetite_expected": "dentro",
  "complete_data_expected": true,
  "expected_hitl_trigger": "STP_dentro_apetito",
  "expected_hitl_trigger_reason": "Dentro de apetito, datos completos, sin factores de agravación — candidato a modo STP"
}
```

### Claves de nivel superior de cada submission (14 campos)
`submission_id`, `line_of_business`, `scenario_tag`, `channel`, `broker`, `received_at`,
`email_raw`, `attachments`, `extracted_data_ground_truth`, `missing_fields_expected`,
`appetite_expected`, `complete_data_expected`, `expected_hitl_trigger`,
`expected_hitl_trigger_reason`.

### Observaciones sobre la estructura de datos
- `email_raw` es un **objeto** `{from, subject, body}`, y `broker` es un **string**.
- `cnae_code` y `loss_history` viven en `attachments[].extracted_text_summary` (texto libre),
  NO en el body del email. Por eso DUDA-004 los excluye de HITL-1 (no hay pdf_parser).
- `loss_history` en el ground truth es una **lista de objetos** `{fecha, tipo, importe_eur}`.
  ⚠️ Pero `data/base/schemas.py` declara `loss_history: Optional[str]` (un string) →
  desalineación entre el schema Pydantic y los datos reales.

---

## `data/base/schemas.py` — 37 líneas

```python
"""
Pydantic models para submissions y outputs del agente.
Estos schemas son la fuente de verdad para ground-truth y validación en evals.
"""

from typing import Optional
from pydantic import BaseModel, Field


class ExtractedData(BaseModel):
    company_name: Optional[str] = None
    cnae_code: Optional[str] = None
    activity_description: Optional[str] = None
    province: Optional[str] = None
    sum_insured_eur: Optional[float] = None
    requested_coverages: Optional[list[str]] = None
    loss_history: Optional[str] = None          # ⚠️ str, pero los datos usan list[dict]
    loss_ratio: Optional[float] = None
    renewal: Optional[bool] = None


class SubmissionInput(BaseModel):
    submission_id: str
    line_of_business: str = Field(..., pattern="^(property|casualty)$")
    scenario_tag: str
    channel: str = Field(..., pattern="^(email|portal|api)$")
    broker: dict                                 # ⚠️ dict, pero los datos usan str
    received_at: str
    email_raw: str                               # ⚠️ str, pero los datos usan dict
    attachments: list[dict] = []
    extracted_data_ground_truth: ExtractedData
    missing_fields_expected: list[str] = []
    appetite_expected: str = Field(..., pattern="^(dentro|fuera|revision)$")
    complete_data_expected: bool
    expected_hitl_trigger: str
    expected_hitl_trigger_reason: str
```

> ⚠️ `schemas.py` no se usa en el pipeline en ejecución (los nodos trabajan con dicts crudos)
> y además está desalineado con la forma real de los datos en 3 campos (`broker`, `email_raw`,
> `loss_history`). Si se quisiera validar las submissions con estos modelos, fallarían.
