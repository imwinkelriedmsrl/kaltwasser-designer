"""
Materialliste (BOM) — Seite 3
Vollständige Stückliste mit Excel-Export.
"""

import streamlit as st
import pandas as pd
import numpy as np
import io
from collections import defaultdict
from typing import Dict, List, Any

from utils.helpers import (
    init_session_state,
    export_bom_to_excel,
    size_expansion_vessel,
)
from data.geberit_flowfit import FLOWFIT_PIPE_SPECS, water_volume_per_meter
from data.component_library import CHILLERS, FAN_COILS, get_chiller, get_fan_coil

# ---------------------------------------------------------------------------
st.set_page_config(page_title="Materialliste | Kaltwasser Designer", layout="wide", page_icon="📋")
init_session_state(st)

st.markdown("""
<style>
.bom-section { background: #f8f9fa; border-left: 4px solid #1565C0; padding: 12px 16px; margin-bottom: 16px; border-radius: 0 8px 8px 0; }
.bom-title { font-size: 1.1rem; font-weight: 700; color: #1565C0; margin-bottom: 8px; }
table.bom thead th { background-color: #1a2332 !important; color: white; }
</style>
""", unsafe_allow_html=True)

st.markdown("# 📋 Materialliste (Stückliste / BOM)")
st.markdown("Vollständige Stückliste für die Geberit FlowFit Kaltwasseranlage.")

nodes  = st.session_state.nodes
edges  = st.session_state.edges
sp     = st.session_state.system_params
results = st.session_state.calc_results

if not nodes:
    st.warning("⚠️ Kein Netzwerk vorhanden. Bitte zuerst im Netzwerk-Editor ein Netz anlegen.")
    st.page_link("pages/1_🔧_Network_Editor.py", label="→ Zum Netzwerk-Editor", icon="🔧")
    st.stop()

# ---------------------------------------------------------------------------
# Build BOM
# ---------------------------------------------------------------------------

def build_bom(nodes, edges, sp, results) -> Dict[str, pd.DataFrame]:
    """Compile the full bill of materials."""
    glycol_pct = int(sp.get("glycol_pct", 30))

    # ------------------------------------------------------------------
    # 1. Outdoor units
    # ------------------------------------------------------------------
    chiller_rows = []
    for n in nodes:
        if n.get("type") == "CHILLER":
            model_key = n.get("model", "Climaveneta_iBX2_G07_27Y")
            ch = get_chiller(model_key)
            chiller_rows.append({
                "Pos.":           len(chiller_rows) + 1,
                "Artikelnummer":  ch.get("article", "—"),
                "Beschreibung":   f"{ch['manufacturer']} {ch['model']}",
                "Typ":            ch["type"],
                "Kälteleistung":  f"{ch['cooling_capacity_kW']} kW",
                "Kältemittel":    ch["refrigerant"],
                "Anschluss":      ch.get("connection_supply","—"),
                "Bezeichnung":    n.get("label",""),
                "Menge":          1,
                "Einheit":        "Stück",
            })

    df_chillers = pd.DataFrame(chiller_rows) if chiller_rows else pd.DataFrame(
        columns=["Pos.","Artikelnummer","Beschreibung","Typ","Kälteleistung","Kältemittel","Anschluss","Bezeichnung","Menge","Einheit"]
    )

    # ------------------------------------------------------------------
    # 2. Indoor units
    # ------------------------------------------------------------------
    fc_rows = []
    for n in nodes:
        if n.get("type") == "FAN_COIL":
            model_key = n.get("model", "Kampmann_KaCool_W_Size4")
            fc = get_fan_coil(model_key)
            voltage = int(n.get("voltage", 10))
            perf = fc["performance"].get(voltage, fc["performance"][10])
            fc_rows.append({
                "Pos.":            len(fc_rows) + 1,
                "Artikelnummer":   fc.get("article","—"),
                "Beschreibung":    f"{fc['manufacturer']} {fc['model']}",
                "Raum":            n.get("room","—"),
                "Betriebsspannung": f"{voltage} V",
                "Kühlleistung":    f"{perf['cooling_total_W']} W",
                "Luftvolumen":     f"{perf['airflow_m3h']} m³/h",
                "Anschluss":       fc.get("connection_supply","—"),
                "Bezeichnung":     n.get("label",""),
                "Menge":           1,
                "Einheit":         "Stück",
            })

    df_fancoils = pd.DataFrame(fc_rows) if fc_rows else pd.DataFrame(
        columns=["Pos.","Artikelnummer","Beschreibung","Raum","Betriebsspannung","Kühlleistung","Luftvolumen","Anschluss","Bezeichnung","Menge","Einheit"]
    )

    # ------------------------------------------------------------------
    # 3. Pipes — grouped by diameter
    # ------------------------------------------------------------------
    # Use calculated sizes if available, otherwise size from flow
    pipe_lengths: Dict[int, float] = defaultdict(float)
    pipe_usage: List[Dict] = []

    for edge in edges:
        eid = edge["id"]
        length_m = edge.get("length_m", 0.0)

        # Determine DN from calculation results or estimate
        dn = 25  # fallback
        if results and "pipe_sizes" in results:
            dn = results["pipe_sizes"].get(eid, 25)

        pipe_lengths[dn] += length_m
        src_label = next((n.get("label","?") for n in nodes if n["id"] == edge["source"]), edge["source"])
        tgt_label = next((n.get("label","?") for n in nodes if n["id"] == edge["target"]), edge["target"])
        pipe_usage.append({
            "Segment":  edge.get("label", f"{src_label}→{tgt_label}"),
            "DN":       dn,
            "Länge [m]": length_m,
        })

    pipe_rows = []
    total_pipe_cost = 0.0
    for dn in sorted(pipe_lengths.keys()):
        raw_length = pipe_lengths[dn]
        length_with_waste = raw_length * 1.10  # +10% Verschnitt
        # Sold in standard bar lengths of 5m
        bars_5m = math.ceil(length_with_waste / 5.0)

        pipe_rows.append({
            "Pos.":                   len(pipe_rows) + 1,
            "Beschreibung":           f"Geberit FlowFit Rohr Ø{dn} mm",
            "Nenndurchmesser":        f"DN{dn}",
            "Innendurchmesser":       f"{FLOWFIT_PIPE_SPECS[dn]['di_mm']:.1f} mm",
            "Länge netto [m]":        round(raw_length, 2),
            "Länge inkl. Verschnitt": round(length_with_waste, 2),
            "Anzahl Stangen (5m)":    bars_5m,
            "Einheit":                "Stück (5m Stangen)",
        })

    df_pipes = pd.DataFrame(pipe_rows) if pipe_rows else pd.DataFrame(
        columns=["Pos.","Beschreibung","Nenndurchmesser","Innendurchmesser","Länge netto [m]","Länge inkl. Verschnitt","Anzahl Stangen (5m)","Einheit"]
    )

    # ------------------------------------------------------------------
    # 4. Fittings — T-Stücke, Bögen, Kupplungen, Reduzierstücke
    # ------------------------------------------------------------------
    fitting_counts: Dict[str, int] = defaultdict(int)
    fitting_dn: Dict[str, str] = {}

    for edge in edges:
        eid = edge["id"]
        dn = 25
        if results and "pipe_sizes" in results:
            dn = results["pipe_sizes"].get(eid, 25)

        fittings = edge.get("fittings", {})
        for fit_type, count in fittings.items():
            key = f"{fit_type}|DN{dn}"
            fitting_counts[key] += count
            fitting_dn[key] = f"DN{dn}"

    fitting_name_map = {
        "elbow_90":          "90° Bogen",
        "t_through":         "T-Stück (Durchgang)",
        "t_branch":          "T-Stück (Abzweig)",
        "coupling":          "Kupplung (gerade Muffe)",
        "valve_isolation":   "Absperrventil",
        "valve_balancing":   "Regulierventil",
        "air_vent":          "Entlüftungsventil",
        "reducer":           "Reduzierstück",
        "check_valve":       "Rückschlagventil",
    }

    fitting_rows = []
    for key, count in sorted(fitting_counts.items()):
        fit_type, dn_str = key.split("|")
        name = fitting_name_map.get(fit_type, fit_type)
        fitting_rows.append({
            "Pos.":          len(fitting_rows) + 1,
            "Beschreibung":  f"Geberit FlowFit {name} {dn_str}",
            "Typ":           name,
            "DN":            dn_str,
            "Menge":         count,
            "Einheit":       "Stück",
        })

    # Add standard fittings (1 isolation valve pair per fan coil)
    n_fc = sum(1 for n in nodes if n.get("type") == "FAN_COIL")
    if n_fc > 0:
        fitting_rows.append({
            "Pos.":          len(fitting_rows) + 1,
            "Beschreibung":  "Geberit FlowFit Absperrventil DN16 (1/2\" Stichleitung GK)",
            "Typ":           "Absperrventil",
            "DN":            "DN16",
            "Menge":         n_fc * 2,  # VL + RL
            "Einheit":       "Stück",
        })
        fitting_rows.append({
            "Pos.":          len(fitting_rows) + 1,
            "Beschreibung":  "Regulierventil DN16 (Stichleitung GK)",
            "Typ":           "Regulierventil",
            "DN":            "DN16",
            "Menge":         n_fc,
            "Einheit":       "Stück",
        })

    df_fittings = pd.DataFrame(fitting_rows) if fitting_rows else pd.DataFrame(
        columns=["Pos.","Beschreibung","Typ","DN","Menge","Einheit"]
    )

    # ------------------------------------------------------------------
    # 5. Hydraulic accessories
    # ------------------------------------------------------------------
    access_rows = []

    # Air vents — 1 per branch circuit high point (estimate 1 per fan coil + 1 main)
    n_vents = max(1, n_fc // 2 + 1)
    access_rows.append({
        "Pos.": 1, "Beschreibung": "Automatischer Entlüfter DN15",
        "Menge": n_vents, "Einheit": "Stück",
        "Bemerkung": "1 pro Kreisläufe / Hochpunkt"
    })

    # Fill & drain valves
    access_rows.append({
        "Pos.": 2, "Beschreibung": "Befüll- und Entleerungshahn DN20",
        "Menge": 2, "Einheit": "Stück",
        "Bemerkung": "VL + RL, tiefster Punkt"
    })

    # Pressure gauge connections
    access_rows.append({
        "Pos.": 3, "Beschreibung": "Manometeranschluss PN16, DN15",
        "Menge": 2, "Einheit": "Stück",
        "Bemerkung": "Vorlauf + Rücklauf"
    })

    # Expansion vessel
    total_vol_L = sum(
        water_volume_per_meter(
            (results["pipe_sizes"].get(e["id"], 25) if results else 25)
        ) * e.get("length_m", 1.0)
        for e in edges
    )
    exp = size_expansion_vessel(
        total_volume_L=max(total_vol_L, 20.0),
        t_supply_C=float(sp.get("t_supply_C", 7.0)),
        glycol_pct=int(sp.get("glycol_pct", 30)),
    )
    exp_size = exp["vn_L"]
    # Round up to standard sizes
    std_sizes = [8, 12, 18, 24, 35, 50, 80, 100, 150, 200]
    exp_std = next((s for s in std_sizes if s >= exp_size), std_sizes[-1])
    access_rows.append({
        "Pos.": 4, "Beschreibung": f"Membran-Druckausdehnungsgefäss {exp_std} L",
        "Menge": 1, "Einheit": "Stück",
        "Bemerkung": f"Berechnetes Min. {exp_size:.1f} L, Vorladedruck {exp['p0_bar']:.2f} bar"
    })

    # Safety valve
    access_rows.append({
        "Pos.": 5, "Beschreibung": "Sicherheitsventil 3 bar, DN15",
        "Menge": 1, "Einheit": "Stück",
        "Bemerkung": "Absicherung Ausdehnungsgefäss"
    })

    # Glycol fill
    glycol_needed_L = max(total_vol_L * float(sp.get("glycol_pct", 30)) / 100.0, 5.0)
    access_rows.append({
        "Pos.": 6, "Beschreibung": f"Ethylenglykol 40% Fertigmischung, Kanister",
        "Menge": math.ceil(glycol_needed_L / 20.0),
        "Einheit": "Kanister (20 L)",
        "Bemerkung": f"Bedarf ca. {glycol_needed_L:.0f} L für {sp.get('glycol_pct',30)}% Konzentration"
    })

    df_accessories = pd.DataFrame(access_rows)

    # ------------------------------------------------------------------
    # 6. Thermal insulation
    # ------------------------------------------------------------------
    insulation_rows = []
    insulation_thickness = {16: 13, 20: 13, 25: 19, 32: 19, 40: 25, 50: 25, 63: 32, 75: 32}  # mm

    for dn in sorted(pipe_lengths.keys()):
        raw_length = pipe_lengths[dn]
        insul_mm = insulation_thickness.get(dn, 25)
        insulation_rows.append({
            "Pos.":              len(insulation_rows) + 1,
            "Beschreibung":      f"Kautschuk-Rohrisolation Ø{dn}mm, {insul_mm}mm Wandstärke",
            "DN":                f"DN{dn}",
            "Dämmstärke [mm]":   insul_mm,
            "Länge netto [m]":   round(raw_length, 2),
            "Länge inkl. Verschnitt": round(raw_length * 1.10, 2),
            "Einheit":           "m",
        })

    df_insulation = pd.DataFrame(insulation_rows) if insulation_rows else pd.DataFrame(
        columns=["Pos.","Beschreibung","DN","Dämmstärke [mm]","Länge netto [m]","Länge inkl. Verschnitt","Einheit"]
    )

    return {
        "Aussengeräte":     df_chillers,
        "Innengeräte":      df_fancoils,
        "Rohre FlowFit":    df_pipes,
        "Formteile":        df_fittings,
        "Hydraulik-Zubehör": df_accessories,
        "Wärmedämmung":     df_insulation,
    }


import math

bom = build_bom(nodes, edges, sp, results)

# ---------------------------------------------------------------------------
# Display BOM
# ---------------------------------------------------------------------------

sections = [
    ("🏭 Aussengeräte (Kältemaschinen)", "Aussengeräte"),
    ("🌡️ Innengeräte (Gebläsekonvektoren)", "Innengeräte"),
    ("🔵 Rohrleitungen Geberit FlowFit", "Rohre FlowFit"),
    ("🔩 Formteile & Armaturen", "Formteile"),
    ("🔧 Hydraulik-Zubehör", "Hydraulik-Zubehör"),
    ("🧊 Wärmedämmung", "Wärmedämmung"),
]

for section_title, key in sections:
    df = bom[key]
    st.markdown(f'<div class="bom-section"><div class="bom-title">{section_title}</div></div>', unsafe_allow_html=True)
    if df.empty:
        st.info(f"Keine Einträge für '{key}'.")
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)
    st.markdown("")

# ---------------------------------------------------------------------------
# If no calculation results yet — note
# ---------------------------------------------------------------------------
if not results:
    st.warning(
        "ℹ️ Hydraulikberechnung noch nicht ausgeführt. "
        "Rohrdimensionierung basiert auf Schätzwerten (DN25). "
        "Bitte Hydraulikberechnung ausführen für exakte Rohrdurchmesser."
    )

# ---------------------------------------------------------------------------
# Summary statistics
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("## Mengenzusammenfassung")

col1, col2, col3, col4 = st.columns(4)

df_pipes = bom["Rohre FlowFit"]
total_pipe_m = df_pipes["Länge netto [m]"].sum() if not df_pipes.empty and "Länge netto [m]" in df_pipes.columns else 0.0
total_pipe_waste = df_pipes["Länge inkl. Verschnitt"].sum() if not df_pipes.empty and "Länge inkl. Verschnitt" in df_pipes.columns else 0.0
df_fit = bom["Formteile"]
total_fittings = df_fit["Menge"].sum() if not df_fit.empty and "Menge" in df_fit.columns else 0
n_ch = len(bom["Aussengeräte"])
n_fc_bom = len(bom["Innengeräte"])

col1.metric("Rohrlänge gesamt (netto)", f"{total_pipe_m:.1f} m")
col2.metric("Rohrlänge inkl. 10% Verschnitt", f"{total_pipe_waste:.1f} m")
col3.metric("Formteile & Armaturen", f"{int(total_fittings)} Stück")
col4.metric("Geräte gesamt", f"{n_ch} Kältemaschine(n) + {n_fc_bom} GK")

# ---------------------------------------------------------------------------
# Export buttons
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("## Export")

ex_col1, ex_col2 = st.columns(2)

with ex_col1:
    if st.button("📊 Als Excel exportieren", use_container_width=True, type="primary"):
        excel_bytes = export_bom_to_excel(bom)
        project_name = sp.get("project_name","Projekt").replace(" ", "_")
        st.download_button(
            label="💾 Excel-Datei herunterladen",
            data=excel_bytes,
            file_name=f"{project_name}_Materialliste.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

with ex_col2:
    if st.button("📄 Als CSV exportieren", use_container_width=True):
        # Combine all tables to one CSV
        all_rows = []
        for sheet_name, df in bom.items():
            if not df.empty:
                df_copy = df.copy()
                df_copy.insert(0, "Kategorie", sheet_name)
                all_rows.append(df_copy)
        if all_rows:
            df_all = pd.concat(all_rows, ignore_index=True)
            csv_str = df_all.to_csv(index=False, sep=";", encoding="utf-8-sig")
            project_name = sp.get("project_name","Projekt").replace(" ", "_")
            st.download_button(
                label="💾 CSV herunterladen",
                data=csv_str.encode("utf-8-sig"),
                file_name=f"{project_name}_Materialliste.csv",
                mime="text/csv",
                use_container_width=True,
            )

st.markdown("---")
st.markdown("*Weiter zum technischen Bericht →*")
st.page_link("pages/4_📈_Technical_Report.py", label="📈 Zum technischen Bericht", icon="📈")
