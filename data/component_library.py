"""
Component library — equipment specifications for Kaltwasser Designer.

Sources:
  - Climaveneta i-BX2-G07 27Y datasheet
  - Kampmann KaCool W (art. 324001242000M1) datasheet
"""

from typing import Dict, Any, List

# ---------------------------------------------------------------------------
# Outdoor units (Kältemaschinen / Aussengeräte)
# ---------------------------------------------------------------------------

CHILLERS: Dict[str, Dict[str, Any]] = {
    "Climaveneta_iBX2_G07_27Y": {
        "manufacturer":         "Climaveneta",
        "model":                "i-BX2-G07 27Y",
        "type":                 "Luftgekühlter Kaltwassersatz",
        "installation":         "Aussenaufstellung",
        # Cooling performance (EN14511)
        "cooling_capacity_kW":  27.20,
        "power_input_kW":       8.450,
        "eer":                  3.220,
        # Water circuit
        "t_supply_C":           7.0,
        "t_return_C":           12.0,
        "flow_rate_m3h":        5.160,
        "dp_evaporator_kPa":    28.5,
        "pump_head_kPa":        96.8,   # Available pump head at nominal conditions
        # Refrigerant
        "refrigerant":          "R32",
        "gwp":                  675,
        "refrigerant_charge_kg": 4.5,   # Approximate
        # Glycol requirement
        "glycol_type":          "Ethylenglykol",
        "glycol_pct":           30,
        "freeze_point_C":       -16.0,
        # Physical
        "length_mm":            1450,
        "width_mm":             550,
        "height_mm":            1700,
        "weight_kg":            260,
        "sound_power_dBa":      78,
        "sound_pressure_1m_dBa": 65,   # approximate
        # Connection
        "connection_supply":    '1¼" AG',
        "connection_return":    '1¼" AG',
        "connection_type":      "Aussengewinde",
        # Electrical
        "voltage":              "3/N/PE 400V 50Hz",
        "fuse_A":               25,
        "ip_class":             "IP44",
        # Operation limits
        "t_ambient_min_C":      -20,
        "t_ambient_max_C":      46,
        "t_water_supply_min_C":  5,
        "t_water_supply_max_C": 20,
        # Article number / cost reference
        "article":              "i-BX2-G07-27Y",
        "unit_price_chf":       None,   # Configured by user
    },
}

# ---------------------------------------------------------------------------
# Indoor units (Gebläsekonvektoren / Fan Coils)
# ---------------------------------------------------------------------------

FAN_COILS: Dict[str, Dict[str, Any]] = {
    "Kampmann_KaCool_W_Size4": {
        "manufacturer":         "Kampmann",
        "model":                "KaCool W Gr. 4",
        "article":              "324001242000M1",
        "type":                 "Wandgerät Gebläsekonvektor",
        "pipe_system":          "2-Rohr",
        "installation":         "Wandmontage",
        # Performance data table: voltage → (total_W, sensible_W, airflow_m3h, sound_dBa)
        "performance": {
            10: {"cooling_total_W":  4040, "cooling_sensible_W": 3120, "airflow_m3h": 778, "sound_dBa": 49},
            8:  {"cooling_total_W":  3560, "cooling_sensible_W": 2770, "airflow_m3h": 659, "sound_dBa": 44},
            6:  {"cooling_total_W":  3059, "cooling_sensible_W": 2380, "airflow_m3h": 540, "sound_dBa": 39},
            4:  {"cooling_total_W":  2530, "cooling_sensible_W": 1960, "airflow_m3h": 421, "sound_dBa": 33},
            2:  {"cooling_total_W":  1964, "cooling_sensible_W": 1520, "airflow_m3h": 302, "sound_dBa": 27},
        },
        # Reference conditions
        "t_water_supply_C":     7.0,
        "t_water_return_C":     12.0,
        "t_inlet_air_C":        27.0,
        "rh_inlet_pct":         48,
        # Hydraulic data (at 10V / max)
        "water_flow_lh":        696,
        "water_resistance_kPa": 67.6,
        # Physical
        "height_mm":            185,
        "width_mm":             333,
        "length_mm":            1235,
        "weight_kg":            18,
        # Connection
        "connection_supply":    '½"',
        "connection_return":    '½"',
        # Control
        "control_signal":       "0-10V / PWM",
        "voltage_range_V":      "2-10",
        # Electrical
        "power_W":              35,   # Fan motor at max
        "voltage_supply":       "230V 50Hz",
        # Article number / cost reference
        "unit_price_chf":       None,
    },
}


def get_chiller_models() -> List[str]:
    """Return list of available chiller model keys."""
    return list(CHILLERS.keys())


def get_fan_coil_models() -> List[str]:
    """Return list of available fan coil model keys."""
    return list(FAN_COILS.keys())


def get_chiller(model_key: str) -> Dict[str, Any]:
    """Return chiller spec dict."""
    return dict(CHILLERS[model_key])


def get_fan_coil(model_key: str) -> Dict[str, Any]:
    """Return fan coil spec dict."""
    return dict(FAN_COILS[model_key])


def get_fan_coil_capacity_W(model_key: str, voltage: int = 10) -> float:
    """Return cooling capacity in W for a given voltage setpoint."""
    fc = FAN_COILS[model_key]
    if voltage not in fc["performance"]:
        # find nearest
        voltages = sorted(fc["performance"].keys())
        voltage = min(voltages, key=lambda v: abs(v - voltage))
    return float(fc["performance"][voltage]["cooling_total_W"])


def get_fan_coil_flow_lh(model_key: str) -> float:
    """Return design water flow rate in l/h."""
    return float(FAN_COILS[model_key]["water_flow_lh"])


def get_fan_coil_dp_kPa(model_key: str) -> float:
    """Return water-side pressure drop in kPa."""
    return float(FAN_COILS[model_key]["water_resistance_kPa"])


# ---------------------------------------------------------------------------
# Node type definitions (used in network editor)
# ---------------------------------------------------------------------------

NODE_TYPES = {
    "CHILLER":              {"label": "Kältemaschine", "color": "#1565C0", "symbol": "square"},
    "FAN_COIL":             {"label": "Gebläsekonvektor", "color": "#2E7D32", "symbol": "circle"},
    "T_JUNCTION":           {"label": "T-Stück",         "color": "#F57F17", "symbol": "diamond"},
    "PUMP":                 {"label": "Pumpe",            "color": "#6A1B9A", "symbol": "triangle-up"},
    "DISTRIBUTION_MANIFOLD":{"label": "Verteiler",        "color": "#AD1457", "symbol": "star"},
    "AIR_VENT":             {"label": "Entlüftung",       "color": "#00838F", "symbol": "x"},
    "FILL_DRAIN":           {"label": "Befüllung/Entleerung", "color": "#558B2F", "symbol": "cross"},
}
