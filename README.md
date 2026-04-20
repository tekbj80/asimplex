# asimplex

Minimal Python repository scaffold using a `src/` layout.

## Quick start

```bash
python -m venv .venv
. .venv/Scripts/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e ".[dev]"
pytest
```

## Streamlit app layout

- `src/asimplex/streamlit_app`: barebone ChatGPT-like UI shell
- `src/asimplex/tools`: CSV utility functions

## Run the app

```bash
streamlit run src/asimplex/streamlit_app/main.py
```

## Build local RAG index

Place domain documents in `knowledge_base/raw` (supported: `.pdf`, `.csv`, `.txt`, `.md`), then run:

```bash
python -m asimplex.rag.build_index
```

The index is persisted in `.asimplex_rag_chroma` and is used to enrich agent context during chat turns.

