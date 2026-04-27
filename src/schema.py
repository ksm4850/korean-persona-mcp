from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

# 데이터셋 raw province 값 (17종 — 일관된 표기가 아님)
PROVINCE_RAW: tuple[str, ...] = (
    "경기", "서울", "부산", "경상남", "인천", "경상북", "대구",
    "충청남", "전라남", "전북", "충청북", "강원", "대전", "광주",
    "울산", "제주", "세종",
)

# 자연어/정식 명칭 → raw 매핑 (LLM/사용자가 자연스러운 표기를 보내도 동작하게)
PROVINCE_ALIASES: dict[str, str] = {
    # 광역시·특별시 (정식 → raw)
    "서울특별시": "서울",
    "부산광역시": "부산",
    "대구광역시": "대구",
    "인천광역시": "인천",
    "광주광역시": "광주",
    "대전광역시": "대전",
    "울산광역시": "울산",
    "세종특별자치시": "세종",
    "세종시": "세종",
    "제주특별자치도": "제주",
    "제주도": "제주",
    # 도 (정식 → raw)
    "경기도": "경기",
    "강원도": "강원",
    "강원특별자치도": "강원",
    "전라남도": "전라남",
    "전라북도": "전북",
    "전북특별자치도": "전북",
    "경상남도": "경상남",
    "경상북도": "경상북",
    "충청남도": "충청남",
    "충청북도": "충청북",
    # 자연스러운 한국어 약식 (전남/전북/경남/경북/충남/충북) → raw
    "전남": "전라남",
    "경남": "경상남",
    "경북": "경상북",
    "충남": "충청남",
    "충북": "충청북",
    # 전북은 이미 raw와 동일
}


def normalize_province(value: str | None) -> str | None:
    if value is None:
        return None
    return PROVINCE_ALIASES.get(value, value)

Sex = Literal["남자", "여자"]
MaritalStatus = Literal["배우자있음", "미혼", "사별", "이혼"]
MilitaryStatus = Literal["비현역", "현역"]

GroupByField = Literal[
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
]

SearchableTextField = Literal[
    "professional_persona",
    "sports_persona",
    "arts_persona",
    "travel_persona",
    "culinary_persona",
    "family_persona",
    "cultural_background",
    "skills_and_expertise",
    "hobbies_and_interests",
    "career_goals_and_ambitions",
]

SEARCHABLE_TEXT_FIELDS: tuple[str, ...] = (
    "professional_persona",
    "sports_persona",
    "arts_persona",
    "travel_persona",
    "culinary_persona",
    "family_persona",
    "cultural_background",
    "skills_and_expertise",
    "hobbies_and_interests",
    "career_goals_and_ambitions",
)

# full=False 일 때 반환할 핵심 요약 컬럼
SUMMARY_COLUMNS: tuple[str, ...] = (
    "uuid",
    "sex",
    "age",
    "province",
    "district",
    "occupation",
    "education_level",
    "persona",
)

FILTERABLE_STR_FIELDS: tuple[str, ...] = (
    "sex",
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


class PersonaFilters(BaseModel):
    """페르소나 검색용 인구통계 필터. 모든 필드는 exact-match."""

    sex: Optional[Sex] = None
    marital_status: Optional[MaritalStatus] = None
    military_status: Optional[MilitaryStatus] = None
    family_type: Optional[str] = None
    housing_type: Optional[str] = None
    education_level: Optional[str] = None
    bachelors_field: Optional[str] = None
    occupation: Optional[str] = None
    district: Optional[str] = Field(
        default=None,
        description="시군구 (자유 텍스트, 약 252종). 정확한 명칭 일치 필요.",
    )
    province: Optional[str] = Field(
        default=None,
        description=(
            "시도 (17종). 정식명/약식 모두 자동 변환됩니다:"
            " '서울특별시'·'서울', '경기도'·'경기', '전라남도'·'전남', '경상북도'·'경북' 등."
            " 데이터셋 내부값은 어색한 표기가 일부 있음 (전라남/경상북/충청남/충청북 등 3글자)."
        ),
    )

    @field_validator("province", mode="before")
    @classmethod
    def _norm_province(cls, v):
        return normalize_province(v) if isinstance(v, str) else v
    country: Optional[str] = None
    age_min: Optional[int] = Field(default=None, ge=19, le=99)
    age_max: Optional[int] = Field(default=None, ge=19, le=99)


class Persona(BaseModel):
    """한국인 페르소나 단일 레코드 (총 26개 필드).

    NVIDIA Nemotron-Personas-Korea 데이터셋의 한 행에 대응. 필드 순서는
    `personas` 테이블 DDL과 일치 (식별자 → 페르소나 서술 → 리스트 → 인구통계).
    """

    # 식별자 -------------------------------------------------------------------
    uuid: str = Field(description="32자 hex 문자열 (대시 없음)")

    # 페르소나 서술 (긴 한국어 텍스트) ------------------------------------------
    persona: str = Field(description="핵심 1~2문장 요약")
    professional_persona: str = Field(description="직업/업무 페르소나")
    sports_persona: str = Field(description="스포츠/운동 페르소나")
    arts_persona: str = Field(description="예술/문화 페르소나")
    travel_persona: str = Field(description="여행 페르소나")
    culinary_persona: str = Field(description="식문화/요리 페르소나")
    family_persona: str = Field(description="가족 관계 페르소나")
    cultural_background: str = Field(description="문화·성장 배경 서술")
    skills_and_expertise: str = Field(description="보유 기술/전문성 서술")
    hobbies_and_interests: str = Field(description="취미·관심사 서술")
    career_goals_and_ambitions: str = Field(description="향후 목표/포부")

    # 리스트 (JSON 배열 형태의 문자열) ------------------------------------------
    skills_and_expertise_list: str = Field(description="스킬 키워드 JSON 배열")
    hobbies_and_interests_list: str = Field(description="취미 키워드 JSON 배열")

    # 인구통계 -----------------------------------------------------------------
    sex: str = Field(description="성별: 남자 / 여자")
    age: int = Field(description="나이 (정수, 19~99)")
    marital_status: str = Field(
        description="결혼상태 (4종: 배우자있음 / 미혼 / 사별 / 이혼)"
    )
    military_status: str = Field(description="병역상태 (비현역 / 현역)")
    family_type: str = Field(description="가구 유형 (39종)")
    housing_type: str = Field(description="주거 형태 (6종)")
    education_level: str = Field(description="최종 학력 (7종)")
    bachelors_field: str = Field(description="학사 전공 분야")
    occupation: str = Field(description="직업 (자유 텍스트)")
    district: str = Field(description="시군구")
    province: str = Field(description="시도 (17종)")
    country: str = Field(description="국가 (단일값: '대한민국')")


PERSONA_COLUMNS: tuple[str, ...] = tuple(Persona.model_fields.keys())
