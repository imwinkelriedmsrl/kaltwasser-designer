"""
General helper utilities for Kaltwasser Designer.
"""

import json
import uuid
import io
from typing import Dict, List, Any, Optional

import pandas as pd
import numpy as np


# ---------------------------------------------------------------------------
# Session-state defaults
# ---------------------------------------------------------------------------

DEFAULT_SYSTEM_PARAMS = {
    "project_name":       "Kaltwasserprojekt",
    "project_number":     "",
    "engineer":           "",
    "t_supply_C":         7.0,
    "t_return_C":         12.0,
    "delta_t_K":          5.0,
    "glycol_type":        "Ethylenglykol",
    "glycol_pct":         30,
    "t_ambient_design_C": 32.0,
    "altitude_m":         400,
    "t_indoor_design_C":  27.0,
    "rh_indoor_pct":      50,
}

DEFAULT_NODES: List[Dict] = []
DEFAULT_EDGES: List[Dict] = []


def init_session_state(st) -> None:
    """
    Initialise Streamlit session state with default values.
    Call this from every page.
    """
    if "nodes" not in st.session_state:
        st.session_state.nodes = list(DEFAULT_NODES)
    if "edges" not in st.session_state:
        st.session_state.edges = list(DEFAULT_EDGES)
    if "system_params" not in st.session_state:
        st.session_state.system_params = dict(DEFAULT_SYSTEM_PARAMS)
    if "calc_results" not in st.session_state:
        st.session_state.calc_results = None
    if "selected_node" not in st.session_state:
        st.session_state.selected_node = None
    if "custom_chillers" not in st.session_state:
        st.session_state.custom_chillers = []
    if "custom_fan_coils" not in st.session_state:
        st.session_state.custom_fan_coils = []


def make_node_id() -> str:
    """Generate a short unique node ID."""
    return "N_" + uuid.uuid4().hex[:8].upper()


def make_edge_id() -> str:
    """Generate a short unique edge ID."""
    return "E_" + uuid.uuid4().hex[:8].upper()


# ---------------------------------------------------------------------------
# Network serialisation
# ---------------------------------------------------------------------------

def network_to_json(nodes: List[Dict], edges: List[Dict], system_params: Dict) -> str:
    """Serialise the network to a JSON string."""
    return json.dumps(
        {"nodes": nodes, "edges": edges, "system_params": system_params},
        indent=2,
        ensure_ascii=False,
    )


def network_from_json(json_str: str):
    """Deserialise a network from a JSON string. Returns (nodes, edges, system_params)."""
    data = json.loads(json_str)
    return data.get("nodes", []), data.get("edges", []), data.get("system_params", {})


# ---------------------------------------------------------------------------
# Unit conversion helpers
# ---------------------------------------------------------------------------

def W_to_kW(w: float) -> float:
    return w / 1000.0

def kW_to_W(kw: float) -> float:
    return kw * 1000.0

def Pa_to_kPa(pa: float) -> float:
    return pa / 1000.0

def kPa_to_Pa(kpa: float) -> float:
    return kpa * 1000.0

def mbar_to_Pa(mbar: float) -> float:
    return mbar * 100.0

def Pa_to_mbar(pa: float) -> float:
    return pa / 100.0

def m3h_to_lh(m3h: float) -> float:
    return m3h * 1000.0

def lh_to_m3h(lh: float) -> float:
    return lh / 1000.0

def lh_to_kgs(lh: float, density: float = 1033.7) -> float:
    """Litres/hour → kg/s"""
    return lh * density / 3600.0 / 1000.0


# ---------------------------------------------------------------------------
# Excel export
# ---------------------------------------------------------------------------

def export_bom_to_excel(bom_data: Dict[str, pd.DataFrame]) -> bytes:
    """
    Export multiple BOM tables to a single Excel workbook.
    Returns bytes suitable for st.download_button.
    """
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for sheet_name, df in bom_data.items():
            df.to_excel(writer, sheet_name=sheet_name[:31], index=False)
    return output.getvalue()


# ---------------------------------------------------------------------------
# Expansion vessel sizing (VDI 4708 / EN 12828)
# ---------------------------------------------------------------------------

def size_expansion_vessel(
    total_volume_L: float,
    t_supply_C: float = 7.0,
    t_fill_C: float = 10.0,
    glycol_pct: int = 30,
    p_static_bar: float = 1.5,
    p_max_bar: float = 3.0,
) -> Dict[str, float]:
    """
    Size expansion vessel using simplified method.

    Returns dict with:
        ve_L    – expansion volume [L]
        vn_L    – nominal vessel volume [L]
        p0_bar  – pre-charge pressure [bar]
    """
    e_coeff = 0.0030 + glycol_pct * 0.000020
    delta_t = 80.0 - t_fill_C

    ve = total_volume_L * e_coeff * delta_t
    p0 = p_static_bar + 0.3
    d_factor = (p_max_bar + 1.0) / (p_max_bar - p0)
    vn = ve * d_factor * 1.1  # 10% safety margin

    return {
        "ve_L":      round(ve, 1),
        "vn_L":      round(vn, 1),
        "p0_bar":    round(p0, 2),
        "p_max_bar": p_max_bar,
    }


# ---------------------------------------------------------------------------
# Noise assessment helper
# ---------------------------------------------------------------------------

def sound_pressure_at_distance(
    sound_power_dBa: float,
    distance_m: float,
    directivity_Q: float = 2.0,
) -> float:
    """
    Approximate sound pressure level at a given distance.
    Lp = Lw - 10*log10(4*π*r² / Q)  [simplified free-field]
    """
    if distance_m <= 0:
        return sound_power_dBa
    surface = 4.0 * np.pi * distance_m**2 / directivity_Q
    lp = sound_power_dBa - 10.0 * np.log10(surface)
    return round(lp, 1)


# ---------------------------------------------------------------------------
# Freeze point helpers
# ---------------------------------------------------------------------------

FREEZE_POINTS_EG = {
    0:  0.0,
    10: -3.5,
    20: -8.5,
    25: -11.0,
    30: -14.0,
    35: -17.5,
    40: -22.0,
    50: -34.0,
}

FREEZE_POINTS_PG = {
    0:  0.0,
    10: -3.0,
    20: -8.0,
    25: -10.5,
    30: -13.0,
    35: -17.0,
    40: -21.0,
    50: -31.0,
}


def get_freeze_point_C(glycol_type: str, glycol_pct: int) -> float:
    """Return freeze point in °C for a glycol mixture."""
    table = FREEZE_POINTS_EG if "ethylen" in glycol_type.lower() else FREEZE_POINTS_PG
    pcts = sorted(table.keys())
    for i in range(len(pcts) - 1):
        if pcts[i] <= glycol_pct <= pcts[i + 1]:
            p0, p1 = pcts[i], pcts[i + 1]
            t0, t1 = table[p0], table[p1]
            return t0 + (t1 - t0) * (glycol_pct - p0) / (p1 - p0)
    if glycol_pct <= pcts[0]:
        return table[pcts[0]]
    return table[pcts[-1]]


def check_frosting(t_supply_C: float, glycol_type: str, glycol_pct: int) -> Dict:
    """Check if supply temperature is safely above freeze point."""
    fp = get_freeze_point_C(glycol_type, glycol_pct)
    safety_margin = t_supply_C - fp
    return {
        "freeze_point_C":   fp,
        "supply_C":         t_supply_C,
        "safety_margin_K":  safety_margin,
        "safe":             safety_margin >= 3.0,
    }


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def fmt_kW(w: float) -> str:
    return f"{w/1000:.2f} kW"

def fmt_Pa(pa: float) -> str:
    return f"{pa:.0f} Pa"

def fmt_kPa(pa: float) -> str:
    return f"{pa/1000:.2f} kPa"

def fmt_ms(v: float) -> str:
    return f"{v:.3f} m/s"

def fmt_lh(lh: float) -> str:
    return f"{lh:.0f} l/h"

def fmt_m3h(m3h: float) -> str:
    return f"{m3h:.3f} m³/h"
