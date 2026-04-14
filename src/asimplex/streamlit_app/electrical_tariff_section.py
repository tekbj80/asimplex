"""Electrical tariff input section."""

from __future__ import annotations

import json
import os

import streamlit as st
from openai import OpenAI
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
    },
    "required": [
        "above_2500_flh",
        "below_2500_flh",
        "base_charge_eur_annual",
        "taxes_duties_percent_of_total",
    ],
}
TARIFF_EXTRACTION_PROMPT_TEMPLATE = (
    "Extract tariff values from this PDF for the selected voltage level.\n"
    "Selected voltage level: {voltage_level}\n\n"
    "Return only valid JSON with numeric values and the exact keys:\n"
    "above_2500_flh: {{energy_charge_eur_per_kwh, power_charge_eur_per_kw}},\n"
    "below_2500_flh: {{energy_charge_eur_per_kwh, power_charge_eur_per_kw}},\n"
    "base_charge_eur_annual: include also the annual charges for the measurement point, Messstellenbetrieb,\n"
    "taxes_duties_percent_of_total.\n"
    "If a value cannot be found, return 0."
)


def _extract_tariff_with_llm(pdf_bytes: bytes, filename: str, voltage_level: str) -> tuple[dict[str, object], str]:
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
    return extracted, raw_response_dump


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
        st.text_area(
            "LLM/API raw response",
            value=llm_response_debug_text,
            height=220,
            key="tariff_llm_raw_response_text_area",
            disabled=True,
        )
        if st.button("Extract tariff from PDF", key="tariff_extract_button", type="secondary"):
            if uploaded_tariff_pdf is None:
                st.error("Please upload a PDF first.")
            else:
                try:
                    with st.spinner("Uploading PDF and extracting tariff values..."):
                        extracted_tariff, llm_response_debug_text = _extract_tariff_with_llm(
                            pdf_bytes=uploaded_tariff_pdf.getvalue(),
                            filename=uploaded_tariff_pdf.name,
                            voltage_level=selected_voltage_level,
                        )
                    apply_extracted_tariff_to_simulation_plan_params(
                        extracted_tariff=extracted_tariff,
                    )
                    st.session_state["electrical_tariff"] = {
                        "selected_voltage_level": selected_voltage_level,
                        "llm_extracted_tariff": extracted_tariff,
                        "llm_response_debug_text": llm_response_debug_text,
                    }
                    st.success("Tariff values extracted.")
                    st.json(extracted_tariff)
                except Exception as exc:
                    llm_response_debug_text = str(exc)
                    st.error(f"Extraction failed: {exc}")

        st.session_state["electrical_tariff"] = {
            "selected_voltage_level": selected_voltage_level,
            "llm_extracted_tariff": extracted_tariff,
            "llm_response_debug_text": llm_response_debug_text,
        }
