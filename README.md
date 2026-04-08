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

