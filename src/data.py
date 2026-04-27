import sys
from pathlib import Path

import pyarrow.parquet as pq

import db
from schema import PERSONA_COLUMNS

DATASET_ID = "nvidia/Nemotron-Personas-Korea"
BATCH_SIZE = 50_000

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def data_dir() -> Path:
    p = PROJECT_ROOT / "data"
    p.mkdir(parents=True, exist_ok=True)
    return p


def db_path() -> Path:
    return data_dir() / "personas.db"


def parquet_dir() -> Path:
    return data_dir() / "parquet"


def _log(msg: str) -> None:
    print(f"[korean-persona-mcp] {msg}", file=sys.stderr, flush=True)


def ensure_dataset() -> Path:
    """Download dataset and ingest into SQLite if not already present.

    Returns the path to the SQLite database. Idempotent: skips download +
    ingest when the database already has rows.
    """
    path = db_path()
    if path.exists():
        with db.connect(path) as conn:
            db.create_schema(conn)
            count = db.row_count(conn)
        if count > 0:
            _log(f"using cached database at {path} ({count:,} rows)")
            return path
        _log(f"empty database at {path}, re-ingesting")

    pq_dir = _download_parquet()
    _ingest_parquet(path, pq_dir)
    return path


def _download_parquet() -> Path:
    """Download dataset parquet files via huggingface_hub.snapshot_download."""
    from huggingface_hub import snapshot_download

    pq_dir = parquet_dir()
    _log(f"downloading {DATASET_ID} into {pq_dir}")
    snapshot_download(
        repo_id=DATASET_ID,
        repo_type="dataset",
        local_dir=str(pq_dir),
        allow_patterns=["*.parquet"],
    )
    files = sorted(pq_dir.rglob("*.parquet"))
    _log(f"downloaded {len(files)} parquet file(s)")
    if not files:
        raise RuntimeError(f"no parquet files found under {pq_dir}")
    return pq_dir


def _ingest_parquet(db_file: Path, pq_dir: Path) -> None:
    files = sorted(pq_dir.rglob("*.parquet"))
    with db.connect(db_file) as conn:
        db.apply_ingest_pragmas(conn)
        db.create_schema(conn)
        total = 0
        for f in files:
            _log(f"ingesting {f.name}")
            pf = pq.ParquetFile(f)
            for batch in pf.iter_batches(batch_size=BATCH_SIZE):
                rows = batch.to_pylist()
                clean = [{k: r.get(k) for k in PERSONA_COLUMNS} for r in rows]
                db.insert_rows(conn, clean)
                conn.commit()
                total += len(clean)
                _log(f"  inserted {total:,} rows total")

        _log("building FTS5 index (this may take a few minutes)...")
        db.rebuild_fts(conn)
        _log("FTS5 index built")
    _log(f"ingest complete: {db_file}")
