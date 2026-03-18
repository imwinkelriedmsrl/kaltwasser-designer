"""
Technischer Bericht — Seite 4
Systemzusammenfassung, Leistungsdaten, Lärmbewertung, Kältemitteldaten.
Enthält: Pufferspeicher, Ausdehnungsgefäss, Sicherheitsventil im Kältemaschinen-Abschnitt.
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from datetime import datetime

from utils.helpers import (
    init_session_state,
    get_freeze_point_C,
    check_frosting,
    sound_pressure_at_distance,
    size_expansion_vessel,
    FREEZE_POINTS_EG,
    FREEZE_POINTS_PG,
)
from data.component_library import CHILLERS, FAN_COILS, get_chiller, get_fan_coil
from data.geberit_flowfit import get_fluid_properties, FLOWFIT_PIPE_SPECS

# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Technischer Bericht | Kaltwasser Designer",
    layout="wide",
    page_icon="📈",
)
init_session_state(st)

st.markdown("""
<style>
@media print {
    section[data-testid="stSidebar"] { display: none !important; }
    .stButton { display: none !important; }
    .no-print { display: none !important; }
}
.report-header {
    background: linear-gradient(135deg, #0D47A1 0%, #1565C0 100%);
    color: white; padding: 24px 32px; border-radius: 12px; margin-bottom: 24px;
}
.report-header h1 { color: white; margin: 0; font-size: 2rem; }
.report-header p  { color: #bbdefb; margin: 4px 0 0 0; }
.data-card {
    background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 8px;
    padding: 16px; margin-bottom: 12px;
}
.data-card h4 { color: #1565C0; margin: 0 0 10px 0; font-size: 0.95rem; font-weight: 700; }
.spec-row {
    display: flex; justify-content: space-between; padding: 3px 0;
    border-bottom: 1px solid #e9ecef; font-size: 0.9rem;
}
.spec-key { color: #555; }
.spec-val { font-weight: 600; color: #212529; }
.section-divider { border: none; border-top: 3px solid #1565C0; margin: 28px 0 20px 0; }
.integrated-badge {
    display: inline-block; background: #d4edda; color: #155724;
    padding: 2px 8px; border-radius: 3px; font-size: 0.8rem; font-weight: 600;
}
.external-badge {
    display: inline-block; background: #fff3cd; color: #856404;
    padding: 2px 8px; border-radius: 3px; font-size: 0.8rem; font-weight: 600;
}
</style>
""", unsafe_allow_html=True)

nodes        = st.session_state.nodes
edges        = st.session_state.edges
sp           = st.session_state.system_params
results      = st.session_state.calc_results

chiller_nodes  = [n for n in nodes if n.get("type") == "CHILLER"]
fan_coil_nodes = [n for n in nodes if n.get("type") == "FAN_COIL"]
glycol_pct     = int(sp.get("glycol_pct", 30))
glycol_type    = sp.get("glycol_type", "Ethylenglykol")
t_sup          = float(sp.get("t_supply_C", 7.0))
t_ret          = float(sp.get("t_return_C", 12.0))
project_name   = sp.get("project_name", "Kaltwasserprojekt")
engineer       = sp.get("engineer", "—")
project_num    = sp.get("project_number", "—")

# Resolve primary chiller data
chiller_data = None
chiller_node_props = {}
if chiller_nodes:
    cn = chiller_nodes[0]
    chiller_node_props = cn.get("props", {})
    model = chiller_node_props.get("model", cn.get("model", "Climaveneta_iBX2_G07_27Y"))
    if model == "custom":
        chiller_data = chiller_node_props
    else:
        try:
            chiller_data = get_chiller(model)
            # Merge pump data and auxiliary data from node props
            chiller_data = dict(chiller_data)
            for k in ("pump_head_kPa", "expansion_vessel_integrated", "expansion_vessel_L",
                      "safety_valve_integrated", "safety_valve_bar",
                      "buffer_tank_integrated", "buffer_tank_L",
                      "buffer_tank_model", "buffer_tank_article"):
                if k in chiller_node_props:
                    chiller_data[k] = chiller_node_props[k]
        except Exception:
            pass

# Total installed indoor load
total_indoor_W = 0.0
for n in fan_coil_nodes:
    props = n.get("props", {})
    model = props.get("model", n.get("model", "Kampmann_KaCool_W_Size4"))
    try:
        if model == "custom":
            total_indoor_W += float(props.get("cooling_W", 3000))
        else:
            fc = get_fan_coil(model)
            v_max = max(fc["performance"].keys())
            total_indoor_W += fc["performance"][v_max]["cooling_total_W"]
    except Exception:
        total_indoor_W += 3000.0

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
now = datetime.now()

st.markdown(f"""
<div class="report-header">
  <h1>Technischer Bericht</h1>
  <p>
    <strong>{project_name}</strong> &nbsp;|&nbsp;
    Projektnummer: {project_num} &nbsp;|&nbsp;
    Ingenieur: {engineer} &nbsp;|&nbsp;
    Datum: {now.strftime('%d.%m.%Y')}
  </p>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# 1. System overview
# ---------------------------------------------------------------------------
st.markdown("## 1. Systemübersicht")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Projektname",           project_name)
c2.metric("Kältemaschinen",        len(chiller_nodes))
c3.metric("Gebläsekonvektoren",    len(fan_coil_nodes))
c4.metric("Installierte Kälteleistung", f"{total_indoor_W/1000:.2f} kW")

c5, c6, c7, c8 = st.columns(4)
c5.metric("Vorlauftemperatur",     f"{t_sup:.1f} °C")
c6.metric("Rücklauftemperatur",    f"{t_ret:.1f} °C")
c7.metric("Temperaturdifferenz",   f"{t_ret - t_sup:.1f} K")
c8.metric("Glykolmischung",        f"{glycol_type} {glycol_pct}%")

# ---------------------------------------------------------------------------
# 2. Outdoor unit (Kältemaschine)
# ---------------------------------------------------------------------------
st.markdown('<hr class="section-divider">', unsafe_allow_html=True)
st.markdown("## 2. Kältemaschine (Aussengerät)")

if not chiller_data:
    st.info("Keine Kältemaschine im Netzwerk vorhanden.")
else:
    ch = chiller_data
    col_ch1, col_ch2, col_ch3 = st.columns(3)

    with col_ch1:
        st.markdown('<div class="data-card"><h4>Leistungsdaten</h4>', unsafe_allow_html=True)
        for k, v in [
            ("Kälteleistung",      f"{ch.get('cooling_capacity_kW','?')} kW"),
            ("Leistungsaufnahme",  f"{ch.get('power_input_kW','?')} kW"),
            ("EER",                f"{ch.get('eer','?')}"),
            ("Vorlauftemperatur",  f"{ch.get('t_supply_C','?')} °C"),
            ("Rücklauftemperatur", f"{ch.get('t_return_C','?')} °C"),
            ("Volumenstrom",       f"{ch.get('flow_rate_m3h','?')} m³/h"),
        ]:
            st.markdown(
                f'<div class="spec-row"><span class="spec-key">{k}</span>'
                f'<span class="spec-val">{v}</span></div>',
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)

    with col_ch2:
        st.markdown('<div class="data-card"><h4>Hydraulik & Pumpe</h4>', unsafe_allow_html=True)
        pump_head_disp = chiller_node_props.get("pump_head_kPa", ch.get("pump_head_kPa", "?"))
        pump_int_disp  = chiller_node_props.get("pump_integrated", ch.get("pump_integrated", True))
        pump_type_disp = chiller_node_props.get("pump_type", ch.get("pump_type", "—"))
        pump_flow_disp = chiller_node_props.get("pump_flow_max_m3h", ch.get("pump_flow_max_m3h", "—"))
        for k, v in [
            ("Druckverlust Verdampfer",    f"{ch.get('dp_evaporator_kPa','?')} kPa"),
            ("Pumpe integriert",           "Ja" if pump_int_disp else "Nein"),
            ("Pumpentyp",                  str(pump_type_disp)),
            ("Pumpenförderhöhe",           f"{pump_head_disp} kPa"),
            ("Pumpenvolumenstrom max.",     f"{pump_flow_disp} m³/h"),
            ("Anschluss VL",               ch.get("connection_supply", "—")),
            ("Glykolkonzentration",        f"{ch.get('glycol_pct',30)} %"),
        ]:
            st.markdown(
                f'<div class="spec-row"><span class="spec-key">{k}</span>'
                f'<span class="spec-val">{v}</span></div>',
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)

    with col_ch3:
        st.markdown('<div class="data-card"><h4>Allgemeine Daten</h4>', unsafe_allow_html=True)
        for k, v in [
            ("Typ",           ch.get("type", ch.get("model_name", "Benutzerdefiniert"))),
            ("Aufstellung",   ch.get("installation", "—")),
            ("Kältemittel",   ch.get("refrigerant", "—")),
            ("GWP",           str(ch.get("gwp", "—"))),
            ("Schallleistung", f"{ch.get('sound_power_dBa','?')} dB(A)"),
            ("Abm. (L×B×H)",  f"{ch.get('length_mm','?')}×{ch.get('width_mm','?')}×{ch.get('height_mm','?')} mm"
             if ch.get("length_mm") else "—"),
            ("Gewicht",       f"{ch.get('weight_kg','?')} kg" if ch.get("weight_kg") else "—"),
        ]:
            st.markdown(
                f'<div class="spec-row"><span class="spec-key">{k}</span>'
                f'<span class="spec-val">{v}</span></div>',
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)

    # --- Expansion vessel, safety valve, buffer tank ---
    st.markdown("### 2.1 Hydraulische Zusatzkomponenten")
    aux_col1, aux_col2, aux_col3 = st.columns(3)

    with aux_col1:
        exp_int = ch.get("expansion_vessel_integrated", False)
        exp_L   = ch.get("expansion_vessel_L", "—")
        badge   = '<span class="integrated-badge">Integriert</span>' if exp_int else '<span class="external-badge">Extern erforderlich</span>'
        st.markdown(f'<div class="data-card"><h4>Ausdehnungsgefäss {badge}</h4>', unsafe_allow_html=True)
        for k, v in [
            ("Status",   "Integriert" if exp_int else "Extern"),
            ("Volumen",  f"{exp_L} L" if exp_L != "—" else "—"),
        ]:
            st.markdown(
                f'<div class="spec-row"><span class="spec-key">{k}</span>'
                f'<span class="spec-val">{v}</span></div>',
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)

    with aux_col2:
        sv_int = ch.get("safety_valve_integrated", False)
        sv_bar = ch.get("safety_valve_bar", "—")
        badge  = '<span class="integrated-badge">Integriert</span>' if sv_int else '<span class="external-badge">Extern erforderlich</span>'
        st.markdown(f'<div class="data-card"><h4>Sicherheitsventil {badge}</h4>', unsafe_allow_html=True)
        for k, v in [
            ("Status",           "Integriert" if sv_int else "Extern"),
            ("Ansprechdruck",    f"{sv_bar} bar" if sv_bar != "—" else "—"),
        ]:
            st.markdown(
                f'<div class="spec-row"><span class="spec-key">{k}</span>'
                f'<span class="spec-val">{v}</span></div>',
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)

    with aux_col3:
        buf_int    = ch.get("buffer_tank_integrated", False)
        buf_L      = ch.get("buffer_tank_L", "—")
        buf_model  = ch.get("buffer_tank_model", "—")
        buf_art    = ch.get("buffer_tank_article", "—")
        badge      = '<span class="integrated-badge">Integriert</span>' if buf_int else '<span class="external-badge">Extern erforderlich</span>'
        st.markdown(f'<div class="data-card"><h4>Pufferspeicher {badge}</h4>', unsafe_allow_html=True)
        for k, v in [
            ("Status",       "Integriert" if buf_int else "Extern"),
            ("Volumen",      f"{buf_L} L" if buf_L != "—" and buf_L else "—"),
            ("Modell",       buf_model if buf_model != "—" else "—"),
            ("Artikelnr.",   buf_art if buf_art != "—" else "—"),
        ]:
            st.markdown(
                f'<div class="spec-row"><span class="spec-key">{k}</span>'
                f'<span class="spec-val">{v}</span></div>',
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# 3. Indoor units (Gebläsekonvektoren)
# ---------------------------------------------------------------------------
st.markdown('<hr class="section-divider">', unsafe_allow_html=True)
st.markdown("## 3. Gebläsekonvektoren (Innengeräte)")

if not fan_coil_nodes:
    st.info("Keine Gebläsekonvektoren im Netzwerk vorhanden.")
else:
    fc_table = []
    for n in fan_coil_nodes:
        props = n.get("props", {})
        model = props.get("model", n.get("model", "Kampmann_KaCool_W_Size4"))
        room  = props.get("room", n.get("room", "—"))

        if model == "custom":
            fc_table.append({
                "Bezeichnung":                   n.get("label", "—"),
                "Raum":                          room,
                "Modell":                        f"[Benutzerdef.] {props.get('model_name','')}",
                "Kühlleistung total [W]":        props.get("cooling_W", "—"),
                "Kühlleistung sensibel [W]":     "—",
                "Luftvolumen [m³/h]":            "—",
                "Schallleistung [dB(A)]":        props.get("sound_dBa", "—"),
                "Wasserfluss [l/h]":             props.get("flow_lh", "—"),
                "Druckverlust [kPa]":            props.get("dp_kPa", "—"),
                "Anschluss":                     props.get("connection", "—"),
            })
        else:
            try:
                fc    = get_fan_coil(model)
                v_max = max(fc["performance"].keys())
                perf  = fc["performance"][v_max]
                fc_table.append({
                    "Bezeichnung":               n.get("label", "—"),
                    "Raum":                      room,
                    "Modell":                    fc["model"],
                    "Kühlleistung total [W]":    perf["cooling_total_W"],
                    "Kühlleistung sensibel [W]": perf["cooling_sensible_W"],
                    "Luftvolumen [m³/h]":        perf["airflow_m3h"],
                    "Schallleistung [dB(A)]":    perf["sound_dBa"],
                    "Wasserfluss [l/h]":         fc["water_flow_lh"],
                    "Druckverlust [kPa]":        fc["water_resistance_kPa"],
                    "Anschluss":                 fc.get("connection_supply", '½"'),
                })
            except Exception:
                pass

    if fc_table:
        df_fc = pd.DataFrame(fc_table)
        st.dataframe(df_fc, use_container_width=True, hide_index=True)

        # Bar chart — only rows with numeric cooling values
        df_chart = df_fc[pd.to_numeric(df_fc["Kühlleistung total [W]"], errors="coerce").notna()].copy()
        df_chart["Kühlleistung total [W]"]    = pd.to_numeric(df_chart["Kühlleistung total [W]"])
        df_chart["Kühlleistung sensibel [W]"] = pd.to_numeric(df_chart["Kühlleistung sensibel [W]"], errors="coerce")

        if not df_chart.empty:
            fig_fc = px.bar(
                df_chart,
                x="Bezeichnung",
                y=["Kühlleistung total [W]", "Kühlleistung sensibel [W]"],
                barmode="group",
                title="Kühlleistung pro Gebläsekonvektor (bei max. Drehzahl)",
                color_discrete_map={
                    "Kühlleistung total [W]":    "#1976d2",
                    "Kühlleistung sensibel [W]": "#64b5f6",
                },
                labels={"value": "Leistung [W]", "Bezeichnung": "Gerät"},
            )
            fig_fc.update_layout(height=380, margin=dict(l=10, r=10, t=40, b=40))
            st.plotly_chart(fig_fc, use_container_width=True)

    # Part-load performance for first library fan coil found
    st.markdown("### Teillast-Analyse")
    ref_node = next(
        (n for n in fan_coil_nodes if n.get("props", {}).get("model", "") != "custom"), None
    )
    if ref_node:
        props_ref = ref_node.get("props", {})
        model_ref = props_ref.get("model", ref_node.get("model", "Kampmann_KaCool_W_Size4"))
        try:
            fc_ref = get_fan_coil(model_ref)
            pl_rows = []
            v_max_ref = max(fc_ref["performance"].keys())
            for v, perf in sorted(fc_ref["performance"].items(), reverse=True):
                pl_rows.append({
                    "Steuersignal [V]":      v,
                    "Kühlleistung [W]":      perf["cooling_total_W"],
                    "Luftvolumen [m³/h]":    perf["airflow_m3h"],
                    "Schallpegel [dB(A)]":   perf["sound_dBa"],
                    "Teillast [%]":          round(
                        perf["cooling_total_W"] / fc_ref["performance"][v_max_ref]["cooling_total_W"] * 100
                    ),
                })
            df_pl = pd.DataFrame(pl_rows)

            fig_pl = go.Figure()
            fig_pl.add_trace(go.Scatter(
                x=df_pl["Steuersignal [V]"], y=df_pl["Kühlleistung [W]"],
                mode="lines+markers", name="Kühlleistung [W]",
                line=dict(color="#1976d2", width=2), yaxis="y",
            ))
            fig_pl.add_trace(go.Scatter(
                x=df_pl["Steuersignal [V]"], y=df_pl["Schallpegel [dB(A)]"],
                mode="lines+markers", name="Schallpegel [dB(A)]",
                line=dict(color="#f57c00", width=2, dash="dot"), yaxis="y2",
            ))
            fig_pl.update_layout(
                title=f"Teillastkurve {fc_ref['model']}",
                xaxis_title="Steuersignal [V]",
                yaxis=dict(title="Kühlleistung [W]", side="left"),
                yaxis2=dict(title="Schallpegel [dB(A)]", side="right", overlaying="y"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
                height=360,
                margin=dict(l=10, r=10, t=50, b=40),
            )
            st.plotly_chart(fig_pl, use_container_width=True)
        except Exception as e:
            st.warning(f"Teillastkurve nicht verfügbar: {e}")

# ---------------------------------------------------------------------------
# 4. Hydraulic results
# ---------------------------------------------------------------------------
st.markdown('<hr class="section-divider">', unsafe_allow_html=True)
st.markdown("## 4. Hydraulikberechnung")

if not results:
    st.warning("Hydraulikberechnung noch nicht ausgeführt. Bitte Seite 2 aufrufen.")
else:
    pump    = results["pump_check"]
    load    = results["load_check"]
    vol     = results["water_volume"]
    crit_dp = results["critical_path_dp_Pa"] / 1000.0

    col_h1, col_h2, col_h3 = st.columns(3)
    with col_h1:
        st.markdown('<div class="data-card"><h4>Drucknachweis</h4>', unsafe_allow_html=True)
        for k, v in [
            ("Systemdruckverlust (krit. Pfad)", f"{crit_dp:.2f} kPa"),
            ("Verfügbare Pumpendruckhöhe",       f"{pump['pump_head_kPa']:.1f} kPa"),
            ("Reserve",                          f"{pump['margin_kPa']:.2f} kPa"),
            ("Pumpenauslastung",                 f"{100 - pump.get('margin_pct',0):.0f} %"),
            ("Pumpeneignung",                    "Geeignet" if pump["adequate"] else "Unzureichend"),
        ]:
            st.markdown(
                f'<div class="spec-row"><span class="spec-key">{k}</span>'
                f'<span class="spec-val">{v}</span></div>',
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)

    with col_h2:
        st.markdown('<div class="data-card"><h4>Leistungsnachweis</h4>', unsafe_allow_html=True)
        for k, v in [
            ("Gesamtkühllast",          f"{load['total_indoor_kW']:.2f} kW"),
            ("Kältemaschinen-Kapazität", f"{load['chiller_capacity_kW']:.1f} kW"),
            ("Auslastung",              f"{load['utilisation_pct']:.1f} %"),
            ("Reserve",                 f"{load['chiller_capacity_kW'] - load['total_indoor_kW']:.2f} kW"),
            ("Leistungseignung",        "Ausreichend" if load["adequate"] else "Überlastet"),
        ]:
            st.markdown(
                f'<div class="spec-row"><span class="spec-key">{k}</span>'
                f'<span class="spec-val">{v}</span></div>',
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)

    with col_h3:
        st.markdown('<div class="data-card"><h4>Systemvolumen</h4>', unsafe_allow_html=True)
        total_vol = vol["total_volume_L"]
        glycol_pct_v = float(sp.get("glycol_pct", 30))
        exp = size_expansion_vessel(max(total_vol, 20.0), t_sup, glycol_pct=glycol_pct)
        std_sizes = [8, 12, 18, 24, 35, 50, 80, 100]
        exp_std   = next((s for s in std_sizes if s >= exp["vn_L"]), std_sizes[-1])
        for k, v in [
            ("Wasserinhalt gesamt",         f"{total_vol:.1f} L"),
            ("davon Rohrleitungen",          f"{vol.get('pipe_volume_L',0):.1f} L"),
            ("davon Gebläsekonvektoren",     f"{vol.get('fc_volume_L',0):.1f} L"),
            ("davon Verdampfer",             f"{vol.get('chiller_evap_L',0):.1f} L"),
            ("davon Pufferspeicher",         f"{vol.get('buffer_tank_L',0):.1f} L"),
            ("Mindesterfordernis",           f"{vol['min_required_L']:.1f} L"),
            ("Ausreichend",                  "Ja" if vol["adequate"] else "Nein"),
            ("Wasseranteil",                 f"{total_vol * (1-glycol_pct_v/100):.1f} L ({100-glycol_pct_v:.0f}%)"),
            ("Glykolanteil",                 f"{total_vol * glycol_pct_v/100:.1f} L ({glycol_pct_v:.0f}%)"),
            ("Ausdehnungsgefäss (berechn.)", f"{exp['vn_L']:.1f} L"),
            ("Ausdehnungsgefäss (gewählt)",  f"{exp_std} L"),
            ("Vorladedruck",                 f"{exp['p0_bar']:.2f} bar"),
        ]:
            st.markdown(
                f'<div class="spec-row"><span class="spec-key">{k}</span>'
                f'<span class="spec-val">{v}</span></div>',
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# 5. Frostschutznachweis
# ---------------------------------------------------------------------------
st.markdown('<hr class="section-divider">', unsafe_allow_html=True)
st.markdown("## 5. Frostschutznachweis")

frost  = check_frosting(t_sup, glycol_type, glycol_pct)
fp     = frost["freeze_point_C"]
margin = frost["safety_margin_K"]

fr_col1, fr_col2 = st.columns([1, 2])
with fr_col1:
    st.markdown('<div class="data-card"><h4>Frostschutzdaten</h4>', unsafe_allow_html=True)
    for k, v in [
        ("Glykolart",              glycol_type),
        ("Konzentration",          f"{glycol_pct} %"),
        ("Gefrierpunkt",           f"{fp:.1f} °C"),
        ("Vorlauftemperatur",      f"{t_sup:.1f} °C"),
        ("Sicherheitsabstand",     f"{margin:.1f} K"),
        ("Min. Sicherheitsabstand", "3.0 K (Empfehlung)"),
        ("Frostschutz",            "Ausreichend" if frost["safe"] else "Unzureichend"),
    ]:
        st.markdown(
            f'<div class="spec-row"><span class="spec-key">{k}</span>'
            f'<span class="spec-val">{v}</span></div>',
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)

with fr_col2:
    table   = FREEZE_POINTS_EG if "ethylen" in glycol_type.lower() else FREEZE_POINTS_PG
    pcts_fp = sorted(table.keys())
    fps_fp  = [table[p] for p in pcts_fp]

    fig_fp = go.Figure()
    fig_fp.add_trace(go.Scatter(
        x=pcts_fp, y=fps_fp,
        mode="lines+markers",
        name=f"Gefrierpunkt {glycol_type}",
        line=dict(color="#1976d2", width=2),
    ))
    fig_fp.add_hline(y=t_sup, line_dash="dash", line_color="#d32f2f",
                     annotation_text=f"VL-Temperatur {t_sup}°C")
    fig_fp.add_vline(x=glycol_pct, line_dash="dot", line_color="#f57c00",
                     annotation_text=f"Konzentration {glycol_pct}%")
    fig_fp.add_scatter(
        x=[glycol_pct], y=[fp], mode="markers",
        marker=dict(size=12, color="#1976d2"),
        name=f"Aktuell: {fp:.1f}°C",
    )
    fig_fp.update_layout(
        title="Gefrierpunktkurve",
        xaxis_title="Glykolkonzentration [%]",
        yaxis_title="Gefrierpunkt [°C]",
        height=320,
        margin=dict(l=10, r=10, t=50, b=40),
    )
    st.plotly_chart(fig_fp, use_container_width=True)

# ---------------------------------------------------------------------------
# 6. Lärmbewertung
# ---------------------------------------------------------------------------
st.markdown('<hr class="section-divider">', unsafe_allow_html=True)
st.markdown("## 6. Lärmbewertung")

if chiller_data:
    lw = chiller_data.get("sound_power_dBa", 78)

    noise_col1, noise_col2 = st.columns([1, 2])

    with noise_col1:
        st.markdown('<div class="data-card"><h4>Aussengerät Schallleistung</h4>', unsafe_allow_html=True)
        for k, v in [
            ("Schallleistungspegel Lw", f"{lw} dB(A)"),
            ("Frequenz",                "Breitband"),
            ("Messnorm",                "EN ISO 3744"),
        ]:
            st.markdown(
                f'<div class="spec-row"><span class="spec-key">{k}</span>'
                f'<span class="spec-val">{v}</span></div>',
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("**Schalldruckpegel in Abstand:**")
        noise_dist_data = []
        for d in [3, 5, 7, 10, 15, 20, 30]:
            lp = sound_pressure_at_distance(lw, d, directivity_Q=2.0)
            noise_dist_data.append({
                "Abstand [m]": d,
                "Lp [dB(A)]":  lp,
                "≤ 45 dB(A)":  "✅" if lp <= 45 else "⚠️",
            })
        st.dataframe(pd.DataFrame(noise_dist_data), hide_index=True, use_container_width=True)

    with noise_col2:
        distances_plot = np.linspace(1, 50, 100)
        lps = [sound_pressure_at_distance(lw, d, directivity_Q=2.0) for d in distances_plot]

        fig_noise = go.Figure()
        fig_noise.add_trace(go.Scatter(
            x=distances_plot, y=lps, mode="lines",
            name="Schalldruckpegel", line=dict(color="#1976d2", width=2),
        ))
        fig_noise.add_hline(y=45, line_dash="dash", line_color="#f57c00",
                            annotation_text="45 dB(A) — typischer Grenzwert Nacht")
        fig_noise.add_hline(y=55, line_dash="dot", line_color="#d32f2f",
                            annotation_text="55 dB(A) — typischer Grenzwert Tag")
        fig_noise.update_layout(
            title="Schalldruckpegel in Abhängigkeit vom Abstand",
            xaxis_title="Abstand [m]",
            yaxis_title="Schalldruckpegel [dB(A)]",
            height=340,
            margin=dict(l=10, r=10, t=50, b=40),
        )
        st.plotly_chart(fig_noise, use_container_width=True)

# ---------------------------------------------------------------------------
# 7. Kältemitteldaten
# ---------------------------------------------------------------------------
st.markdown('<hr class="section-divider">', unsafe_allow_html=True)
st.markdown("## 7. Kältemitteldaten (F-Gas)")

if chiller_data:
    ref           = chiller_data.get("refrigerant", "R32")
    gwp           = chiller_data.get("gwp", 675)
    charge        = chiller_data.get("refrigerant_charge_kg", 4.5)
    n_units       = len(chiller_nodes)
    total_charge  = (charge or 0) * n_units
    co2_eq_t      = total_charge * (gwp or 0) / 1000.0

    rr_col1, rr_col2 = st.columns(2)
    with rr_col1:
        st.markdown('<div class="data-card"><h4>Kältemittelinformation</h4>', unsafe_allow_html=True)
        for k, v in [
            ("Kältemittel",                ref),
            ("GWP (100 Jahre)",            str(gwp)),
            ("Kältemittelfüllmenge/Gerät", f"ca. {charge} kg"),
            ("Anzahl Geräte",              str(n_units)),
            ("Gesamtfüllmenge",            f"ca. {total_charge:.1f} kg"),
            ("CO₂-Äquivalent gesamt",      f"{co2_eq_t:.2f} t CO₂-eq"),
            ("F-Gas Meldepflicht",
             "Ja (> 5 kg GWP > 150)" if total_charge > 5 and (gwp or 0) > 150 else "Prüfen"),
        ]:
            st.markdown(
                f'<div class="spec-row"><span class="spec-key">{k}</span>'
                f'<span class="spec-val">{v}</span></div>',
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)

    with rr_col2:
        refrigerants = {
            "R32": 675, "R410A": 2088, "R134a": 1430,
            "R407C": 1774, "R290 (Propan)": 3, "R1234yf": 4,
        }
        highlight  = [str(ref) in k for k in refrigerants.keys()]
        colors_gwp = ["#1976d2" if h else "#90caf9" for h in highlight]

        fig_gwp = go.Figure(go.Bar(
            x=list(refrigerants.keys()),
            y=list(refrigerants.values()),
            marker_color=colors_gwp,
            text=list(refrigerants.values()),
            textposition="outside",
        ))
        fig_gwp.add_hline(y=750, line_dash="dash", line_color="#f57c00",
                          annotation_text="F-Gas Grenze 2025: GWP 750")
        fig_gwp.update_layout(
            title="GWP-Vergleich gängiger Kältemittel",
            yaxis_title="GWP (100 Jahre)",
            height=340,
            margin=dict(l=10, r=10, t=50, b=40),
            showlegend=False,
        )
        st.plotly_chart(fig_gwp, use_container_width=True)

# ---------------------------------------------------------------------------
# 8. Fluid properties
# ---------------------------------------------------------------------------
st.markdown('<hr class="section-divider">', unsafe_allow_html=True)
st.markdown("## 8. Flüssigkeitseigenschaften")

props = get_fluid_properties(glycol_pct)

fp_col1, fp_col2 = st.columns([1, 2])
with fp_col1:
    st.markdown('<div class="data-card"><h4>Wärmeträger</h4>', unsafe_allow_html=True)
    for k, v in [
        ("Flüssigkeit",        f"{glycol_type} {glycol_pct}%"),
        ("Dichte",             f"{props['density_kg_m3']:.1f} kg/m³"),
        ("Viskosität (dyn.)",  f"{props['viscosity_Pa_s']*1000:.3f} mPa·s"),
        ("Wärmekapazität",     f"{props['cp_J_kgK']:.0f} J/(kg·K)"),
        ("Rohrrauigkeit",      f"{props['roughness_mm']:.3f} mm"),
        ("VL-Temperatur",      f"{props['t_supply_C']:.1f} °C"),
        ("RL-Temperatur",      f"{props['t_return_C']:.1f} °C"),
        ("Gefrierpunkt",       f"{get_freeze_point_C(glycol_type, glycol_pct):.1f} °C"),
    ]:
        st.markdown(
            f'<div class="spec-row"><span class="spec-key">{k}</span>'
            f'<span class="spec-val">{v}</span></div>',
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)

with fp_col2:
    st.markdown("**Geberit FlowFit — Rohrquerschnitte (DN20–DN75)**")
    pipe_rows_spec = []
    for dn, spec in FLOWFIT_PIPE_SPECS.items():
        di   = spec["di_mm"] / 1000.0
        area = np.pi * (spec["di_mm"] / 2) ** 2 / 100.0
        vol_pm = np.pi * (di / 2) ** 2 * 1000.0
        pipe_rows_spec.append({
            "DN":                    dn,
            "da [mm]":               spec["da_mm"],
            "di [mm]":               spec["di_mm"],
            "s [mm]":                spec["s_mm"],
            "Artikelnummer":         spec.get("article", "—"),
            "Querschnitt [cm²]":     round(area, 3),
            "Wasserinhalt [L/m]":    round(vol_pm, 4),
        })
    st.dataframe(pd.DataFrame(pipe_rows_spec), use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# 9. Print button
# ---------------------------------------------------------------------------
st.markdown('<hr class="section-divider">', unsafe_allow_html=True)
st.markdown('<div class="no-print">', unsafe_allow_html=True)
c_print1, c_print2 = st.columns(2)
with c_print1:
    st.button(
        "Drucken (Browser-Druckdialog)",
        help="Ctrl+P für Druckdialog. Sidebar wird beim Drucken ausgeblendet.",
        use_container_width=True,
    )
    st.caption("Tipp: Browser → Drucken → Als PDF speichern für druckfertige Ausgabe")

with c_print2:
    st.info(
        "Dieser Bericht enthält alle Systemdaten und ist für die technische Dokumentation geeignet. "
        "Für den Ausdruck wird das Browser-Druckmenü empfohlen (Ctrl+P)."
    )
st.markdown("</div>", unsafe_allow_html=True)

st.markdown("---")
st.caption(
    f"Kaltwasser Designer | Technischer Bericht erstellt am {now.strftime('%d.%m.%Y %H:%M')} | "
    f"Projekt: {project_name} | Ingenieur: {engineer} | "
    f"Imwinkelried Lüftung + Klima AG — www.imwinkelried.ch"
)
