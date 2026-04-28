# korean-persona-mcp

[NVIDIA Nemotron-Personas-Korea](https://huggingface.co/datasets/nvidia/Nemotron-Personas-Korea) 데이터셋(한국인 페르소나 100만 건, CC BY 4.0)을 Claude/AI 도구로 노출하는 MCP 서버입니다.

## 제공 도구

- `get_random_personas(count, filters?)` — 무작위 샘플 (1–50건)
- `search_personas(query?, fields?, filters?, limit, full)` — FTS5(`bm25` 랭킹) + 인구통계 필터 복합 검색. 한국어 단어 검색 시 접두사 와일드카드 사용 권장 (예: `등산*`)
- `get_persona_by_uuid(uuid)` — UUID로 단일 레코드 조회
- `get_demographic_stats(group_by, filters?)` — 인구통계 분포 집계

인구통계 필터/group_by 필드: `sex`, `marital_status`, `military_status`, `family_type`, `housing_type`, `education_level`, `bachelors_field`, `occupation`, `district`, `province`, `country`, `age_min`/`age_max`

> ℹ️ `province` 원본 값(17개, 데이터셋 내 표기 불일치): `경기, 서울, 부산, 경상남, 인천, 경상북, 대구, 충청남, 전라남, 전북, 충청북, 강원, 대전, 광주, 울산, 제주, 세종`. 일반적인 형식은 자동 변환됩니다 — `서울특별시`, `서울`, `전라남도`, `전남`, `경상북도`, `경북` 등 모두 올바른 원본 값으로 매핑됩니다.

FTS5 인덱싱 텍스트 컬럼: `professional_persona`, `sports_persona`, `arts_persona`, `travel_persona`, `culinary_persona`, `family_persona`, `cultural_background`, `skills_and_expertise`, `hobbies_and_interests`, `career_goals_and_ambitions`

## 설치

```bash
uv sync
```

서버를 처음 시작하거나 `--bootstrap` 옵션을 사용하면, 데이터셋 Parquet 파일을 `data/parquet/`에 다운로드하고 `data/personas.db`에 적재합니다(모두 프로젝트 루트 하위, gitignore 처리됨). 다운로드 용량이 크고(~GB) 시간이 걸리지만(~수 분), 이후 실행 시에는 이 단계를 건너뜁니다.

```bash
uv run main.py --bootstrap
```

## 실행

```bash
# stdio 모드 (Claude Desktop / Claude Code)
uv run main.py

# HTTP 모드 (streamable-http, 127.0.0.1:8080)
uv run main.py --http

# 호스트/포트 지정
uv run main.py --http --host 0.0.0.0 --port 9000
```

## Claude Desktop 설정

`claude_desktop_config.json`에 아래 내용을 추가합니다:

```json
{
  "mcpServers": {
    "korean-persona": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/korean-persona-mcp",
        "run",
        "main.py"
      ]
    }
  }
}
```

## HTTP 테스트

```bash
npx @modelcontextprotocol/inspector
# http://127.0.0.1:8080/mcp 에 연결
```

## 프로젝트 구조

```
korean-persona-mcp/
├── main.py              # CLI 진입점
├── pyproject.toml
├── src/
│   ├── schema.py        # Pydantic 모델 + 필드 화이트리스트
│   ├── db.py            # SQLite 쿼리 레이어
│   ├── data.py          # HuggingFace 다운로드 + 적재
│   └── server.py        # FastMCP 도구 정의
└── README.md
```

## 데이터셋 출처

데이터: NVIDIA, *Nemotron-Personas-Korea*, CC BY 4.0 라이선스. 전체 인용 및 제한 사항(합성 데이터, 성인 한정, 생물학적 성별만 포함)은 데이터셋 페이지를 참고하세요.