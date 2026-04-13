"""Helpers to build and run simuplex peak-shaving simulations."""

from __future__ import annotations

import copy
import datetime as dt

from bokeh.embed import file_html
from bokeh.resources import CDN
from simuplex import (
    DEFAULT_BATTERY_PARAMS,
    DEFAULT_CLOCK_PARAMS,
    DEFAULT_COMMERCIAL_PARAMS,
    DEFAULT_GRID_PARAMS,
    DEFAULT_LOAD_PARAMS,
    DEFAULT_PV_PARAMS,
    GermanGridTariff,
    PeakShavingMUSimulator,
)
from simuplex.ancillaries.interactive_plots import sim_plot
from simuplex.applications.peak_shaving import DEFAULT_APPLICATION_PARAMS


def build_peak_shaving_simulator(
    *,
    load_profile: list[float],
    pv_power_profile: list[float],
    simulation_plan_params: dict,
) -> PeakShavingMUSimulator:
    if len(load_profile) != len(pv_power_profile):
        raise ValueError("Load and PV profile lengths must match.")

    clock_params = copy.deepcopy(DEFAULT_CLOCK_PARAMS)
    clock_cfg = simulation_plan_params.get("clock", {})
    start_year = int(clock_cfg.get("start_year", 2023))
    timestep_minutes = int(clock_cfg.get("timestep_minutes", 15))
    clock_params["start_time"] = dt.datetime(start_year, 1, 1)
    clock_params["time_step_size"] = dt.timedelta(minutes=timestep_minutes)

    load_params = copy.deepcopy(DEFAULT_LOAD_PARAMS)
    load_params["load_power_profile"] = [float(v) for v in load_profile]

    pv_params = copy.deepcopy(DEFAULT_PV_PARAMS)
    pv_params["power_profile_per_kwp"] = [float(v) for v in pv_power_profile]
    # Current app assumption: profile is already scaled to intended size.
    pv_params["array_capacity"] = 1.0

    bess_params = copy.deepcopy(DEFAULT_BATTERY_PARAMS)
    bess_cfg = simulation_plan_params.get("battery", {})
    for key in ["nominal_capacity", "nominal_power", "inverter_power", "initial_soc", "capex", "annual_opex"]:
        if key in bess_cfg:
            bess_params[key] = float(bess_cfg[key])

    grid_params = copy.deepcopy(DEFAULT_GRID_PARAMS)
    grid_cfg = simulation_plan_params.get("grid", {})
    if "max_power" in grid_cfg:
        grid_params["max_power"] = float(grid_cfg["max_power"])

    app_params = copy.deepcopy(DEFAULT_APPLICATION_PARAMS)
    app_cfg = simulation_plan_params.get("application", {})
    for key in ["grid_limit", "evo_threshold", "backup_power_soc"]:
        if key in app_cfg:
            app_params[key] = float(app_cfg[key])
    for key in ["grid_sale_allowed", "lsk_charge_from_grid"]:
        if key in app_cfg:
            app_params[key] = bool(app_cfg[key])

    tariff_cfg = simulation_plan_params.get("tariff", {})
    below = tariff_cfg.get("below_2500", {})
    above = tariff_cfg.get("above_2500", {})
    tariff = GermanGridTariff(
        below_2500={
            "grid_draw_cost": float(below.get("grid_draw_cost", DEFAULT_COMMERCIAL_PARAMS["tariff"].tariff_below_2500["grid_draw_cost"])),
            "feed_in_tariff": float(below.get("feed_in_tariff", DEFAULT_COMMERCIAL_PARAMS["tariff"].tariff_below_2500["feed_in_tariff"])),
            "demand_charge": float(below.get("demand_charge", DEFAULT_COMMERCIAL_PARAMS["tariff"].tariff_below_2500["demand_charge"])),
        },
        above_2500={
            "grid_draw_cost": float(above.get("grid_draw_cost", DEFAULT_COMMERCIAL_PARAMS["tariff"].tariff_above_2500["grid_draw_cost"])),
            "feed_in_tariff": float(above.get("feed_in_tariff", DEFAULT_COMMERCIAL_PARAMS["tariff"].tariff_above_2500["feed_in_tariff"])),
            "demand_charge": float(above.get("demand_charge", DEFAULT_COMMERCIAL_PARAMS["tariff"].tariff_above_2500["demand_charge"])),
        },
    )
    commercial_params = {"tariff": tariff}

    return PeakShavingMUSimulator(
        clock_params=clock_params,
        commercial_params=commercial_params,
        bess_params=bess_params,
        pv_params=pv_params,
        load_params=load_params,
        grid_params=grid_params,
        application_params=app_params,
    )


def build_simulation_plot_html(simulator: PeakShavingMUSimulator, *, title: str = "Simulation Plan Output") -> str:
    """Build HTML for the simulator interactive Bokeh plot."""
    layout = sim_plot(simulator, title=title)
    return file_html(layout, CDN, title)
