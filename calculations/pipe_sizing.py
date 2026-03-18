"""
Pipe sizing module for Geberit FlowFit chilled water systems.

Uses the pressure-drop lookup tables in data/geberit_flowfit.py to select
the optimal pipe diameter for a given flow and design criteria.
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
# Public wrappers / extended logic
# ---------------------------------------------------------------------------

def size_pipe(
    flow_W: float,
    glycol_pct: int = 30,
    is_branch: bool = False,
) -> Tuple[int, Dict]:
    """
    Select the smallest Geberit FlowFit pipe satisfying design criteria.

    Design criteria (per VDI 2035 / SWKI):
      - Main pipes  (is_branch=False): v ≤ 1.5 m/s, ΔP ≤ 1.5 mbar/m
      - Branch pipes (is_branch=True):  v ≤ 1.0 m/s, ΔP ≤ 1.5 mbar/m

    Parameters
    ----------
    flow_W : float
        Thermal flow [W]
    glycol_pct : int
        Glycol concentration [%]
    is_branch : bool
        True for branch pipes (lower velocity limit)

    Returns
    -------
    (nominal_dn, pipe_data_dict)
    """
    max_v = 1.0 if is_branch else 1.5
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
        Selected pipe diameter
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

    Returns
    -------
    Same list with added keys:
        nominal_dn, velocity_m_s, pressure_drop_mbar_m,
        dp_pipe_Pa, dp_fittings_Pa, dp_total_Pa, dp_total_kPa,
        water_content_L
    """
    result = []
    for seg in segments:
        flow_W   = seg.get("flow_W", 0.0)
        length_m = seg.get("length_m", 0.0)
        is_branch = seg.get("is_branch", False)
        fittings  = seg.get("fittings", {})

        if flow_W <= 0:
            seg = dict(seg)
            seg.update({
                "nominal_dn": 16,
                "velocity_m_s": 0.0,
                "pressure_drop_mbar_m": 0.0,
                "dp_pipe_Pa": 0.0,
                "dp_fittings_Pa": 0.0,
                "dp_total_Pa": 0.0,
                "dp_total_kPa": 0.0,
                "water_content_L": 0.0,
            })
            result.append(seg)
            continue

        dn, _ = size_pipe(flow_W, glycol_pct=glycol_pct, is_branch=is_branch)
        dp_data = calculate_segment_dp(flow_W, length_m, dn, glycol_pct, fittings)
        wc = calculate_pipe_water_content(dn, length_m)

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
        })
        result.append(seg)
    return result
