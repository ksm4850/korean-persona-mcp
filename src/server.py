import re
from typing import Any

from mcp.server.fastmcp import FastMCP

import db
from data import db_path, ensure_dataset
from schema import GroupByField, PersonaFilters, SearchableTextField

mcp = FastMCP("korean-persona")

_UUID_RE = re.compile(r"^[0-9a-f]{32}$", re.IGNORECASE)


def _conn():
    return db.connect(db_path())


def _filters_dict(filters: PersonaFilters | None) -> dict[str, Any]:
    if filters is None:
        return {}
    return filters.model_dump(exclude_none=True)


@mcp.tool()
def get_random_personas(
    count: int = 1,
    filters: PersonaFilters | None = None,
) -> list[dict[str, Any]]:
    """한국인 페르소나를 무작위로 샘플링합니다.

    NVIDIA Nemotron-Personas-Korea 데이터셋(100만 건)에서 임의의 페르소나를
    `count`개 반환합니다. 롤플레이, 합성 데이터 생성, 테스트용 다양한 페르소나
    확보에 적합합니다.

    Args:
        count: 가져올 페르소나 개수 (1~50). 기본값 1.
        filters: 선택적 필터. 성별/지역/나이대 등으로 모집단을 좁힌 뒤 샘플링.
            예: {"province": "서울특별시", "age_min": 30, "age_max": 49}

    Returns:
        페르소나 dict 리스트. 각 항목은 26개 필드(인구통계 + 페르소나 텍스트)를 포함.
    """
    if not 1 <= count <= 50:
        raise ValueError("count must be between 1 and 50")
    with _conn() as conn:
        return db.random_personas(conn, count, _filters_dict(filters))


@mcp.tool()
def search_personas(
    query: str | None = None,
    fields: list[SearchableTextField] | None = None,
    filters: PersonaFilters | None = None,
    limit: int = 20,
    full: bool = False,
) -> dict[str, Any]:
    """페르소나 검색. FTS5 자유 텍스트 + 인구통계 필터 결합.

    토크나이저는 `unicode61` (어절 단위 토큰화) + 2/3/4글자 prefix 인덱스를 사용합니다.
    한국어 검색에서는 `등산* AND 트로트*`처럼 prefix wildcard를 권장합니다
    (단순 키워드는 정확한 어절이 일치해야만 매칭됨).

    Args:
        query: FTS5 MATCH 표현식. None이면 텍스트 검색 없이 필터만 적용.
        fields: 검색 대상 FTS 컬럼 제한. 다음 10개 중 선택:
            professional_persona, sports_persona, arts_persona, travel_persona,
            culinary_persona, family_persona, cultural_background,
            skills_and_expertise, hobbies_and_interests, career_goals_and_ambitions.
            미지정 시 10개 컬럼 전체 매칭.
        filters: 인구통계 필터 dict (성별/지역/나이대/학력/직업 등).
        limit: 최대 반환 개수 (1~100, 기본 20).
        full: True면 26개 전체 컬럼, False면 핵심 요약 컬럼만 반환.

    Returns:
        {"count": 반환 개수, "results": 페르소나 dict 리스트}.
        query 있으면 bm25(rank) 오름차순 정렬, 없으면 LIMIT 순.

    Examples:
        - 60대 이상 여성 + 등산: query="등산*", filters={"sex":"여자","age_min":60}
        - 부산 한식당 종사자: query="한식*", filters={"province":"부산"}
        - 전남 거주: filters={"province":"전남"} or {"province":"전라남도"} (자동 변환)
        - 취미 컬럼만 검색: query="트로트*", fields=["hobbies_and_interests"]

    Note:
        province는 정식명("서울특별시")·자연 약식("전남")·정식 도명("전라남도")
        모두 자동 매핑됩니다. 데이터셋 내부값은 17종이고 일부 표기가 어색합니다
        (전라남/경상북/충청남/충청북 등). 입력은 익숙한 형태로 보내면 됩니다.
    """
    if query is not None and not query.strip():
        query = None
    with _conn() as conn:
        return db.search_personas(
            conn,
            query=query,
            fields=fields,
            filters=_filters_dict(filters),
            limit=limit,
            full=full,
        )


@mcp.tool()
def get_persona_by_uuid(uuid: str) -> dict[str, Any]:
    """UUID로 단일 페르소나를 조회합니다.

    이전 호출 결과에 포함된 `uuid` 값으로 동일한 페르소나를 다시 가져올 때 사용합니다.
    재현 가능한 테스트 시나리오를 만들 때 유용합니다.

    Args:
        uuid: 32자 16진수 문자열.

    Returns:
        해당 페르소나의 26개 필드 dict. 존재하지 않으면 에러.
    """
    if not _UUID_RE.match(uuid):
        raise ValueError("uuid must be a 32-character hex string")
    with _conn() as conn:
        row = db.get_by_uuid(conn, uuid)
    if row is None:
        raise ValueError(f"no persona found with uuid={uuid}")
    return row


@mcp.tool()
def get_demographic_stats(
    group_by: GroupByField,
    filters: PersonaFilters | None = None,
    limit:int = None,
) -> dict[str, int]:
    """특정 인구통계 필드의 분포를 집계합니다.

    `group_by`로 지정한 필드의 카테고리별 페르소나 수를 카운트가 큰 순으로 반환합니다.
    예: 시도별 인구 분포, 직업별 분포, 학력 수준 분포 등. `filters`를 함께 주면
    부분 집단 안에서의 분포(예: 서울 거주자 중 학력 분포)를 볼 수 있습니다.

    Args:
        group_by: 집계 기준 필드. 다음 중 하나:
            sex, age, marital_status, military_status, family_type,
            housing_type, education_level, bachelors_field,
            occupation, district, province.
        filters: 선택적 필터. 집계 모집단을 좁히고 싶을 때 사용.
        limit: 기본값 50, 상한 300

    Returns:
        {카테고리 값: 건수} 형태의 dict. 건수 내림차순으로 정렬됨.
    """
    limit = min(limit or 50, 300)
    with _conn() as conn:
        return db.aggregate(conn, group_by, _filters_dict(filters),limit)


def run_stdio() -> None:
    ensure_dataset()
    mcp.run()


def run_http(host: str, port: int) -> None:
    ensure_dataset()
    mcp.settings.host = host
    mcp.settings.port = port
    if host not in ("127.0.0.1", "localhost", "::1"):
        from mcp.server.transport_security import TransportSecuritySettings
        mcp.settings.transport_security = TransportSecuritySettings(
            enable_dns_rebinding_protection=False
        )
    mcp.run(transport="streamable-http")
