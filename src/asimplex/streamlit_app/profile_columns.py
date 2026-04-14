"""Central profile-column definitions and display metadata."""

from __future__ import annotations

from enum import Enum

try:
    from enum import StrEnum
except ImportError:  # pragma: no cover - Python < 3.11 fallback
    class StrEnum(str, Enum):
        """Compatibility fallback for Python versions without StrEnum."""


class ProfileColumn(StrEnum):
    SITE_LOAD = "site_load"
    PV_PRODUCTION = "pv_production"
    PV_SURPLUS = "pv_surplus"
    GRID_IMPORT = "grid_import"

    @property
    def column_name(self) -> str:
        return str(self.value)

profile_label: dict[ProfileColumn, str] = {
    ProfileColumn.SITE_LOAD: "Site Load",
    ProfileColumn.PV_PRODUCTION: "PV Production",
    ProfileColumn.PV_SURPLUS: "PV Surplus",
    ProfileColumn.GRID_IMPORT: "Grid Import",
}

profile_color: dict[ProfileColumn, str] = {
    ProfileColumn.SITE_LOAD: "blue",
    ProfileColumn.PV_PRODUCTION: "gold",
    ProfileColumn.PV_SURPLUS: "green",
    ProfileColumn.GRID_IMPORT: "red",
}

description: dict[ProfileColumn, str] = {
    ProfileColumn.SITE_LOAD: "Daily load consumption.",
    ProfileColumn.PV_PRODUCTION: "Daily PV production.",
    ProfileColumn.PV_SURPLUS: "Excess PV production to be exported to the grid or charged to battery.",
    ProfileColumn.GRID_IMPORT: "Net grid energy consumption after accounting for PV production.",
}

