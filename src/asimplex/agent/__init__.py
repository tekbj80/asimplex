"""LangChain agent package for simulation tuning."""

try:  # pragma: no cover - optional at import time before dependencies are installed
    from asimplex.agent.runner import run_tuning_agent
except Exception:  # pragma: no cover
    run_tuning_agent = None  # type: ignore[assignment]

__all__ = ["run_tuning_agent"]
