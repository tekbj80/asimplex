"""Electrical tariff input section."""

from __future__ import annotations

import streamlit as st


def render_electrical_tariff_section() -> None:
    tariff_state = st.session_state.get("electrical_tariff", {})
    lt_state = tariff_state.get("lt_2500_hour_equivalent", {})
    gt_state = tariff_state.get("gt_2500_hour_equivalent", {})

    with st.sidebar.expander("Electrical Tariff", expanded=False):
        st.markdown("**< 2500 Hour Equivalent**")
        lt_power_charge = st.number_input(
            "Power Charge (EUR/kW)",
            min_value=0.0,
            value=float(lt_state.get("power_charge_eur_per_kw", 0.0)),
            step=0.1,
            key="tariff_lt_power_charge",
        )
        lt_energy_charge = st.number_input(
            "Energy Charge (EUR/kWh)",
            min_value=0.0,
            value=float(lt_state.get("energy_charge_eur_per_kwh", 0.0)),
            step=0.001,
            format="%.4f",
            key="tariff_lt_energy_charge",
        )

        st.markdown("**> 2500 Hour Equivalent**")
        gt_power_charge = st.number_input(
            "Power Charge (EUR/kW) ",
            min_value=0.0,
            value=float(gt_state.get("power_charge_eur_per_kw", 0.0)),
            step=0.1,
            key="tariff_gt_power_charge",
        )
        gt_energy_charge = st.number_input(
            "Energy Charge (EUR/kWh) ",
            min_value=0.0,
            value=float(gt_state.get("energy_charge_eur_per_kwh", 0.0)),
            step=0.001,
            format="%.4f",
            key="tariff_gt_energy_charge",
        )

        st.markdown("**Other inputs**")
        other_charges = st.number_input(
            "other charges: EUR/kWh",
            min_value=0.0,
            value=float(tariff_state.get("other_charges_eur_per_kwh", 0.0)),
            step=0.001,
            format="%.4f",
            key="tariff_other_charges",
        )
        taxes_duties_percent = st.number_input(
            "taxes/duties (percentage of total): %",
            min_value=0.0,
            max_value=100.0,
            value=float(tariff_state.get("taxes_duties_percent_of_total", 0.0)),
            step=0.1,
            key="tariff_taxes_duties_percent",
        )

        st.session_state["electrical_tariff"] = {
            "lt_2500_hour_equivalent": {
                "power_charge_eur_per_kw": float(lt_power_charge),
                "energy_charge_eur_per_kwh": float(lt_energy_charge),
            },
            "gt_2500_hour_equivalent": {
                "power_charge_eur_per_kw": float(gt_power_charge),
                "energy_charge_eur_per_kwh": float(gt_energy_charge),
            },
            "other_charges_eur_per_kwh": float(other_charges),
            "taxes_duties_percent_of_total": float(taxes_duties_percent),
        }
