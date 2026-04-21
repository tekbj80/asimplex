# asimplex

AI-assisted simulation app for battery system sizing for the German on-grid context, with:
- Streamlit UI
- LangChain-based tuning agent
- Local RAG over domain documents
- Simulation benchmark comparison and HTML export

## Quick start

```bash
python -m venv .venv
. .venv/Scripts/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e ".[dev]"
```

## Configure API key

Set your OpenAI key before running:

```bash
$env:OPENAI_API_KEY="your_key_here"  # PowerShell
```

## Build local RAG index

Place domain documents in `knowledge_base/raw` (supported: `.pdf`, `.csv`, `.txt`, `.md`), then run:

```bash
python -m asimplex.rag.build_index
```

The index is stored in `.asimplex_rag_chroma`.

## Run the app

```bash
streamlit run src/asimplex/streamlit_app/main.py
```

## Typical usage flow

1. **Profiles tab**
   - Upload load profile and PV profile.
   - Upload tariff PDF and extract tariff values.
   - Run **Run base case**.

2. **Simulations tab**
   - Adjust simulation parameters in **Simulation Plan**.
   - Click **Run simulation**.
   - Review **Simulation Benchmarks** and **Simulation Interactive Plot**.
   - In **Result Export**:
     - Edit title/description.
     - Optionally click **Ask AI to generate description**.
     - Click **Generate file to download** and then **Download HTML**.

3. **Chat tab**
   - Ask the agent to tune `application.grid_limit`, `application.evo_threshold`, and `battery_selection.product_id`.
   - Review pending proposal, then **Confirm apply + run** or reject.
   - Agent uses RAG context and price-list lookup tools.

## Notes

- Chat and tariff extraction include rate-limit controls in app settings.
- Export uses browser download (client-side). The app cannot read the final local save path chosen in the browser.
