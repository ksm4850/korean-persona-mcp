import sqlite3
from pathlib import Path
from typing import Any

from schema import (
    FILTERABLE_STR_FIELDS,
    GroupByField,
    PERSONA_COLUMNS,
    SEARCHABLE_TEXT_FIELDS,
    SUMMARY_COLUMNS,
)

TABLE = "personas"
FTS_TABLE = "personas_fts"
MAX_LIMIT = 100

# 검색/필터 가능 인구통계 컬럼 (B-tree 인덱스 대상)
DEMO_COLUMNS: tuple[str, ...] = (
    "sex",
    "age",
    "marital_status",
    "military_status",
    "family_type",
    "housing_type",
    "education_level",
    "bachelors_field",
    "occupation",
    "district",
    "province",
    "country",
)

# FTS5 인덱싱 대상 텍스트 컬럼 (schema.SEARCHABLE_TEXT_FIELDS와 동일)
FTS_COLUMNS: tuple[str, ...] = SEARCHABLE_TEXT_FIELDS


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def apply_ingest_pragmas(conn: sqlite3.Connection) -> None:
    """대량 인제스트 가속용 PRAGMA. 인제스트 직전에 호출."""
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA cache_size=-262144")  # 256MB


def create_schema(conn: sqlite3.Connection) -> None:
    cols_sql = ",\n  ".join(
        f"{col} INTEGER" if col == "age" else f"{col} TEXT"
        for col in PERSONA_COLUMNS
    )
    conn.execute(
        f"CREATE TABLE IF NOT EXISTS {TABLE} (\n  {cols_sql},\n  PRIMARY KEY (uuid)\n)"
    )
    for col in DEMO_COLUMNS:
        conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{TABLE}_{col} ON {TABLE}({col})")

    fts_cols = ", ".join(FTS_COLUMNS)
    conn.execute(
        f"CREATE VIRTUAL TABLE IF NOT EXISTS {FTS_TABLE} USING fts5("
        f"  {fts_cols},"
        f"  content='{TABLE}', content_rowid='rowid',"
        f"  tokenize='unicode61 remove_diacritics 2',"
        f"  prefix='2 3 4'"
        f")"
    )
    conn.commit()


def rebuild_fts(conn: sqlite3.Connection) -> None:
    """personas 전체를 personas_fts에 일괄 재빌드 (deferred build).

    매 배치마다 FTS에 INSERT하는 것보다 훨씬 빠름. 인제스트 끝난 뒤 한 번 호출.
    """
    fts_cols = ", ".join(FTS_COLUMNS)
    conn.execute(f"INSERT INTO {FTS_TABLE}({FTS_TABLE}) VALUES('delete-all')")
    conn.execute(
        f"INSERT INTO {FTS_TABLE}(rowid, {fts_cols}) "
        f"SELECT rowid, {fts_cols} FROM {TABLE}"
    )
    conn.commit()


def row_count(conn: sqlite3.Connection) -> int:
    cur = conn.execute(f"SELECT COUNT(*) FROM {TABLE}")
    return cur.fetchone()[0]


def insert_rows(conn: sqlite3.Connection, rows: list[dict[str, Any]]) -> None:
    """personas 본 테이블에만 INSERT. FTS 인덱스는 rebuild_fts로 일괄 빌드."""
    placeholders = ",".join(["?"] * len(PERSONA_COLUMNS))
    cols = ",".join(PERSONA_COLUMNS)
    sql = f"INSERT OR REPLACE INTO {TABLE} ({cols}) VALUES ({placeholders})"
    payload = [tuple(_coerce(r.get(c)) for c in PERSONA_COLUMNS) for r in rows]
    conn.executemany(sql, payload)


def _coerce(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bytes)):
        return value
    return str(value)


def _build_where(
    filters: dict[str, Any], prefix: str = ""
) -> tuple[str, list[Any]]:
    p = f"{prefix}." if prefix else ""
    clauses: list[str] = []
    params: list[Any] = []
    for field in FILTERABLE_STR_FIELDS:
        v = filters.get(field)
        if v is not None:
            clauses.append(f"{p}{field} = ?")
            params.append(v)
    age_min = filters.get("age_min")
    age_max = filters.get("age_max")
    if age_min is not None:
        clauses.append(f"{p}age >= ?")
        params.append(age_min)
    if age_max is not None:
        clauses.append(f"{p}age <= ?")
        params.append(age_max)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return where, params


def random_personas(
    conn: sqlite3.Connection, n: int, filters: dict[str, Any]
) -> list[dict[str, Any]]:
    where, params = _build_where(filters)
    sql = f"SELECT * FROM {TABLE} {where} ORDER BY RANDOM() LIMIT ?"
    cur = conn.execute(sql, [*params, n])
    return [dict(r) for r in cur.fetchall()]


def search_personas(
    conn: sqlite3.Connection,
    query: str | None,
    fields: list[str] | None,
    filters: dict[str, Any],
    limit: int,
    full: bool,
) -> dict[str, Any]:
    """FTS5 자유 텍스트 + 인구통계 필터 결합 검색.

    - query 있음: FTS5 MATCH, bm25() 점수 오름차순 정렬
    - query 없음: 인구통계 필터만 (LIMIT 순)
    - fields 지정: 해당 FTS 컬럼만 매칭 (`{col1 col2} : (query)`)
    - full=True: 26개 전체 컬럼, False: SUMMARY_COLUMNS만
    """
    limit = max(1, min(int(limit), MAX_LIMIT))

    if fields:
        invalid = [f for f in fields if f not in FTS_COLUMNS]
        if invalid:
            raise ValueError(f"invalid FTS fields: {invalid}")

    select_cols = "p.*" if full else ", ".join(f"p.{c}" for c in SUMMARY_COLUMNS)
    where_demo, demo_params = _build_where(filters, prefix="p")

    if query:
        if fields:
            match_expr = "{" + " ".join(fields) + "} : (" + query + ")"
        else:
            match_expr = query

        and_demo = (
            "AND " + where_demo.removeprefix("WHERE ") if where_demo else ""
        )
        sql = f"""
            SELECT {select_cols}, bm25({FTS_TABLE}) AS rank
            FROM {FTS_TABLE} f
            JOIN {TABLE} p ON p.rowid = f.rowid
            WHERE {FTS_TABLE} MATCH ?
            {and_demo}
            ORDER BY rank
            LIMIT ?
        """
        params: list[Any] = [match_expr, *demo_params, limit]
    else:
        sql = f"""
            SELECT {select_cols}
            FROM {TABLE} p
            {where_demo}
            LIMIT ?
        """
        params = [*demo_params, limit]

    rows = conn.execute(sql, params).fetchall()
    results = [dict(r) for r in rows]
    return {"count": len(results), "results": results}


def get_by_uuid(conn: sqlite3.Connection, uuid: str) -> dict[str, Any] | None:
    cur = conn.execute(f"SELECT * FROM {TABLE} WHERE uuid = ?", [uuid])
    row = cur.fetchone()
    return dict(row) if row else None


def aggregate(
    conn: sqlite3.Connection, group_by: GroupByField, filters: dict[str, Any],limit:int = None
) -> dict[str, int]:
    if group_by not in PERSONA_COLUMNS:
        raise ValueError(f"invalid group_by field: {group_by}")
    where, params = _build_where(filters)
    sql = (
        f"SELECT {group_by} AS k, COUNT(*) AS c FROM {TABLE} "
        f"{where} GROUP BY {group_by} ORDER BY c DESC"
    )
    if limit is not None:
        sql += " LIMIT ?"
        params = (*params, limit)
    cur = conn.execute(sql, params)
    return {str(r["k"]): r["c"] for r in cur.fetchall()}
