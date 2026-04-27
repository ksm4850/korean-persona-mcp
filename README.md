# korean-persona-mcp

An MCP server that exposes the [NVIDIA Nemotron-Personas-Korea](https://huggingface.co/datasets/nvidia/Nemotron-Personas-Korea) dataset (1M Korean personas, CC BY 4.0) as Claude/AI tools.

## Tools

- `get_random_personas(count, filters?)` — random sample (1–50)
- `search_personas(query?, fields?, filters?, limit, full)` — FTS5 (`bm25` ranking) + demographic filter combined search. Korean short keywords: use prefix wildcard (e.g., `등산*`).
- `get_persona_by_uuid(uuid)` — single record lookup
- `get_demographic_stats(group_by, filters?)` — distribution counts

Demographic filter/group_by fields: `sex`, `marital_status`, `military_status`, `family_type`, `housing_type`, `education_level`, `bachelors_field`, `occupation`, `district`, `province`, `country`, `age_min`/`age_max`.

> ℹ️ `province` raw values (17, with inconsistent labeling in the dataset): `경기, 서울, 부산, 경상남, 인천, 경상북, 대구, 충청남, 전라남, 전북, 충청북, 강원, 대전, 광주, 울산, 제주, 세종`. The tool automatically maps common forms — `서울특별시`, `서울`, `전라남도`, `전남`, `경상북도`, `경북` etc. all resolve to the correct raw value.

FTS5 indexed text columns: `professional_persona`, `sports_persona`, `arts_persona`, `travel_persona`, `culinary_persona`, `family_persona`, `cultural_background`, `skills_and_expertise`, `hobbies_and_interests`, `career_goals_and_ambitions`.

## Setup

```bash
uv sync
```

The first time the server starts (or via `--bootstrap`), it downloads the dataset Parquet files into `data/parquet/` and ingests them into `data/personas.db` (both inside the project root, gitignored). Download is large (~GB) and slow (~minutes); subsequent starts skip this step.

```bash
uv run main.py --bootstrap
```

## Running

```bash
# stdio (Claude Desktop / Claude Code)
uv run main.py

# HTTP (streamable-http on 127.0.0.1:8080)
uv run main.py --http

# Custom host/port
uv run main.py --http --host 0.0.0.0 --port 9000
```

## Claude Desktop config

Add to `claude_desktop_config.json`:

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

## HTTP testing

```bash
npx @modelcontextprotocol/inspector
# Connect to http://127.0.0.1:8080/mcp
```

## Project layout

```
korean-persona-mcp/
├── main.py              # CLI entry point
├── pyproject.toml
├── src/
│   ├── schema.py        # Pydantic models + field whitelists
│   ├── db.py            # SQLite query layer
│   ├── data.py          # HF download + ingest
│   └── server.py        # FastMCP tools
└── README.md
```

## Dataset attribution

Data: NVIDIA, *Nemotron-Personas-Korea*, released under CC BY 4.0. See the dataset page for full citation and limitations (synthetic data; adults only; no gender identity beyond biological sex).
