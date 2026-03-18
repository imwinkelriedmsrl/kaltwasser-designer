"""
Materialliste (BOM) — Seite 3
Vollständige Stückliste mit Geberit FlowFit Artikelnummern, Excel-Export.
Enthält: T-Stücke mit Artikelnummern, kein DN16, Pufferspeicher/Ausdehnungsgefäss
wenn nicht integriert.
"""

import math
import streamlit as st
import pandas as pd
from collections import defaultdict
from typing import Dict, List, Any

from utils.helpers import init_session_state, export_bom_to_excel, size_expansion_vessel
from data.geberit_flowfit import (
    FLOWFIT_PIPE_SPECS, water_volume_per_meter,
    FLOWFIT_T_PIECES, FLOWFIT_T_PIECES_REDUCING,
    FLOWFIT_COUPLINGS, FLOWFIT_ELBOWS_90, FLOWFIT_REDUCERS,
    get_t_piece_article, get_elbow_article, get_coupling_article,
)
from data.component_library import CHILLERS, FAN_COILS, get_chiller, get_fan_coil

# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Materialliste | Kaltwasser Designer",
    layout="wide",
    page_icon="📋",
)
init_session_state(st)

st.markdown("""
<style>
.bom-section {
    background: #f8f9fa; border-left: 4px solid #1565C0;
    padding: 12px 16px; margin-bottom: 16px; border-radius: 0 8px 8px 0;
}
.bom-title { font-size: 1.1rem; font-weight: 700; color: #1565C0; margin-bottom: 8px; }
</style>
""", unsafe_allow_html=True)

st.markdown("# 📋 Materialliste (Stückliste / BOM)")
st.markdown("Vollständige Stückliste für die Geberit FlowFit Kaltwasseranlage inkl. Artikelnummern.")

nodes   = st.session_state.nodes
edges   = st.session_state.edges
sp      = st.session_state.system_params
results = st.session_state.calc_results

if not nodes:
    st.warning("Kein Netzwerk vorhanden. Bitte zuerst im Netzwerk-Editor ein Netz anlegen.")
    st.page_link("pages/1_🔧_Network_Editor.py", label="Zum Netzwerk-Editor", icon="🔧")
    st.stop()

# ---------------------------------------------------------------------------
# Build BOM
# ---------------------------------------------------------------------------

def _get_fc_display_info(node: Dict):
    """Return (article, description, cooling_str, airflow_str, connection_str) for a FAN_COIL node."""
    props = node.get("props", {})
    model_key = props.get("model", node.get("model", "Kampmann_KaCool_W_Size4"))

    if model_key == "custom":
        article     = "—"
        description = f"{props.get('manufacturer','')} {props.get('model_name','Benutzerdef.')}"
        cooling_str = f"{props.get('cooling_W','?')} W"
        airflow_str = "—"
        conn_str    = props.get("connection", '½"')
    else:
        try:
            fc = get_fan_coil(model_key)
            perf10  = fc["performance"][10]
            article     = fc.get("article", "—")
            description = f"{fc['manufacturer']} {fc['model']}"
            cooling_str = f"{perf10['cooling_total_W']} W"
            airflow_str = f"{perf10['airflow_m3h']} m³/h"
            conn_str    = fc.get("connection_supply", '½"')
        except Exception:
            article     = "—"
            description = model_key
            cooling_str = "—"
            airflow_str = "—"
            conn_str    = "—"

    return article, description, cooling_str, airflow_str, conn_str


def _fitting_article(fit_type: str, dn: int) -> str:
    """Return article number for a fitting type and DN."""
    if fit_type in ("t_through", "t_branch"):
        info = FLOWFIT_T_PIECES.get(dn, {})
        return info.get("article", "—")
    elif fit_type == "elbow_90":
        info = FLOWFIT_ELBOWS_90.get(dn, {})
        return info.get("article", "—")
    elif fit_type == "coupling":
        info = FLOWFIT_COUPLINGS.get(dn, {})
        return info.get("article", "—")
    elif fit_type == "reducer":
        # reducer needs both sizes — fall back generic
        return "628.XXX.XX.1"
    return "—"


def build_bom(nodes, edges, sp, results) -> Dict[str, pd.DataFrame]:
    """Compile the full bill of materials."""

    # ------------------------------------------------------------------
    # 1. Outdoor units
    # ------------------------------------------------------------------
    chiller_rows = []
    for n in nodes:
        if n.get("type") != "CHILLER":
            continue
        props     = n.get("props", {})
        model_key = props.get("model", n.get("model", "Climaveneta_iBX2_G07_27Y"))

        if model_key == "custom":
            row = {
                "Pos.":          len(chiller_rows) + 1,
                "Artikelnummer": "—",
                "Beschreibung":  f"{props.get('manufacturer','')} {props.get('model_name','Benutzerdef.')}",
                "Typ":           "Benutzerdefiniert",
                "Kälteleistung": f"{props.get('cooling_capacity_kW','?')} kW",
                "Kältemittel":   props.get("refrigerant", "—"),
                "Anschluss":     props.get("connection_supply", "—"),
                "Bezeichnung":   n.get("label", ""),
                "Pufferspeicher": f"{props.get('buffer_tank_L','—')} L" if props.get("buffer_tank_integrated") else "extern",
                "Ausdehnungsgef.": f"{props.get('expansion_vessel_L','—')} L" if props.get("expansion_vessel_integrated") else "extern",
                "Menge":         1,
                "Einheit":       "Stück",
            }
        else:
            try:
                ch = get_chiller(model_key)
                # Use node props overrides if present
                buf_int = props.get("buffer_tank_integrated", ch.get("buffer_tank_integrated", False))
                buf_L   = props.get("buffer_tank_L",   ch.get("buffer_tank_L",   0))
                exp_int = props.get("expansion_vessel_integrated", ch.get("expansion_vessel_integrated", False))
                exp_L   = props.get("expansion_vessel_L", ch.get("expansion_vessel_L", 0))
                row = {
                    "Pos.":          len(chiller_rows) + 1,
                    "Artikelnummer": ch.get("article", "—"),
                    "Beschreibung":  f"{ch['manufacturer']} {ch['model']}",
                    "Typ":           ch["type"],
                    "Kälteleistung": f"{ch['cooling_capacity_kW']} kW",
                    "Kältemittel":   ch["refrigerant"],
                    "Anschluss":     ch.get("connection_supply", "—"),
                    "Bezeichnung":   n.get("label", ""),
                    "Pufferspeicher": f"{buf_L} L (integriert)" if buf_int else "extern",
                    "Ausdehnungsgef.": f"{exp_L} L (integriert)" if exp_int else "extern",
                    "Menge":         1,
                    "Einheit":       "Stück",
                }
            except Exception:
                row = {
                    "Pos.": len(chiller_rows) + 1,
                    "Artikelnummer": "—", "Beschreibung": model_key,
                    "Typ": "—", "Kälteleistung": "—", "Kältemittel": "—",
                    "Anschluss": "—", "Bezeichnung": n.get("label", ""),
                    "Pufferspeicher": "—", "Ausdehnungsgef.": "—",
                    "Menge": 1, "Einheit": "Stück",
                }
        chiller_rows.append(row)

    df_chillers = pd.DataFrame(chiller_rows) if chiller_rows else pd.DataFrame(
        columns=["Pos.", "Artikelnummer", "Beschreibung", "Typ",
                 "Kälteleistung", "Kältemittel", "Anschluss", "Bezeichnung",
                 "Pufferspeicher", "Ausdehnungsgef.", "Menge", "Einheit"]
    )

    # ------------------------------------------------------------------
    # 2. Indoor units
    # ------------------------------------------------------------------
    fc_rows = []
    for n in nodes:
        if n.get("type") != "FAN_COIL":
            continue
        props = n.get("props", {})
        article, description, cooling_str, airflow_str, conn_str = _get_fc_display_info(n)
        room = props.get("room", n.get("room", "—"))
        fc_rows.append({
            "Pos.":          len(fc_rows) + 1,
            "Artikelnummer": article,
            "Beschreibung":  description,
            "Raum":          room,
            "Kühlleistung":  cooling_str,
            "Luftvolumen":   airflow_str,
            "Anschluss":     conn_str,
            "Bezeichnung":   n.get("label", ""),
            "Menge":         1,
            "Einheit":       "Stück",
        })

    df_fancoils = pd.DataFrame(fc_rows) if fc_rows else pd.DataFrame(
        columns=["Pos.", "Artikelnummer", "Beschreibung", "Raum", "Kühlleistung",
                 "Luftvolumen", "Anschluss", "Bezeichnung", "Menge", "Einheit"]
    )

    # ------------------------------------------------------------------
    # 3. Pipes (minimum DN20)
    # ------------------------------------------------------------------
    pipe_lengths: Dict[int, float] = defaultdict(float)

    for edge in edges:
        eid      = edge["id"]
        length_m = edge.get("length_m", 0.0)
        dn = 25  # default if not yet sized
        if results and "pipe_sizes" in results:
            dn = results["pipe_sizes"].get(eid, 25)
        # Enforce minimum DN20
        dn = max(dn, 20)
        pipe_lengths[dn] += length_m

    pipe_rows = []
    for dn in sorted(pipe_lengths.keys()):
        raw_length        = pipe_lengths[dn]
        length_with_waste = raw_length * 1.10
        bars_5m           = math.ceil(length_with_waste / 5.0)
        spec              = FLOWFIT_PIPE_SPECS.get(dn, {})
        inner_mm          = spec.get("di_mm", "?")
        article           = spec.get("article", "—")
        pipe_rows.append({
            "Pos.":                    len(pipe_rows) + 1,
            "Artikelnummer":           article,
            "Beschreibung":            spec.get("desc", f"Geberit FlowFit Rohr Ø{dn} mm"),
            "Nenndurchmesser":         f"DN{dn}",
            "Innendurchmesser":        f"{inner_mm} mm",
            "Länge netto [m]":         round(raw_length, 2),
            "Länge inkl. Verschnitt":  round(length_with_waste, 2),
            "Anzahl Stangen (5m)":     bars_5m,
            "Einheit":                 "Stück (5m Stangen)",
        })

    df_pipes = pd.DataFrame(pipe_rows) if pipe_rows else pd.DataFrame(
        columns=["Pos.", "Artikelnummer", "Beschreibung", "Nenndurchmesser", "Innendurchmesser",
                 "Länge netto [m]", "Länge inkl. Verschnitt", "Anzahl Stangen (5m)", "Einheit"]
    )

    # ------------------------------------------------------------------
    # 4. Fittings with article numbers
    # ------------------------------------------------------------------
    fitting_counts: Dict[str, int] = defaultdict(int)

    for edge in edges:
        eid = edge["id"]
        dn  = 25
        if results and "pipe_sizes" in results:
            dn = results["pipe_sizes"].get(eid, 25)
        dn = max(dn, 20)
        fittings_src = edge.get("fittings", {})
        if not fittings_src:
            props = edge.get("props", {})
            fittings_src = props.get("fittings_raw", {})
        for fit_type, count in fittings_src.items():
            key = f"{fit_type}|DN{dn}"
            fitting_counts[key] += count

    fitting_name_map = {
        "elbow_90":        "90° Bogen",
        "t_through":       "T-Stück (Durchgang)",
        "t_branch":        "T-Stück (Abzweig)",
        "coupling":        "Kupplung (Verbinder)",
        "valve_isolation": "Absperrventil",
        "valve_balancing": "Regulierventil",
        "air_vent":        "Entlüftungsventil",
        "reducer":         "Reduzierstück",
        "check_valve":     "Rückschlagventil",
    }

    fitting_rows = []
    for key, count in sorted(fitting_counts.items()):
        fit_type, dn_str = key.split("|")
        dn_int = int(dn_str.replace("DN", ""))
        name   = fitting_name_map.get(fit_type, fit_type)
        art    = _fitting_article(fit_type, dn_int)
        fitting_rows.append({
            "Pos.":         len(fitting_rows) + 1,
            "Artikelnummer": art,
            "Beschreibung": f"Geberit FlowFit {name} {dn_str}",
            "Typ":          name,
            "DN":           dn_str,
            "Menge":        count,
            "Einheit":      "Stück",
        })

    # Add stich pipe isolation valves for fan coils (minimum DN20)
    n_fc = sum(1 for n in nodes if n.get("type") == "FAN_COIL")
    if n_fc > 0:
        art_iso_20 = FLOWFIT_COUPLINGS.get(20, {}).get("article", "—")
        fitting_rows.append({
            "Pos.":         len(fitting_rows) + 1,
            "Artikelnummer": "—",
            "Beschreibung": 'Absperrventil DN20 (½" Stichleitung GK)',
            "Typ":          "Absperrventil",
            "DN":           "DN20",
            "Menge":        n_fc * 2,
            "Einheit":      "Stück",
        })
        fitting_rows.append({
            "Pos.":         len(fitting_rows) + 1,
            "Artikelnummer": "—",
            "Beschreibung": "Regulierventil DN20 (Stichleitung GK)",
            "Typ":          "Regulierventil",
            "DN":           "DN20",
            "Menge":        n_fc,
            "Einheit":      "Stück",
        })

    df_fittings = pd.DataFrame(fitting_rows) if fitting_rows else pd.DataFrame(
        columns=["Pos.", "Artikelnummer", "Beschreibung", "Typ", "DN", "Menge", "Einheit"]
    )

    # ------------------------------------------------------------------
    # 5. Hydraulic accessories
    #    Check if expansion vessel / safety valve / buffer tank are
    #    already integrated in the chiller — if not, add them to BOM
    # ------------------------------------------------------------------
    access_rows = []

    # Determine what is integrated in chillers
    exp_vessel_integrated   = False
    safety_valve_integrated = False
    buffer_tank_integrated  = False
    for n in nodes:
        if n.get("type") == "CHILLER":
            props = n.get("props", {})
            model = props.get("model", "")
            ch_data = {}
            if model and model != "custom":
                try:
                    ch_data = get_chiller(model)
                except Exception:
                    pass
            exp_vessel_integrated   = props.get("expansion_vessel_integrated",   ch_data.get("expansion_vessel_integrated",   False))
            safety_valve_integrated = props.get("safety_valve_integrated",      ch_data.get("safety_valve_integrated",      False))
            buffer_tank_integrated  = props.get("buffer_tank_integrated",       ch_data.get("buffer_tank_integrated",       False))
            break

    n_vents = max(1, n_fc // 2 + 1)
    access_rows.append({
        "Pos.": 1, "Artikelnummer": "—",
        "Beschreibung": "Automatischer Entlüfter DN15",
        "Menge": n_vents, "Einheit": "Stück",
        "Bemerkung": "1 pro Kreisläufe / Hochpunkt",
    })
    access_rows.append({
        "Pos.": 2, "Artikelnummer": "—",
        "Beschreibung": "Befüll- und Entleerungshahn DN20",
        "Menge": 2, "Einheit": "Stück",
        "Bemerkung": "VL + RL, tiefster Punkt",
    })
    access_rows.append({
        "Pos.": 3, "Artikelnummer": "—",
        "Beschreibung": "Manometeranschluss PN16, DN15",
        "Menge": 2, "Einheit": "Stück",
        "Bemerkung": "Vorlauf + Rücklauf",
    })

    total_vol_L = sum(
        water_volume_per_meter(
            max(results["pipe_sizes"].get(e["id"], 25), 20) if results else 25
        ) * e.get("length_m", 1.0)
        for e in edges
    )

    # Expansion vessel — only if NOT integrated in chiller
    if not exp_vessel_integrated:
        exp = size_expansion_vessel(
            total_volume_L=max(total_vol_L, 20.0),
            t_supply_C=float(sp.get("t_supply_C", 7.0)),
            glycol_pct=int(sp.get("glycol_pct", 30)),
        )
        exp_size = exp["vn_L"]
        std_sizes = [8, 12, 18, 24, 35, 50, 80, 100, 150, 200]
        exp_std   = next((s for s in std_sizes if s >= exp_size), std_sizes[-1])
        access_rows.append({
            "Pos.": 4, "Artikelnummer": "—",
            "Beschreibung": f"Membran-Druckausdehnungsgefäss {exp_std} L",
            "Menge": 1, "Einheit": "Stück",
            "Bemerkung": f"Berechnetes Min. {exp_size:.1f} L, Vorladedruck {exp['p0_bar']:.2f} bar",
        })
    else:
        access_rows.append({
            "Pos.": 4, "Artikelnummer": "—",
            "Beschreibung": "Ausdehnungsgefäss — integriert in Kältemaschine",
            "Menge": 0, "Einheit": "Stück",
            "Bemerkung": "In Kältemaschine integriert",
        })

    # Safety valve — only if NOT integrated
    if not safety_valve_integrated:
        access_rows.append({
            "Pos.": 5, "Artikelnummer": "—",
            "Beschreibung": "Sicherheitsventil 3 bar, DN15",
            "Menge": 1, "Einheit": "Stück",
            "Bemerkung": "Absicherung Ausdehnungsgefäss",
        })
    else:
        access_rows.append({
            "Pos.": 5, "Artikelnummer": "—",
            "Beschreibung": "Sicherheitsventil — integriert in Kältemaschine",
            "Menge": 0, "Einheit": "Stück",
            "Bemerkung": "In Kältemaschine integriert",
        })

    # Buffer tank — only if NOT integrated
    if not buffer_tank_integrated:
        access_rows.append({
            "Pos.": 6, "Artikelnummer": "—",
            "Beschreibung": "Pufferspeicher (extern)",
            "Menge": 1, "Einheit": "Stück",
            "Bemerkung": "Externes Pufferspeicher — Grösse projektspezifisch festlegen",
        })

    glycol_needed_L = max(total_vol_L * float(sp.get("glycol_pct", 30)) / 100.0, 5.0)
    access_rows.append({
        "Pos.": len(access_rows) + 1, "Artikelnummer": "—",
        "Beschreibung": "Ethylenglykol 40% Fertigmischung, Kanister",
        "Menge": math.ceil(glycol_needed_L / 20.0),
        "Einheit": "Kanister (20 L)",
        "Bemerkung": f"Bedarf ca. {glycol_needed_L:.0f} L für {sp.get('glycol_pct',30)}% Konzentration",
    })

    df_accessories = pd.DataFrame(access_rows)

    # ------------------------------------------------------------------
    # 6. Thermal insulation
    # ------------------------------------------------------------------
    insulation_thickness = {20: 13, 25: 19, 32: 19, 40: 25, 50: 25, 63: 32, 75: 32}
    insulation_rows = []
    for dn in sorted(pipe_lengths.keys()):
        raw_length = pipe_lengths[dn]
        insul_mm   = insulation_thickness.get(dn, 25)
        insulation_rows.append({
            "Pos.":                   len(insulation_rows) + 1,
            "Beschreibung":           f"Kautschuk-Rohrisolation Ø{dn}mm, {insul_mm}mm Wandstärke",
            "DN":                     f"DN{dn}",
            "Dämmstärke [mm]":        insul_mm,
            "Länge netto [m]":        round(raw_length, 2),
            "Länge inkl. Verschnitt": round(raw_length * 1.10, 2),
            "Einheit":                "m",
        })

    df_insulation = pd.DataFrame(insulation_rows) if insulation_rows else pd.DataFrame(
        columns=["Pos.", "Beschreibung", "DN", "Dämmstärke [mm]",
                 "Länge netto [m]", "Länge inkl. Verschnitt", "Einheit"]
    )

    return {
        "Aussengeräte":      df_chillers,
        "Innengeräte":       df_fancoils,
        "Rohre FlowFit":     df_pipes,
        "Formteile":         df_fittings,
        "Hydraulik-Zubehör": df_accessories,
        "Wärmedämmung":      df_insulation,
    }


bom = build_bom(nodes, edges, sp, results)

# ---------------------------------------------------------------------------
# Display BOM
# ---------------------------------------------------------------------------
sections = [
    ("Aussengeräte (Kältemaschinen)",       "Aussengeräte"),
    ("Innengeräte (Gebläsekonvektoren)",     "Innengeräte"),
    ("Rohrleitungen Geberit FlowFit",        "Rohre FlowFit"),
    ("Formteile & Armaturen",               "Formteile"),
    ("Hydraulik-Zubehör",                   "Hydraulik-Zubehör"),
    ("Wärmedämmung",                        "Wärmedämmung"),
]

for section_title, key in sections:
    df = bom[key]
    st.markdown(
        f'<div class="bom-section"><div class="bom-title">{section_title}</div></div>',
        unsafe_allow_html=True,
    )
    if df.empty:
        st.info(f"Keine Einträge für '{key}'.")
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)

if not results:
    st.warning(
        "Hydraulikberechnung noch nicht ausgeführt. "
        "Rohrdimensionierung basiert auf Schätzwerten (DN25, min DN20). "
        "Bitte Hydraulikberechnung ausführen für exakte Rohrdurchmesser."
    )

# ---------------------------------------------------------------------------
# Summary statistics
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("## Mengenzusammenfassung")

col1, col2, col3, col4 = st.columns(4)

df_pipes_bom = bom["Rohre FlowFit"]
total_pipe_m     = df_pipes_bom["Länge netto [m]"].sum() if not df_pipes_bom.empty and "Länge netto [m]" in df_pipes_bom.columns else 0.0
total_pipe_waste = df_pipes_bom["Länge inkl. Verschnitt"].sum() if not df_pipes_bom.empty and "Länge inkl. Verschnitt" in df_pipes_bom.columns else 0.0
df_fit_bom       = bom["Formteile"]
total_fittings   = df_fit_bom["Menge"].sum() if not df_fit_bom.empty and "Menge" in df_fit_bom.columns else 0
n_ch_bom         = len(bom["Aussengeräte"])
n_fc_bom         = len(bom["Innengeräte"])

col1.metric("Rohrlänge gesamt (netto)",          f"{total_pipe_m:.1f} m")
col2.metric("Rohrlänge inkl. 10% Verschnitt",    f"{total_pipe_waste:.1f} m")
col3.metric("Formteile & Armaturen",             f"{int(total_fittings)} Stück")
col4.metric("Geräte gesamt",                     f"{n_ch_bom} Kältemaschine(n) + {n_fc_bom} GK")

# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("## Export")

ex_col1, ex_col2 = st.columns(2)

with ex_col1:
    if st.button("Als Excel exportieren", use_container_width=True, type="primary"):
        excel_bytes  = export_bom_to_excel(bom)
        project_name = sp.get("project_name", "Projekt").replace(" ", "_")
        st.download_button(
            label="Excel-Datei herunterladen",
            data=excel_bytes,
            file_name=f"{project_name}_Materialliste.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

with ex_col2:
    if st.button("Als CSV exportieren", use_container_width=True):
        all_rows = []
        for sheet_name, df in bom.items():
            if not df.empty:
                df_copy = df.copy()
                df_copy.insert(0, "Kategorie", sheet_name)
                all_rows.append(df_copy)
        if all_rows:
            df_all       = pd.concat(all_rows, ignore_index=True)
            csv_str      = df_all.to_csv(index=False, sep=";", encoding="utf-8-sig")
            project_name = sp.get("project_name", "Projekt").replace(" ", "_")
            st.download_button(
                label="CSV herunterladen",
                data=csv_str.encode("utf-8-sig"),
                file_name=f"{project_name}_Materialliste.csv",
                mime="text/csv",
                use_container_width=True,
            )

st.markdown("---")
st.page_link("pages/4_📈_Technical_Report.py", label="Weiter zum technischen Bericht", icon="📈")
