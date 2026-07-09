"""
Carga el golden dataset de las 72 submissions a Phoenix Arize como Dataset.
Ejecutar desde la raíz: python scripts/upload_phoenix_dataset.py

Requiere en .env:
  PHOENIX_API_KEY
  PHOENIX_COLLECTOR_ENDPOINT  (ej. https://app.phoenix.arize.com/s/Insurance_Agents/v1/traces)

Crea (o sobreescribe) el dataset "chubb-uw-golden-72" en Phoenix.
"""

import sys, os, json, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import httpx

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DATASET_NAME = "chubb-uw-golden-72"
DATASET_DESC = (
    "Golden dataset PoC UW Agent Chubb EMEA — 72 submissions sintéticas "
    "(36 Property + 36 Casualty, incluidos 12 edge cases). "
    "Cubre escenarios STP, HITL-1/2/3 y casos límite."
)

INPUT_KEYS  = ["submission_id", "channel", "line_of_business", "broker",
               "received_at", "email_raw", "attachments"]
OUTPUT_KEYS = ["extracted_data_ground_truth", "missing_fields_expected",
               "appetite_expected", "expected_hitl_trigger",
               "expected_hitl_trigger_reason", "scenario_tag", "line_of_business"]


def _base_url() -> str:
    endpoint = os.getenv("PHOENIX_COLLECTOR_ENDPOINT", "")
    return endpoint.replace("/v1/traces", "").rstrip("/")


def _headers() -> dict:
    api_key = os.getenv("PHOENIX_API_KEY", "").strip()
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


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


def dataset_exists(client: httpx.Client) -> str | None:
    """Devuelve el dataset_id si ya existe, None si no."""
    r = client.get("/v1/datasets")
    r.raise_for_status()
    for ds in r.json().get("data", []):
        if ds.get("name") == DATASET_NAME:
            return ds["id"]
    return None


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true",
                        help="Sobreescribir dataset existente sin confirmación")
    args = parser.parse_args()

    api_key = os.getenv("PHOENIX_API_KEY", "").strip()
    if not api_key:
        print("[ERROR] PHOENIX_API_KEY no definida en .env")
        sys.exit(1)

    base_url = _base_url()
    print(f"\nConectando con Phoenix: {base_url}")

    subs = load_submissions()
    print(f"Submissions cargadas: {len(subs)}")

    with httpx.Client(base_url=base_url, headers=_headers(), timeout=60) as client:

        existing_id = dataset_exists(client)
        if existing_id:
            print(f"Dataset '{DATASET_NAME}' ya existe (id={existing_id})")
            if not args.force:
                answer = input("¿Sobreescribir? [s/N]: ").strip().lower()
                if answer != "s":
                    print("Cancelado.")
                    return
            action = "update"
        else:
            action = "create"

        # POST /v1/datasets/upload — acepta arrays paralelas: inputs[i] / outputs[i] / metadata[i]
        inputs_list   = [{k: sub.get(k) for k in INPUT_KEYS}  for sub in subs]
        outputs_list  = [{k: sub.get(k) for k in OUTPUT_KEYS} for sub in subs]
        metadata_list = [{"submission_id": sub["submission_id"],
                          "scenario_tag":  sub.get("scenario_tag", "")} for sub in subs]

        payload = {
            "action":      action,
            "name":        DATASET_NAME,
            "description": DATASET_DESC,
            "inputs":      inputs_list,
            "outputs":     outputs_list,
            "metadata":    metadata_list,
        }

        r = client.post("/v1/datasets/upload", json=payload)
        r.raise_for_status()
        # El endpoint devuelve null — recuperamos el id con GET posterior
        r2 = client.get("/v1/datasets")
        r2.raise_for_status()
        ds = next((d for d in r2.json().get("data", []) if d.get("name") == DATASET_NAME), None)
        dataset_id = ds["id"] if ds else "desconocido"

        print(f"\n[OK] Dataset '{DATASET_NAME}' subido con {len(subs)} ejemplos.")
        print(f"     Dataset ID: {dataset_id}")
        print(f"     Ver en Phoenix: {base_url}/datasets/{dataset_id}")


if __name__ == "__main__":
    main()
