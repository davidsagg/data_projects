"""Airflow DAG for automated MusicDNA AI indexing pipeline.

Scans /data/raw for new audio files and runs the full ingestion,
feature extraction, embedding and catalog update pipeline.
"""

import glob
import json
import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

# Configuracao padrao das tasks:
default_args = {
    "owner": "musicdna",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=2),
    "start_date": datetime(2026, 1, 1),
}

RAW_DIR = "/workspace/data/raw"
PROCESSED_DIR = "/workspace/data/processed"
EMBEDDINGS_DIR = "/workspace/data/embeddings"
CHROMA_DIR = "/workspace/data/embeddings/chroma"
DB_PATH = "/workspace/data/catalog.duckdb"
INDEXED_LOG = "/workspace/data/.indexed_files.json"


def _load_indexed() -> set:
    if os.path.exists(INDEXED_LOG):
        return set(json.loads(open(INDEXED_LOG).read()))
    return set()


def _save_indexed(indexed: set) -> None:
    with open(INDEXED_LOG, "w") as f:
        json.dump(list(indexed), f)


# ---------------------------------------------------------------------------
# Task functions
# ---------------------------------------------------------------------------


def scan_new_files_fn(**context):
    """Detecta arquivos novos em /data/raw/ nao indexados."""
    indexed = _load_indexed()
    patterns = ["*.wav", "*.mp3", "*.flac"]
    all_files = []
    for p in patterns:
        all_files.extend(glob.glob(os.path.join(RAW_DIR, p)))
    new_files = [f for f in all_files if f not in indexed]
    context["ti"].xcom_push(key="new_files", value=new_files)
    print(f"Arquivos novos encontrados: {len(new_files)}")
    return new_files


def ingest_audio_fn(**context):
    """Executa M1 AudioIngestionPipeline para cada arquivo novo."""
    import sys

    sys.path.insert(0, "/workspace/src")
    from src.audio.ingestion import AudioIngestionPipeline
    from src.infrastructure.mlflow_tracker import MLflowTracker

    new_files = context["ti"].xcom_pull(key="new_files", task_ids="scan_new_files")
    if not new_files:
        print("Sem arquivos novos para ingerir.")
        context["ti"].xcom_push(key="job_ids", value=[])
        return
    pipeline = AudioIngestionPipeline(PROCESSED_DIR, DB_PATH)
    tracker = MLflowTracker()
    job_ids = []
    for fpath in new_files:
        tracker.start_run(f"ingest_{os.path.basename(fpath)}")
        try:
            job_id = pipeline.ingest(fpath)
            job_ids.append({"job_id": job_id, "file": fpath})
            tracker.log_metrics({"ingest_ok": 1.0})
            tracker.end_run("FINISHED")
        except Exception as e:
            tracker.log_metrics({"ingest_ok": 0.0})
            tracker.end_run("FAILED")
            print(f"Erro ao ingerir {fpath}: {e}")
    context["ti"].xcom_push(key="job_ids", value=job_ids)


def extract_features_fn(**context):
    """Executa M2 FeatureExtractor para cada job_id."""
    import sys
    import time

    sys.path.insert(0, "/workspace/src")
    from src.audio.features import FeatureExtractor
    from src.infrastructure.mlflow_tracker import MLflowTracker

    job_ids = context["ti"].xcom_pull(key="job_ids", task_ids="ingest_audio") or []
    extractor = FeatureExtractor(EMBEDDINGS_DIR)
    tracker = MLflowTracker()
    for item in job_ids:
        job_id = item["job_id"]
        processed_path = os.path.join(PROCESSED_DIR, f"{job_id}.wav")
        tracker.start_run(f"extract_{job_id[:8]}")
        t0 = time.time()
        try:
            features = extractor.extract_acoustic(job_id, processed_path)
            tracker.log_metrics({"processing_time_sec": time.time() - t0})
            if "bpm" in features:
                tracker.log_metrics({"bpm_detected": features["bpm"]})
            tracker.end_run("FINISHED")
        except Exception as e:
            tracker.end_run("FAILED")
            print(f"Erro ao extrair features de {job_id}: {e}")


def index_embeddings_fn(**context):
    """Executa embedding CLAP e indexacao no ChromaDB (M2+M3)."""
    import sys

    sys.path.insert(0, "/workspace/src")
    from src.audio.features import FeatureExtractor
    from src.matching.catalog_store import CatalogStore
    from src.matching.vector_store import VectorStore

    job_ids = context["ti"].xcom_pull(key="job_ids", task_ids="ingest_audio") or []
    extractor = FeatureExtractor(EMBEDDINGS_DIR)
    vs = VectorStore(persist_dir=CHROMA_DIR)
    cat = CatalogStore(db_path=DB_PATH)
    for item in job_ids:
        job_id = item["job_id"]
        processed_path = os.path.join(PROCESSED_DIR, f"{job_id}.wav")
        try:
            embedding = extractor.extract_embedding(job_id, processed_path)
            meta_rows = cat.filter()
            meta = next((r for r in meta_rows if r.get("job_id") == job_id), {})
            index_meta = {
                "title": meta.get("title", ""),
                "genre": meta.get("genre", ""),
                "bpm": float(meta.get("bpm_manual", 0) or 0),
                "mood": meta.get("mood", ""),
                "key": "",
            }
            vs.index(job_id, embedding, index_meta)
            print(f"Indexado: {job_id}")
        except Exception as e:
            print(f"Erro ao indexar {job_id}: {e}")


def update_catalog_fn(**context):
    """Marca arquivos como indexados no log e atualiza status no DuckDB."""
    import duckdb

    job_ids = context["ti"].xcom_pull(key="job_ids", task_ids="ingest_audio") or []
    indexed = _load_indexed()
    db = duckdb.connect(DB_PATH)
    for item in job_ids:
        indexed.add(item["file"])
        try:
            db.execute(
                "UPDATE catalog SET status='indexed' WHERE job_id=?",
                [item["job_id"]],
            )
        except Exception:
            pass
    _save_indexed(indexed)
    print(f"Catalog atualizado. Total indexado: {len(indexed)} arquivos.")


# ---------------------------------------------------------------------------
# DAG definition
# ---------------------------------------------------------------------------

with DAG(
    dag_id="musicdna_pipeline",
    default_args=default_args,
    schedule_interval="@hourly",
    catchup=False,
    description="Pipeline de indexacao automatica do MusicDNA AI",
    tags=["musicdna", "audio", "ml"],
) as dag:

    t1 = PythonOperator(task_id="scan_new_files", python_callable=scan_new_files_fn)
    t2 = PythonOperator(task_id="ingest_audio", python_callable=ingest_audio_fn)
    t3 = PythonOperator(
        task_id="extract_features", python_callable=extract_features_fn
    )
    t4 = PythonOperator(
        task_id="index_embeddings", python_callable=index_embeddings_fn
    )
    t5 = PythonOperator(task_id="update_catalog", python_callable=update_catalog_fn)

    t1 >> t2 >> t3 >> t4 >> t5
