"""
Pipe sizing module for Geberit FlowFit chilled water systems.

Uses the pressure-drop lookup tables in data/geberit_flowfit.py to select
the optimal pipe diameter for a given flow and design criteria.

Minimum pipe size is DN20 (DN16 removed from catalogue).
Velocity limits are configurable via system_params.
"""

from typing import Dict, Tuple, List, Optional
import numpy as np
from data.geberit_flowfit import (
    size_pipe as _ff_size_pipe,
    get_pipe_data as _ff_get_pipe_data,
    AVAILABLE_SIZES,
    FLOWFIT_PIPE_SPECS,
    water_volume_per_meter,
    get_fluid_properties,
    FITTING_ZETA,
)


# ---------------------------------------------------------------------------
# Default velocity limits (can be overridden via system_params)
# ---------------------------------------------------------------------------
DEFAULT_V_MAX_MAIN_MS   = 1.5  # main pipes
DEFAULT_V_MAX_BRANCH_MS = 0.7  # branch pipes (to fan coils)


# ---------------------------------------------------------------------------
# Public wrappers / extended logic
# ---------------------------------------------------------------------------

def size_pipe(
    flow_W: float,
    glycol_pct: int = 30,
    is_branch: bool = False,
    v_max_main: float = DEFAULT_V_MAX_MAIN_MS,
    v_max_branch: float = DEFAULT_V_MAX_BRANCH_MS,
) -> Tuple[int, Dict]:
    """
    Select the smallest Geberit FlowFit pipe satisfying design criteria.
    Minimum pipe size is DN20.

    Design criteria (configurable, default per VDI 2035 / SWKI):
      - Main pipes  (is_branch=False): v ≤ v_max_main m/s, ΔP ≤ 1.5 mbar/m
      - Branch pipes (is_branch=True): v ≤ v_max_branch m/s, ΔP ≤ 1.5 mbar/m

    Parameters
    ----------
    flow_W : float
        Thermal flow [W]
    glycol_pct : int
        Glycol concentration [%]
    is_branch : bool
        True for branch pipes (lower velocity limit)
    v_max_main : float
        Maximum velocity for main pipes [m/s]
    v_max_branch : float
        Maximum velocity for branch pipes [m/s]

    Returns
    -------
    (nominal_dn, pipe_data_dict)
    """
    max_v = v_max_branch if is_branch else v_max_main
    return _ff_size_pipe(flow_W, glycol_pct=glycol_pct, max_velocity_m_s=max_v, max_dp_mbar_m=1.5)


def get_pipe_data(nominal_dn: int, glycol_pct: int, flow_W: float) -> Dict:
    """Thin wrapper around geberit_flowfit.get_pipe_data."""
    return _ff_get_pipe_data(nominal_dn, glycol_pct, flow_W)


def calculate_fitting_dp_Pa(
    zeta: float,
    velocity_m_s: float,
    density_kg_m3: float,
) -> float:
    """
    Pressure drop through a fitting.

    ΔP = ζ × ρ × v² / 2  [Pa]
    """
    return zeta * density_kg_m3 * velocity_m_s**2 / 2.0


def calculate_segment_dp(
    flow_W: float,
    length_m: float,
    nominal_dn: int,
    glycol_pct: int,
    fittings: Optional[Dict[str, int]] = None,
) -> Dict:
    """
    Calculate total pressure drop for a pipe segment including fittings.

    Parameters
    ----------
    flow_W : float
        Thermal load through this segment [W]
    length_m : float
        Pipe length [m]
    nominal_dn : int
        Selected pipe diameter (minimum DN20)
    glycol_pct : int
        Glycol concentration [%]
    fittings : dict, optional
        {fitting_type: count} e.g. {"elbow_90": 2, "t_branch": 1}

    Returns
    -------
    dict with:
        dp_pipe_Pa      – pressure drop straight pipe [Pa]
        dp_fittings_Pa  – pressure drop fittings [Pa]
        dp_total_Pa     – total pressure drop [Pa]
        dp_total_kPa    – total pressure drop [kPa]
        velocity_m_s    – flow velocity
        pressure_drop_mbar_m – specific pipe pressure drop
    """
    pipe_data = get_pipe_data(nominal_dn, glycol_pct, flow_W)
    v = pipe_data["velocity_m_s"]
    R = pipe_data["pressure_drop_mbar_m"]  # mbar/m

    # Straight pipe: convert mbar/m → Pa/m (×100)
    dp_pipe_Pa = R * 100.0 * length_m

    # Fittings
    props = get_fluid_properties(glycol_pct)
    rho = props["density_kg_m3"]
    dp_fit_Pa = 0.0
    if fittings:
        for fitting_type, count in fittings.items():
            zeta = FITTING_ZETA.get(fitting_type, 0.0)
            dp_fit_Pa += count * calculate_fitting_dp_Pa(zeta, v, rho)

    dp_total_Pa = dp_pipe_Pa + dp_fit_Pa

    return {
        "dp_pipe_Pa":             dp_pipe_Pa,
        "dp_fittings_Pa":         dp_fit_Pa,
        "dp_total_Pa":            dp_total_Pa,
        "dp_total_kPa":           dp_total_Pa / 1000.0,
        "velocity_m_s":           v,
        "pressure_drop_mbar_m":   R,
        "mass_flow_kg_h":         pipe_data["mass_flow_kg_h"],
    }


def calculate_pipe_water_content(
    nominal_dn: int,
    length_m: float,
) -> float:
    """Return water volume in litres for a pipe segment."""
    return water_volume_per_meter(nominal_dn) * length_m


def size_all_segments(
    segments: List[Dict],
    glycol_pct: int = 30,
    v_max_main: float = DEFAULT_V_MAX_MAIN_MS,
    v_max_branch: float = DEFAULT_V_MAX_BRANCH_MS,
) -> List[Dict]:
    """
    Size all pipe segments in a network.

    Parameters
    ----------
    segments : list of dicts, each with:
        id          – segment identifier
        flow_W      – thermal flow [W]
        length_m    – length [m]
        is_branch   – bool
        fittings    – dict {fitting_type: count}
    glycol_pct : int
    v_max_main : float
        Max velocity for main pipes [m/s]
    v_max_branch : float
        Max velocity for branch pipes [m/s]

    Returns
    -------
    Same list with added keys:
        nominal_dn, velocity_m_s, pressure_drop_mbar_m,
        dp_pipe_Pa, dp_fittings_Pa, dp_total_Pa, dp_total_kPa,
        water_content_L, velocity_exceeded
    """
    result = []
    for seg in segments:
        flow_W    = seg.get("flow_W", 0.0)
        length_m  = seg.get("length_m", 0.0)
        is_branch = seg.get("is_branch", False)
        fittings  = seg.get("fittings", {})

        if flow_W <= 0:
            seg = dict(seg)
            seg.update({
                "nominal_dn": 20,
                "velocity_m_s": 0.0,
                "pressure_drop_mbar_m": 0.0,
                "dp_pipe_Pa": 0.0,
                "dp_fittings_Pa": 0.0,
                "dp_total_Pa": 0.0,
                "dp_total_kPa": 0.0,
                "water_content_L": 0.0,
                "velocity_exceeded": False,
            })
            result.append(seg)
            continue

        dn, _ = size_pipe(
            flow_W, glycol_pct=glycol_pct, is_branch=is_branch,
            v_max_main=v_max_main, v_max_branch=v_max_branch
        )
        dp_data = calculate_segment_dp(flow_W, length_m, dn, glycol_pct, fittings)
        wc = calculate_pipe_water_content(dn, length_m)

        v_limit = v_max_branch if is_branch else v_max_main
        velocity_exceeded = dp_data["velocity_m_s"] > v_limit

        seg = dict(seg)
        seg.update({
            "nominal_dn":              dn,
            "velocity_m_s":            dp_data["velocity_m_s"],
            "pressure_drop_mbar_m":    dp_data["pressure_drop_mbar_m"],
            "dp_pipe_Pa":              dp_data["dp_pipe_Pa"],
            "dp_fittings_Pa":          dp_data["dp_fittings_Pa"],
            "dp_total_Pa":             dp_data["dp_total_Pa"],
            "dp_total_kPa":            dp_data["dp_total_kPa"],
            "water_content_L":         wc,
            "velocity_exceeded":       velocity_exceeded,
        })
        result.append(seg)
    return result
