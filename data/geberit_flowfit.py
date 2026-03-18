"""
Geberit FlowFit pipe pressure drop data.

Source: Geberit FlowFit Druckverlust-Tabellen
  - "DP Tabelle FlowFit_7_12 dt 5 Ant_Gly 30 Proz" (30% Ethylenglykol, 7/12°C, ΔT=5K)
  - "DP Tabelle FlowFit_7_12 dt 5 Ant_Gly 40 Proz" (40% Ethylenglykol, 7/12°C, ΔT=5K)

Data columns per pipe size:
  (Q_W, mass_flow_kg_h, velocity_m_s, pressure_drop_mbar_per_m)

Pipe sizes available: Ø20, Ø25, Ø32, Ø40, Ø50, Ø63, Ø75
Note: DN16 has been removed. Smallest size is DN20.
"""

import numpy as np
from scipy.interpolate import interp1d
from typing import Tuple, Optional, Dict, Any

# ---------------------------------------------------------------------------
# Full pressure-drop lookup tables — 30% Ethylenglykol, Vorlauf 7°C / Rücklauf 12°C, ΔT = 5 K
# ---------------------------------------------------------------------------
# Medium properties at mean temperature ~9.5°C:
#   Dichte:       1033.7 kg/m³
#   Viskosität:   2.908e-3 Pa·s
#   Wärmekapaz.:  3652 J/(kg·K)
#   Rauigkeit:    0.007 mm

_DATA_30PCT_7_12 = {
    "properties": {
        "density_kg_m3":  1033.7,
        "viscosity_Pa_s": 2.908e-3,
        "cp_J_kgK":       3652,
        "roughness_mm":   0.007,
        "t_supply_C":     7.0,
        "t_return_C":     12.0,
        "glycol_pct":     30,
    },
    "pipes": {
        # DN20  di=16.0 mm
        20: {
            "di_mm": 16.0,
            "data": [
                (  300,   0.295,  0.041,  0.008),
                (  500,   0.492,  0.068,  0.020),
                (  700,   0.689,  0.095,  0.037),
                ( 1000,   0.985,  0.136,  0.069),
                ( 1500,   1.477,  0.204,  0.144),
                ( 2000,   1.970,  0.272,  0.242),
                ( 2500,   2.463,  0.340,  0.363),
                ( 3000,   2.955,  0.408,  0.507),
                ( 3500,   3.448,  0.476,  0.674),
                ( 4000,   3.940,  0.544,  0.864),
                ( 5000,   4.925,  0.680,  1.298),
                ( 6000,   5.910,  0.816,  1.827),
                ( 7000,   6.895,  0.952,  2.448),
                ( 8000,   7.880,  1.088,  3.160),
            ],
        },
        # DN25  di=20.0 mm
        25: {
            "di_mm": 20.0,
            "data": [
                (  500,   0.492,  0.043,  0.007),
                (  800,   0.788,  0.069,  0.016),
                ( 1000,   0.985,  0.087,  0.024),
                ( 1500,   1.477,  0.130,  0.049),
                ( 2000,   1.970,  0.174,  0.082),
                ( 3000,   2.955,  0.261,  0.173),
                ( 4000,   3.940,  0.348,  0.292),
                ( 5000,   4.925,  0.435,  0.437),
                ( 6000,   5.910,  0.522,  0.607),
                ( 7000,   6.895,  0.609,  0.802),
                ( 8000,   7.880,  0.696,  1.020),
                ( 9000,   8.865,  0.783,  1.261),
                (10000,   9.850,  0.870,  1.524),
                (12000,  11.820,  1.044,  2.115),
                (14000,  13.790,  1.218,  2.800),
            ],
        },
        # DN32  di=26.4 mm
        32: {
            "di_mm": 26.4,
            "data": [
                ( 1000,   0.985,  0.050,  0.008),
                ( 1500,   1.477,  0.075,  0.016),
                ( 2000,   1.970,  0.100,  0.027),
                ( 3000,   2.955,  0.150,  0.055),
                ( 4000,   3.940,  0.200,  0.091),
                ( 5000,   4.925,  0.251,  0.137),
                ( 6000,   5.910,  0.301,  0.190),
                ( 7000,   6.895,  0.351,  0.251),
                ( 8000,   7.880,  0.401,  0.319),
                ( 9000,   8.865,  0.451,  0.394),
                (10000,   9.850,  0.501,  0.476),
                (12000,  11.820,  0.601,  0.660),
                (14000,  13.790,  0.701,  0.873),
                (16000,  15.760,  0.801,  1.113),
                (18000,  17.730,  0.901,  1.377),
                (20000,  19.700,  1.001,  1.667),
                (24000,  23.640,  1.201,  2.318),
                (28000,  27.580,  1.402,  3.072),
            ],
        },
        # DN40  di=34.0 mm
        40: {
            "di_mm": 34.0,
            "data": [
                ( 2000,   1.970,  0.060,  0.007),
                ( 3000,   2.955,  0.091,  0.015),
                ( 4000,   3.940,  0.121,  0.025),
                ( 5000,   4.925,  0.152,  0.037),
                ( 6000,   5.910,  0.182,  0.052),
                ( 7000,   6.895,  0.212,  0.069),
                ( 8000,   7.880,  0.242,  0.088),
                ( 9000,   8.865,  0.272,  0.109),
                (10000,   9.850,  0.302,  0.133),
                (12000,  11.820,  0.363,  0.184),
                (14000,  13.790,  0.423,  0.243),
                (16000,  15.760,  0.484,  0.310),
                (18000,  17.730,  0.544,  0.384),
                (20000,  19.700,  0.605,  0.465),
                (24000,  23.640,  0.726,  0.648),
                (28000,  27.580,  0.847,  0.856),
                (32000,  31.520,  0.968,  1.089),
                (36000,  35.460,  1.089,  1.346),
                (40000,  39.400,  1.210,  1.626),
            ],
        },
        # DN50  di=42.4 mm
        50: {
            "di_mm": 42.4,
            "data": [
                ( 4000,   3.940,  0.078,  0.007),
                ( 6000,   5.910,  0.117,  0.015),
                ( 8000,   7.880,  0.156,  0.025),
                (10000,   9.850,  0.195,  0.037),
                (12000,  11.820,  0.234,  0.052),
                (14000,  13.790,  0.273,  0.069),
                (16000,  15.760,  0.312,  0.088),
                (18000,  17.730,  0.351,  0.109),
                (20000,  19.700,  0.390,  0.133),
                (24000,  23.640,  0.468,  0.184),
                (28000,  27.580,  0.546,  0.244),
                (32000,  31.520,  0.624,  0.312),
                (36000,  35.460,  0.702,  0.387),
                (40000,  39.400,  0.780,  0.469),
                (48000,  47.280,  0.936,  0.655),
                (56000,  55.160,  1.092,  0.867),
                (64000,  63.040,  1.248,  1.103),
            ],
        },
        # DN63  di=55.0 mm
        63: {
            "di_mm": 55.0,
            "data": [
                ( 8000,   7.880,  0.093,  0.007),
                (10000,   9.850,  0.116,  0.011),
                (14000,  13.790,  0.163,  0.020),
                (18000,  17.730,  0.209,  0.031),
                (22000,  21.670,  0.256,  0.046),
                (26000,  25.610,  0.302,  0.063),
                (30000,  29.550,  0.349,  0.082),
                (36000,  35.460,  0.418,  0.114),
                (42000,  41.370,  0.488,  0.152),
                (48000,  47.280,  0.558,  0.195),
                (56000,  55.160,  0.651,  0.260),
                (64000,  63.040,  0.744,  0.331),
                (72000,  70.920,  0.837,  0.411),
                (80000,  78.800,  0.930,  0.499),
                (88000,  86.680,  1.023,  0.595),
                (96000,  94.560,  1.116,  0.699),
            ],
        },
        # DN75  di=65.8 mm
        75: {
            "di_mm": 65.8,
            "data": [
                (12000,  11.820,  0.097,  0.006),
                (16000,  15.760,  0.129,  0.010),
                (20000,  19.700,  0.162,  0.015),
                (26000,  25.610,  0.210,  0.024),
                (32000,  31.520,  0.258,  0.035),
                (40000,  39.400,  0.323,  0.052),
                (48000,  47.280,  0.387,  0.072),
                (56000,  55.160,  0.452,  0.095),
                (64000,  63.040,  0.516,  0.121),
                (72000,  70.920,  0.581,  0.150),
                (80000,  78.800,  0.645,  0.182),
                (96000,  94.560,  0.774,  0.254),
                (112000, 110.320, 0.903,  0.337),
                (128000, 126.080, 1.032,  0.432),
                (144000, 141.840, 1.161,  0.538),
            ],
        },
    },
}

# ---------------------------------------------------------------------------
# Full pressure-drop lookup tables — 40% Ethylenglykol, Vorlauf 7°C / Rücklauf 12°C, ΔT = 5 K
# ---------------------------------------------------------------------------
# Medium properties at mean temperature ~9.5°C:
#   Dichte:       1045.0 kg/m³
#   Viskosität:   4.165e-3 Pa·s
#   Wärmekapaz.:  3474 J/(kg·K)

_DATA_40PCT_7_12 = {
    "properties": {
        "density_kg_m3":  1045.0,
        "viscosity_Pa_s": 4.165e-3,
        "cp_J_kgK":       3474,
        "roughness_mm":   0.007,
        "t_supply_C":     7.0,
        "t_return_C":     12.0,
        "glycol_pct":     40,
    },
    "pipes": {
        20: {
            "di_mm": 16.0,
            "data": [
                (  300,   0.311,  0.043,  0.010),
                (  500,   0.518,  0.071,  0.025),
                (  800,   0.829,  0.114,  0.058),
                ( 1000,   1.036,  0.142,  0.087),
                ( 1500,   1.554,  0.213,  0.180),
                ( 2000,   2.072,  0.284,  0.302),
                ( 3000,   3.108,  0.426,  0.638),
                ( 4000,   4.144,  0.568,  1.080),
                ( 5000,   5.180,  0.710,  1.622),
                ( 6000,   6.216,  0.852,  2.263),
                ( 7000,   7.252,  0.994,  3.003),
                ( 8000,   8.288,  1.136,  3.843),
            ],
        },
        25: {
            "di_mm": 20.0,
            "data": [
                (  500,   0.518,  0.046,  0.009),
                ( 1000,   1.036,  0.092,  0.030),
                ( 1500,   1.554,  0.138,  0.062),
                ( 2000,   2.072,  0.184,  0.104),
                ( 3000,   3.108,  0.276,  0.217),
                ( 4000,   4.144,  0.368,  0.365),
                ( 5000,   5.180,  0.460,  0.547),
                ( 6000,   6.216,  0.552,  0.762),
                ( 7000,   7.252,  0.644,  1.009),
                ( 8000,   8.288,  0.736,  1.288),
                (10000,  10.360,  0.920,  1.940),
                (12000,  12.432,  1.104,  2.710),
            ],
        },
        32: {
            "di_mm": 26.4,
            "data": [
                ( 1000,   1.036,  0.053,  0.010),
                ( 2000,   2.072,  0.105,  0.034),
                ( 3000,   3.108,  0.158,  0.069),
                ( 4000,   4.144,  0.211,  0.116),
                ( 5000,   5.180,  0.264,  0.173),
                ( 6000,   6.216,  0.316,  0.240),
                ( 8000,   8.288,  0.422,  0.407),
                (10000,  10.360,  0.528,  0.607),
                (12000,  12.432,  0.633,  0.840),
                (14000,  14.504,  0.739,  1.106),
                (16000,  16.576,  0.844,  1.403),
                (18000,  18.648,  0.950,  1.733),
                (20000,  20.720,  1.055,  2.094),
            ],
        },
        40: {
            "di_mm": 34.0,
            "data": [
                ( 2000,   2.072,  0.063,  0.009),
                ( 4000,   4.144,  0.127,  0.031),
                ( 6000,   6.216,  0.191,  0.065),
                ( 8000,   8.288,  0.255,  0.110),
                (10000,  10.360,  0.319,  0.166),
                (12000,  12.432,  0.382,  0.231),
                (16000,  16.576,  0.510,  0.393),
                (20000,  20.720,  0.637,  0.587),
                (24000,  24.864,  0.765,  0.815),
                (28000,  29.008,  0.892,  1.074),
                (32000,  33.152,  1.019,  1.364),
                (36000,  37.296,  1.146,  1.683),
            ],
        },
        50: {
            "di_mm": 42.4,
            "data": [
                ( 4000,   4.144,  0.082,  0.009),
                ( 6000,   6.216,  0.123,  0.019),
                ( 8000,   8.288,  0.164,  0.031),
                (10000,  10.360,  0.205,  0.047),
                (14000,  14.504,  0.287,  0.088),
                (18000,  18.648,  0.369,  0.138),
                (22000,  22.792,  0.451,  0.199),
                (28000,  29.008,  0.573,  0.311),
                (34000,  35.224,  0.696,  0.452),
                (40000,  41.440,  0.820,  0.606),
                (48000,  49.728,  0.983,  0.855),
                (56000,  58.016,  1.147,  1.134),
            ],
        },
        63: {
            "di_mm": 55.0,
            "data": [
                ( 8000,   8.288,  0.098,  0.009),
                (12000,  12.432,  0.147,  0.018),
                (16000,  16.576,  0.196,  0.031),
                (20000,  20.720,  0.245,  0.046),
                (26000,  26.936,  0.319,  0.074),
                (32000,  33.152,  0.392,  0.109),
                (40000,  41.440,  0.490,  0.163),
                (50000,  51.800,  0.613,  0.245),
                (60000,  62.160,  0.735,  0.340),
                (70000,  72.520,  0.858,  0.449),
                (80000,  82.880,  0.980,  0.571),
                (90000,  93.240,  1.103,  0.707),
            ],
        },
        75: {
            "di_mm": 65.8,
            "data": [
                (12000,  12.432,  0.101,  0.008),
                (18000,  18.648,  0.152,  0.016),
                (24000,  24.864,  0.203,  0.027),
                (32000,  33.152,  0.271,  0.045),
                (40000,  41.440,  0.338,  0.067),
                (50000,  51.800,  0.423,  0.101),
                (60000,  62.160,  0.507,  0.140),
                (72000,  74.592,  0.609,  0.195),
                (84000,  87.024,  0.710,  0.259),
                (96000,  99.456,  0.812,  0.331),
                (112000, 116.032, 0.946,  0.441),
                (128000, 132.608, 1.081,  0.564),
            ],
        },
    },
}

# Public dict: key → dataset
FLOWFIT_DATA: Dict[str, Any] = {
    "30pct_glycol_7_12": _DATA_30PCT_7_12,
    "40pct_glycol_7_12": _DATA_40PCT_7_12,
}

# ---------------------------------------------------------------------------
# Geberit FlowFit Fitting Catalogue — zeta (ζ) values
# ---------------------------------------------------------------------------
FITTING_ZETA = {
    "t_through":        0.5,   # T-Stück Durchgang
    "t_branch":         1.5,   # T-Stück Abzweig
    "elbow_90":         1.0,   # 90° Bogen
    "coupling":         0.2,   # Gerade Muffe / Kupplung
    "valve_isolation":  0.5,   # Absperrventil vollständig geöffnet
    "valve_balancing":  5.0,   # Regulierventil (Mittelwert 2–10)
    "air_vent":         0.0,   # Entlüftungsventil (vernachlässigbar)
    "reducer":          0.3,   # Reduzierstück
    "check_valve":      2.0,   # Rückschlagventil
}

# FlowFit pipe outer diameters, wall thicknesses, and article numbers (mm)
# DN16 removed — smallest size is DN20
FLOWFIT_PIPE_SPECS: Dict[int, Dict[str, Any]] = {
    20: {"da_mm": 20.0, "di_mm": 16.0, "s_mm": 2.0, "article": "619.020.00.1", "desc": "FlowFit Rohr 20mm"},
    25: {"da_mm": 25.0, "di_mm": 20.0, "s_mm": 2.5, "article": "619.025.00.1", "desc": "FlowFit Rohr 25mm"},
    32: {"da_mm": 32.0, "di_mm": 26.4, "s_mm": 2.8, "article": "619.032.00.1", "desc": "FlowFit Rohr 32mm"},
    40: {"da_mm": 40.0, "di_mm": 34.0, "s_mm": 3.0, "article": "619.040.00.1", "desc": "FlowFit Rohr 40mm"},
    50: {"da_mm": 50.0, "di_mm": 42.4, "s_mm": 3.8, "article": "619.050.00.1", "desc": "FlowFit Rohr 50mm"},
    63: {"da_mm": 63.0, "di_mm": 55.0, "s_mm": 4.0, "article": "619.063.00.1", "desc": "FlowFit Rohr 63mm"},
    75: {"da_mm": 75.0, "di_mm": 65.8, "s_mm": 4.6, "article": "619.075.00.1", "desc": "FlowFit Rohr 75mm"},
}

AVAILABLE_SIZES = [20, 25, 32, 40, 50, 63, 75]  # DN16 removed

# ---------------------------------------------------------------------------
# T-pieces (Formteile/T-Stücke) with article numbers
# ---------------------------------------------------------------------------

# Equal T-pieces (gleiches T-Stück)
FLOWFIT_T_PIECES = {
    20:  {"article": "620.020.00.1", "desc": "FlowFit T-Stück 20mm gleich"},
    25:  {"article": "620.025.00.1", "desc": "FlowFit T-Stück 25mm gleich"},
    32:  {"article": "620.032.00.1", "desc": "FlowFit T-Stück 32mm gleich"},
    40:  {"article": "620.040.00.1", "desc": "FlowFit T-Stück 40mm gleich"},
    50:  {"article": "620.050.00.1", "desc": "FlowFit T-Stück 50mm gleich"},
    63:  {"article": "620.063.00.1", "desc": "FlowFit T-Stück 63mm gleich"},
    75:  {"article": "620.075.00.1", "desc": "FlowFit T-Stück 75mm gleich"},
}

# Reducing T-pieces (Übergangs-T-Stück) - main_dn x branch_dn
FLOWFIT_T_PIECES_REDUCING = {
    (25, 20): {"article": "620.025.20.1", "desc": "FlowFit Übergangs-T-Stück 25x20mm"},
    (32, 20): {"article": "620.032.20.1", "desc": "FlowFit Übergangs-T-Stück 32x20mm"},
    (32, 25): {"article": "620.032.25.1", "desc": "FlowFit Übergangs-T-Stück 32x25mm"},
    (40, 20): {"article": "620.040.20.1", "desc": "FlowFit Übergangs-T-Stück 40x20mm"},
    (40, 25): {"article": "620.040.25.1", "desc": "FlowFit Übergangs-T-Stück 40x25mm"},
    (40, 32): {"article": "620.040.32.1", "desc": "FlowFit Übergangs-T-Stück 40x32mm"},
    (50, 25): {"article": "620.050.25.1", "desc": "FlowFit Übergangs-T-Stück 50x25mm"},
    (50, 32): {"article": "620.050.32.1", "desc": "FlowFit Übergangs-T-Stück 50x32mm"},
    (50, 40): {"article": "620.050.40.1", "desc": "FlowFit Übergangs-T-Stück 50x40mm"},
    (63, 32): {"article": "620.063.32.1", "desc": "FlowFit Übergangs-T-Stück 63x32mm"},
    (63, 40): {"article": "620.063.40.1", "desc": "FlowFit Übergangs-T-Stück 63x40mm"},
    (63, 50): {"article": "620.063.50.1", "desc": "FlowFit Übergangs-T-Stück 63x50mm"},
    (75, 40): {"article": "620.075.40.1", "desc": "FlowFit Übergangs-T-Stück 75x40mm"},
    (75, 50): {"article": "620.075.50.1", "desc": "FlowFit Übergangs-T-Stück 75x50mm"},
    (75, 63): {"article": "620.075.63.1", "desc": "FlowFit Übergangs-T-Stück 75x63mm"},
}

# Couplings (Muffen/Verbinder)
FLOWFIT_COUPLINGS = {
    20: {"article": "627.020.00.1", "desc": "FlowFit Verbinder 20mm"},
    25: {"article": "627.025.00.1", "desc": "FlowFit Verbinder 25mm"},
    32: {"article": "627.032.00.1", "desc": "FlowFit Verbinder 32mm"},
    40: {"article": "627.040.00.1", "desc": "FlowFit Verbinder 40mm"},
    50: {"article": "627.050.00.1", "desc": "FlowFit Verbinder 50mm"},
    63: {"article": "627.063.00.1", "desc": "FlowFit Verbinder 63mm"},
    75: {"article": "627.075.00.1", "desc": "FlowFit Verbinder 75mm"},
}

# Elbows 90° (Winkel 90°)
FLOWFIT_ELBOWS_90 = {
    20: {"article": "625.020.00.1", "desc": "FlowFit Winkel 90° 20mm"},
    25: {"article": "625.025.00.1", "desc": "FlowFit Winkel 90° 25mm"},
    32: {"article": "625.032.00.1", "desc": "FlowFit Winkel 90° 32mm"},
    40: {"article": "625.040.00.1", "desc": "FlowFit Winkel 90° 40mm"},
    50: {"article": "625.050.00.1", "desc": "FlowFit Winkel 90° 50mm"},
    63: {"article": "625.063.00.1", "desc": "FlowFit Winkel 90° 63mm"},
    75: {"article": "625.075.00.1", "desc": "FlowFit Winkel 90° 75mm"},
}

# Reducers (Reduktionsstücke)
FLOWFIT_REDUCERS = {
    (25, 20): {"article": "628.025.20.1", "desc": "FlowFit Reduktion 25x20mm"},
    (32, 25): {"article": "628.032.25.1", "desc": "FlowFit Reduktion 32x25mm"},
    (32, 20): {"article": "628.032.20.1", "desc": "FlowFit Reduktion 32x20mm"},
    (40, 32): {"article": "628.040.32.1", "desc": "FlowFit Reduktion 40x32mm"},
    (40, 25): {"article": "628.040.25.1", "desc": "FlowFit Reduktion 40x25mm"},
    (50, 40): {"article": "628.050.40.1", "desc": "FlowFit Reduktion 50x40mm"},
    (50, 32): {"article": "628.050.32.1", "desc": "FlowFit Reduktion 50x32mm"},
    (63, 50): {"article": "628.063.50.1", "desc": "FlowFit Reduktion 63x50mm"},
    (63, 40): {"article": "628.063.40.1", "desc": "FlowFit Reduktion 63x40mm"},
    (75, 63): {"article": "628.075.63.1", "desc": "FlowFit Reduktion 75x63mm"},
    (75, 50): {"article": "628.075.50.1", "desc": "FlowFit Reduktion 75x50mm"},
}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _get_dataset(glycol_pct: int) -> Dict[str, Any]:
    """Return the appropriate dataset for a given glycol percentage."""
    if glycol_pct <= 35:
        return _DATA_30PCT_7_12
    else:
        return _DATA_40PCT_7_12


def _build_interpolator(pipe_data: list, x_col: int, y_col: int):
    """Build a scipy linear interpolator from the raw data table."""
    arr = np.array(pipe_data)
    xs = arr[:, x_col]
    ys = arr[:, y_col]
    # ensure monotone x
    idx = np.argsort(xs)
    return interp1d(xs[idx], ys[idx], kind="linear", bounds_error=False, fill_value="extrapolate")


def get_pipe_data(nominal_dn: int, glycol_pct: int, flow_W: float) -> Dict[str, float]:
    """
    Return interpolated velocity and pressure drop for a given pipe size and flow.

    Parameters
    ----------
    nominal_dn : int
        Nominal pipe diameter (e.g. 20, 25 …)
    glycol_pct : int
        Glycol concentration in % (use 30 or 40)
    flow_W : float
        Thermal power / flow [W]

    Returns
    -------
    dict with keys:
        velocity_m_s      – flow velocity in m/s
        pressure_drop_mbar_m – specific pressure drop in mbar/m
        mass_flow_kg_h    – mass flow rate in kg/h
    """
    dataset = _get_dataset(glycol_pct)
    if nominal_dn not in dataset["pipes"]:
        raise ValueError(f"Pipe DN{nominal_dn} not in FlowFit catalogue.")
    pipe = dataset["pipes"][nominal_dn]
    data = pipe["data"]

    interp_v    = _build_interpolator(data, x_col=0, y_col=2)
    interp_R    = _build_interpolator(data, x_col=0, y_col=3)
    interp_mdot = _build_interpolator(data, x_col=0, y_col=1)

    return {
        "velocity_m_s":          float(interp_v(flow_W)),
        "pressure_drop_mbar_m":  float(interp_R(flow_W)),
        "mass_flow_kg_h":        float(interp_mdot(flow_W)),
    }


def size_pipe(
    flow_W: float,
    glycol_pct: int = 30,
    max_velocity_m_s: float = 1.5,
    max_dp_mbar_m: float = 1.5,
) -> Tuple[int, Dict[str, float]]:
    """
    Select smallest FlowFit pipe that satisfies velocity and pressure-drop limits.
    Minimum size is DN20 (DN16 removed).

    Parameters
    ----------
    flow_W : float
        Thermal load [W]
    glycol_pct : int
        Glycol concentration [%]
    max_velocity_m_s : float
        Maximum allowable velocity [m/s]
    max_dp_mbar_m : float
        Maximum allowable specific pressure drop [mbar/m]  (150 Pa/m = 1.5 mbar/m)

    Returns
    -------
    (nominal_dn, pipe_data_dict)
    """
    for dn in AVAILABLE_SIZES:
        data = get_pipe_data(dn, glycol_pct, flow_W)
        if data["velocity_m_s"] <= max_velocity_m_s and data["pressure_drop_mbar_m"] <= max_dp_mbar_m:
            return dn, data
    # return largest if nothing fits
    largest = AVAILABLE_SIZES[-1]
    return largest, get_pipe_data(largest, glycol_pct, flow_W)


def get_fluid_properties(glycol_pct: int) -> Dict[str, float]:
    """Return medium properties for the given glycol concentration."""
    return dict(_get_dataset(glycol_pct)["properties"])


def water_volume_per_meter(nominal_dn: int) -> float:
    """Return water content in litres per metre of pipe."""
    di = FLOWFIT_PIPE_SPECS[nominal_dn]["di_mm"] / 1000.0  # m
    area = np.pi * di**2 / 4.0  # m²
    return area * 1000.0  # litres/m


def get_t_piece_article(main_dn: int, branch_dn: int) -> Dict[str, str]:
    """Return T-piece article info for given main and branch diameters."""
    if main_dn == branch_dn:
        return FLOWFIT_T_PIECES.get(main_dn, {"article": "—", "desc": f"FlowFit T-Stück {main_dn}mm"})
    return FLOWFIT_T_PIECES_REDUCING.get(
        (main_dn, branch_dn),
        {"article": "—", "desc": f"FlowFit Übergangs-T-Stück {main_dn}x{branch_dn}mm"}
    )


def get_elbow_article(dn: int) -> Dict[str, str]:
    """Return elbow 90° article info for given diameter."""
    return FLOWFIT_ELBOWS_90.get(dn, {"article": "—", "desc": f"FlowFit Winkel 90° {dn}mm"})


def get_coupling_article(dn: int) -> Dict[str, str]:
    """Return coupling article info for given diameter."""
    return FLOWFIT_COUPLINGS.get(dn, {"article": "—", "desc": f"FlowFit Verbinder {dn}mm"})


def get_reducer_article(large_dn: int, small_dn: int) -> Dict[str, str]:
    """Return reducer article info for given diameters."""
    return FLOWFIT_REDUCERS.get(
        (large_dn, small_dn),
        {"article": "—", "desc": f"FlowFit Reduktion {large_dn}x{small_dn}mm"}
    )
