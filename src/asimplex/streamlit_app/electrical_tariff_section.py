"""Electrical tariff input section."""

from __future__ import annotations

import json
import os
from typing import Any

import streamlit as st
from openai import OpenAI

from asimplex.llm_usage import record_llm_usage
from asimplex.observability.app_log_store import log_event
from asimplex.persistence.session_store import append_llm_usage_event, create_version, save_tariff_snapshot
from asimplex.streamlit_app.simulation_plan_section import (
    apply_extracted_tariff_to_simulation_plan_params,
)

VOLTAGE_LEVEL_OPTIONS = [
    "Umspannung Höchst-/ Hochspannung",
    "Hochspannung",
    "Umspannung Hoch-/ Mittelspannung",
    "Mittelspannung",
    "Umspannung Mittel-/ Niederspannung",
    "Niederspannung",
]
TARIFF_JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "above_2500_flh": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "energy_charge_eur_per_kwh": {"type": "number"},
                "power_charge_eur_per_kw": {"type": "number"},
            },
            "required": ["energy_charge_eur_per_kwh", "power_charge_eur_per_kw"],
        },
        "below_2500_flh": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "energy_charge_eur_per_kwh": {"type": "number"},
                "power_charge_eur_per_kw": {"type": "number"},
            },
            "required": ["energy_charge_eur_per_kwh", "power_charge_eur_per_kw"],
        },
        "base_charge_eur_annual": {"type": "number"},
        "taxes_duties_percent_of_total": {"type": "number"},
        "extraction_confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "missing_fields": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "above_2500_flh",
        "below_2500_flh",
        "base_charge_eur_annual",
        "taxes_duties_percent_of_total",
        "extraction_confidence",
        "missing_fields",
    ],
}
TARIFF_EXTRACTION_PROMPT_TEMPLATE = (
    "Extract tariff values from this PDF for the selected voltage level.\n"
    "Selected voltage level: {voltage_level}\n\n"
    "Return only valid JSON with numeric values and the exact keys:\n"
    "above_2500_flh: {{energy_charge_eur_per_kwh, power_charge_eur_per_kw}},\n"
    "below_2500_flh: {{energy_charge_eur_per_kwh, power_charge_eur_per_kw}},\n"
    "base_charge_eur_annual: include also the annual charges for the measurement point, Messstellenbetrieb,\n"
    "taxes_duties_percent_of_total,\n"
    "extraction_confidence (0..1),\n"
    "missing_fields (array of missing field names).\n"
    "Do not invent values. If values are missing, include them in missing_fields."
)


def _validate_extracted_tariff_payload(extracted_tariff: dict[str, Any], parsed: dict[str, Any]) -> None:
    if not isinstance(extracted_tariff, dict):
        raise ValueError("Tariff extraction returned invalid payload type.")
    if not isinstance(parsed, dict):
        raise ValueError("Tariff extraction parsing failed.")

    missing_fields = parsed.get("missing_fields", [])
    extraction_confidence = float(parsed.get("extraction_confidence", 0.0) or 0.0)
    if not isinstance(missing_fields, list):
        raise ValueError("Tariff extraction missing_fields must be a list.")
    if missing_fields:
        raise ValueError(f"Missing required tariff fields: {', '.join(str(x) for x in missing_fields)}")
    if extraction_confidence < 0.5:
        raise ValueError(f"Extraction confidence too low ({extraction_confidence:.2f}).")

    below = extracted_tariff.get("below_2500_flh", {})
    above = extracted_tariff.get("above_2500_flh", {})
    if not isinstance(below, dict) or not isinstance(above, dict):
        raise ValueError("Tariff blocks are malformed.")
    numeric_values = [
        float(below.get("energy_charge_eur_per_kwh", 0.0) or 0.0),
        float(below.get("power_charge_eur_per_kw", 0.0) or 0.0),
        float(above.get("energy_charge_eur_per_kwh", 0.0) or 0.0),
        float(above.get("power_charge_eur_per_kw", 0.0) or 0.0),
        float(extracted_tariff.get("base_charge_eur_annual", 0.0) or 0.0),
        float(extracted_tariff.get("taxes_duties_percent_of_total", 0.0) or 0.0),
    ]
    if all(v == 0.0 for v in numeric_values):
        raise ValueError("Extraction appears invalid: all tariff values are zero.")
    if max(numeric_values[:4]) <= 0.0:
        raise ValueError("Extraction appears invalid: missing energy/power charge values.")


def _extract_tariff_with_llm(
    pdf_bytes: bytes, filename: str, voltage_level: str
) -> tuple[dict[str, object], str, dict[str, int] | None]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    client = OpenAI(api_key=api_key)

    upload_response = client.files.create(
        file=(filename, pdf_bytes, "application/pdf"),
        purpose="user_data",
    )
    file_id = getattr(upload_response, "id", None)
    if not isinstance(file_id, str) or not file_id:
        raise RuntimeError("File upload did not return a valid file id.")

    prompt = TARIFF_EXTRACTION_PROMPT_TEMPLATE.format(voltage_level=voltage_level)
    llm_response = client.responses.create(
        model="gpt-4.1-mini",
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_file", "file_id": file_id},
                ],
            }
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "tariff_extraction",
                "schema": TARIFF_JSON_SCHEMA,
                "strict": True,
            }
        },
    )
    raw_response_dump = llm_response.model_dump_json(indent=2)
    output_text = getattr(llm_response, "output_text", None)
    if not isinstance(output_text, str) or not output_text.strip():
        raise RuntimeError("LLM did not return JSON output text.")
    parsed = json.loads(output_text)
    extracted = {
        "above_2500_flh": {
            "energy_charge_eur_per_kwh": float(parsed["above_2500_flh"]["energy_charge_eur_per_kwh"]),
            "power_charge_eur_per_kw": float(parsed["above_2500_flh"]["power_charge_eur_per_kw"]),
        },
        "below_2500_flh": {
            "energy_charge_eur_per_kwh": float(parsed["below_2500_flh"]["energy_charge_eur_per_kwh"]),
            "power_charge_eur_per_kw": float(parsed["below_2500_flh"]["power_charge_eur_per_kw"]),
        },
        "base_charge_eur_annual": float(parsed["base_charge_eur_annual"]),
        "taxes_duties_percent_of_total": float(parsed["taxes_duties_percent_of_total"]),
    }
    _validate_extracted_tariff_payload(extracted, parsed)
    usage_info: dict[str, int] | None = None
    usage_obj = getattr(llm_response, "usage", None)
    if usage_obj is not None:
        usage_info = {
            "input_tokens": int(getattr(usage_obj, "input_tokens", 0) or 0),
            "output_tokens": int(getattr(usage_obj, "output_tokens", 0) or 0),
        }
    return extracted, raw_response_dump, usage_info


def render_electrical_tariff_section() -> None:
    tariff_state = st.session_state.get("electrical_tariff", {})

    with st.sidebar.expander("Electrical Tariff", expanded=False):
        selected_voltage_level = st.selectbox(
            "Voltage level",
            options=VOLTAGE_LEVEL_OPTIONS,
            index=VOLTAGE_LEVEL_OPTIONS.index(
                tariff_state.get("selected_voltage_level", VOLTAGE_LEVEL_OPTIONS[0])
            )
            if tariff_state.get("selected_voltage_level", VOLTAGE_LEVEL_OPTIONS[0]) in VOLTAGE_LEVEL_OPTIONS
            else 0,
            key="tariff_voltage_level",
        )
        uploaded_tariff_pdf = st.file_uploader(
            "Upload tariff PDF",
            type=["pdf"],
            accept_multiple_files=False,
            key="tariff_pdf_upload",
        )
        extracted_tariff = tariff_state.get("llm_extracted_tariff")
        llm_response_debug_text = str(tariff_state.get("llm_response_debug_text", ""))
        source_filename = str(tariff_state.get("source_filename", "") or "")
        loaded_from_session = bool(tariff_state.get("loaded_from_session", False))
        if source_filename:
            st.caption(f"Loaded file: `{source_filename}`")
        if loaded_from_session:
            st.warning(
                "Tariff values were loaded from the last saved session state. "
                "These may not match the currently uploaded file, this could be due to manual edits."
            )
        if st.button("Extract tariff from PDF", key="tariff_extract_button", type="secondary"):
            if uploaded_tariff_pdf is None:
                st.error("Please upload a PDF first.")
            else:
                try:
                    with st.spinner("Uploading PDF and extracting tariff values..."):
                        extracted_tariff, llm_response_debug_text, usage = _extract_tariff_with_llm(
                            pdf_bytes=uploaded_tariff_pdf.getvalue(),
                            filename=uploaded_tariff_pdf.name,
                            voltage_level=selected_voltage_level,
                        )
                    if isinstance(usage, dict):
                        row = record_llm_usage(
                            st.session_state,
                            label="Tariff extraction",
                            model_name="gpt-4.1-mini",
                            input_tokens=usage.get("input_tokens"),
                            output_tokens=usage.get("output_tokens"),
                        )
                        project_name = str(st.session_state.get("project_name", "") or "")
                        if project_name:
                            append_llm_usage_event(project_name, row)
                    apply_extracted_tariff_to_simulation_plan_params(
                        extracted_tariff=extracted_tariff,
                    )
                    st.session_state["electrical_tariff"] = {
                        "selected_voltage_level": selected_voltage_level,
                        "llm_extracted_tariff": extracted_tariff,
                        "llm_response_debug_text": llm_response_debug_text,
                        "source_filename": uploaded_tariff_pdf.name,
                        "loaded_from_session": False,
                    }
                    source_filename = uploaded_tariff_pdf.name
                    loaded_from_session = False
                    project_name = str(st.session_state.get("project_name", "") or "")
                    if project_name:
                        save_tariff_snapshot(
                            project_name=project_name,
                            filename=uploaded_tariff_pdf.name,
                            selected_voltage_level=selected_voltage_level,
                            extracted_tariff=extracted_tariff if isinstance(extracted_tariff, dict) else {},
                        )
                        create_version(
                            project_name=project_name,
                            source="tariff_upload",
                            note=f"Tariff extracted from {uploaded_tariff_pdf.name} ({selected_voltage_level})",
                            params=st.session_state.get("simulation_plan_params", {}),
                            patch={"extracted_tariff": extracted_tariff} if isinstance(extracted_tariff, dict) else {},
                        )
                    log_event(
                        project_name=project_name,
                        source="tariff_extraction",
                        event_type="extract_tariff",
                        status="success",
                        message="Tariff extracted and applied.",
                        payload={
                            "filename": uploaded_tariff_pdf.name,
                            "selected_voltage_level": selected_voltage_level,
                        },
                    )
                    st.success("Tariff values extracted.")
                except Exception as exc:
                    llm_response_debug_text = str(exc)
                    st.error(f"Extraction failed: {exc}")
                    log_event(
                        project_name=str(st.session_state.get("project_name", "") or ""),
                        source="tariff_extraction",
                        event_type="extract_tariff",
                        status="error",
                        error=str(exc),
                        message="Tariff extraction failed. No state changes were applied.",
                        payload={
                            "filename": getattr(uploaded_tariff_pdf, "name", ""),
                            "selected_voltage_level": selected_voltage_level,
                        },
                    )

        if isinstance(extracted_tariff, dict):
            st.info("Extracted values have been automatically updated to the simulation inputs.")
            st.code(json.dumps(extracted_tariff, indent=2), language="json")

        st.session_state["electrical_tariff"] = {
            "selected_voltage_level": selected_voltage_level,
            "llm_extracted_tariff": extracted_tariff,
            "llm_response_debug_text": llm_response_debug_text,
            "source_filename": source_filename,
            "loaded_from_session": loaded_from_session,
        }
