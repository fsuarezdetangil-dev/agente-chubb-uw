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
               "expected_hitl_trigger_reason", "scenario_tag", "line_of_business"]


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
        # La referencia (ground truth) debe viajar también en inputs["__reference"]:
        # run_langsmith_eval.py la lee desde ahí (contrato entre ambos scripts).
        inputs["__reference"] = outputs
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
