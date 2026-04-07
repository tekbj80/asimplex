# Streamlit chat agent package — folder structure and architecture

This file is the working project plan (copied from the architecture design). Update it as the project evolves.

## Phased rollout (how we proceed)

1. **Done**: Package scaffold + **chat UI and map** (`app/main.py`, `chat_ui.py`, `session_state.py`, `map_location.py`, `schemas/location.py`). Run: `pip install -e .` then `streamlit run src/aisim_chat/app/main.py`.
2. **Next**: Wire session state and agent context (no full agent until we choose tools).
3. **Later**: Agent **step-by-step** — runner, prompts, then one tool at a time (CSV → residual → …).
4. **Legacy code**: Keep mature **simulation logic** outside or under `domain/` as a thin adapter (`simulator.py` calling your existing package); do not rewrite it in the UI layer.

---

## Design goals

- **Separation of concerns**: UI (Streamlit) does not embed business logic; the agent orchestrates **tools** that call **domain** code.
- **Testability**: Pure functions for math/simulation; tools are thin wrappers with clear I/O contracts.
- **Extensibility**: New tools or a second battery model plug in without rewriting the chat loop.
- **Demonstrable RAG**: Battery datasheets live in a **portfolio corpus**; embeddings + retrieval support both **grounded answers** (citations) and **structured simulation inputs** mapped from retrieved specs.

## Recommended top-level layout

```text
aisim-chat/                          # or your chosen package name
├── pyproject.toml                   # deps: streamlit, pandas, numpy, pydantic;
│                                    # agent SDK; RAG (e.g. langchain + chroma + pypdf, or llama-index)
├── README.md
├── .env.example                     # API keys; never commit secrets
├── src/
│   └── aisim_chat/                  # importable package
│       ├── __init__.py
│       ├── config.py                # settings from env (model name, paths, limits, RAG paths)
│       ├── app/
│       │   ├── __init__.py
│       │   ├── main.py              # streamlit entry: st.set_page_config, routing
│       │   ├── chat_ui.py           # message list, input, file upload widget
│       │   ├── session_state.py     # typed helpers for chat history, uploaded files, coords
│       │   └── map_location.py      # map picker (folium/pydeck) → lat/lon + optional address
│       ├── agent/
│       │   ├── __init__.py
│       │   ├── runner.py            # single entry: user_message + context → agent reply + tool calls
│       │   ├── prompts.py           # system prompt + stage hints (CSV → analyze → decide → sim)
│       │   ├── state.py             # optional: conversation / pipeline state if using a graph
│       │   └── backends/            # optional: openai.py, anthropic.py thin adapters
│       ├── rag/                     # RAG layer (no Streamlit imports)
│       │   ├── __init__.py
│       │   ├── chunking.py          # load PDF/text → chunks + stable chunk ids + page metadata
│       │   ├── embeddings.py        # embedding client wrapper (local sentence-transformers vs API)
│       │   ├── vector_store.py      # create/load/persist store (e.g. Chroma under data/rag_index)
│       │   ├── ingest.py            # build or update index from data/battery_portfolio
│       │   └── retrieve.py          # query → list[RetrievedChunk] with source, page, score
│       ├── tools/
│       │   ├── __init__.py          # export TOOL_REGISTRY for the agent
│       │   ├── csv_ingest.py        # tool: sniff delimiter/decimal, parse dates, return DataFrame summary
│       │   ├── load_profile.py      # tool: dtypes, nrows, describe(); validate required columns
│       │   ├── residual_load.py     # tool: residual_load = pv - load (aligns indices, units)
│       │   ├── battery_selection.py # tool: scores/heuristics → "app A" vs "app B"
│       │   ├── battery_rag.py       # tool: search_battery_portfolio(query) → snippets + citations
│       │   ├── battery_sizing.py    # tool: capacity distribution / sizing curve
│       │   ├── simulation.py        # tool: runs simulator with BatterySimParams (+ optional rag_evidence ids)
│       │   └── benchmarks.py        # tool: aggregate/compare run metrics
│       ├── domain/
│       │   ├── __init__.py
│       │   ├── csv_sniffer.py       # delimiter/decimal/date inference (no LLM)
│       │   ├── profiles.py          # normalization, resampling, column mapping
│       │   ├── residual.py          # residual_load computation
│       │   ├── battery_apps.py      # definitions of the two applications + selection rules
│       │   ├── battery_params.py    # pydantic BatterySimParams; validation ranges from engineering rules
│       │   ├── sizing.py            # battery sizing math
│       │   ├── simulator.py         # core simulation (callable from tools)
│       │   └── metrics.py           # benchmark KPIs shared by simulation + analysis
│       ├── io/
│       │   ├── __init__.py
│       │   └── uploads.py           # save Streamlit uploads to temp dir; return paths + metadata
│       └── schemas/
│           ├── __init__.py
│           ├── chat.py              # message roles, attachments
│           ├── location.py          # lat, lon, label
│           ├── rag.py               # RetrievedChunk, citation payload for UI
│           └── results.py           # pydantic models for tool outputs (easy to show in UI)
├── scripts/
│   └── build_rag_index.py           # thin CLI: calls rag.ingest with paths from config
├── tests/
│   ├── domain/                      # unit tests for pure logic
│   ├── tools/                       # integration tests with small fixture CSVs
│   └── rag/                         # retrieval tests on tiny fixture PDFs or mocked store
└── data/
    ├── fixtures/                    # tiny CSV samples (various separators/decimals)
    ├── battery_portfolio/           # authoritative battery datasheets (PDF/MD); large files gitignored
    │   └── README.md                # how to add datasheets + rerun index build
    └── rag_index/                   # persisted vector DB + metadata (gitignored)
```

**Why `src/aisim_chat`**: avoids accidental imports from the repo root and matches standard packaging practice.

## How this maps to your 10 steps

| Step | Where it lives |
|------|----------------|
| 1 Chat | `app/chat_ui.py` + `agent/runner.py` |
| 2 Location | `app/map_location.py` + `schemas/location.py`; store in session state and inject into agent context |
| 3–4 CSV + stats | `tools/csv_ingest.py`, `tools/load_profile.py` → `domain/csv_sniffer.py`, `domain/profiles.py` |
| 5 Residual load | `tools/residual_load.py` → `domain/residual.py` |
| 6 Battery app choice | `tools/battery_selection.py` → `domain/battery_apps.py` |
| 7 Sizing / capacities | `tools/battery_sizing.py` → `domain/sizing.py` |
| 8 Simulation | `tools/battery_rag.py` (retrieve specs) → `domain/battery_params.py` → `tools/simulation.py` → `domain/simulator.py` |
| 9 Benchmarks | `tools/benchmarks.py` → `domain/metrics.py` |
| 10 Recommendation | Agent prompt + `agent/prompts.py` synthesis; cite RAG sources when comparing battery options |

## Battery portfolio + RAG (demo-friendly)

**Corpus**: Place vendor datasheets (PDF, optional Markdown) under `data/battery_portfolio/`. Treat this folder as the **source of truth** for text available to retrieval; keep large binaries out of git via `.gitignore` and document how to obtain or drop files in `data/battery_portfolio/README.md`.

**Index build (offline)**: `scripts/build_rag_index.py` → `rag/ingest.py`: extract text (e.g. pypdf), chunk with overlap, attach metadata (`source_file`, `page`, `chunk_id`). Embed and persist to `data/rag_index/` (gitignored). Re-run when datasheets change.

**Runtime retrieval**: Agent tool `tools/battery_rag.py` calls `rag/retrieve.py` and returns **top-k chunks with citations** (file + page + snippet). The UI can show “Sources” for the demo.

**Populating the simulation**: Define a small **structured** `domain/battery_params.py` (e.g. usable_energy_kwh, max_power_kw, efficiency, DoD limits) that `domain/simulator.py` actually consumes. The agent uses retrieved text to **fill or adjust** `BatterySimParams`; validated params are passed to `tools/simulation.py`.

## Streamlit + map

- Use **streamlit-folium** or **pydeck** for click-to-pick coordinates; persist `lat`, `lon` (and optional geocoded label) in `app/session_state.py`.
- Pass location into the agent as structured context (not only natural language) so tools can use it later.

## Decisions to lock in when you implement

1. **Agent framework**: LangGraph, LangChain tools, or OpenAI Assistants — folder layout stays the same; only `agent/runner.py` and deps change.
2. **Simulation**: Optional deps in `pyproject.toml` under `[project.optional-dependencies]`; lazy-import in `domain/simulator.py`. **Prefer wrapping legacy simulation** instead of reimplementing.
3. **RAG stack**: One consistent stack for embeddings + vector store; keep interfaces in `rag/embeddings.py` and `rag/vector_store.py`.
4. **Params from datasheets**: Prefer validated `BatterySimParams` over passing raw strings into the simulator.

## Optional additions (later)

- `notebooks/` for exploratory analysis
- `docs/` for internal architecture notes (only if you want them)
