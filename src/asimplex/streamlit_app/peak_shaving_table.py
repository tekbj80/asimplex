"""Peak shaving result table section."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from asimplex.constants import HOUR_FRAC, TARIFF_THRESHOLD
from simuplex.application_support_functions.peak_shaving import determine_battery_discharge


def render_peak_shaving_table() -> None:
    profiles = st.session_state.get("power_profiles")
    if profiles is None or profiles.empty:
        return

    with st.expander("Peak Shaving to Achieve 2500 Full Usage Hours", expanded=True):
        required_cols = {"load", "pv", "grid_power_draw"}
        if not required_cols.issubset(set(profiles.columns)):
            st.info("Load and PV profiles are both required to compute battery discharge results.")
            return

        load_peak = float(profiles["load"].max())
        if load_peak <= 0:
            st.warning("Load peak is zero. Unable to compute a valid power limit.")
            return

        power_limit = profiles["grid_power_draw"].mul(HOUR_FRAC).sum() / TARIFF_THRESHOLD
        st.caption(f"Tariff threshold: {TARIFF_THRESHOLD:.0f} | Computed power limit: {power_limit:.2f} kW")

        try:
            battery_input = pd.DataFrame({"grid_power_draw": profiles["grid_power_draw"]}, index=profiles.index)
            discharge_df = determine_battery_discharge(
                load_profile=battery_input,
                power_limit=float(power_limit),
                col="grid_power_draw",
            )
            st.session_state["battery_discharge_results"] = discharge_df
            if isinstance(discharge_df, pd.DataFrame) and not discharge_df.empty:
                st.dataframe(discharge_df, width="stretch")
            else:
                st.info("No discharge events found for the current power limit.")
        except Exception as exc:
            st.error(f"Battery discharge calculation failed: {exc}")
