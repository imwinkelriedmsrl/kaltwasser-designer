"""
Hydraulikberechnung — Seite 2
Durchflüsse, Druckverluste, Rohrdimensionierung, Kritischer Pfad,
Geschwindigkeitswarnungen, Systemwasserinhalt (Wasser/Glykol-Aufteilung).
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

from utils.helpers import init_session_state, check_frosting
from calculations.hydraulics import NetworkCalculator
from data.geberit_flowfit import FLOWFIT_PIPE_SPECS, get_fluid_properties

# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Hydraulikberechnung | Kaltwasser Designer",
    layout="wide",
    page_icon="📊",
)
init_session_state(st)

st.markdown("""
<style>
.result-card {
    background: #f0f4f8; border: 1px solid #c8d6e8; border-radius: 8px;
    padding: 16px; margin-bottom: 12px;
}
.ok-badge  { color: #155724; background: #d4edda; padding: 3px 8px; border-radius: 4px; font-weight: 600; }
.err-badge { color: #721c24; background: #f8d7da; padding: 3px 8px; border-radius: 4px; font-weight: 600; }
.warn-box  {
    background: #fff3cd; border: 1px solid #ffc107; border-radius: 6px;
    padding: 10px 14px; margin: 6px 0; color: #856404;
}
</style>
""", unsafe_allow_html=True)

st.markdown("# 📊 Hydraulikberechnung")
st.markdown("Automatische Rohrdimensionierung, Druckverlustberechnung und Pumpeneignungsprüfung.")

DN_COLORS = {
    20: "#bbdefb", 25: "#90caf9", 32: "#64b5f6",
    40: "#42a5f5", 50: "#2196f3", 63: "#1976d2", 75: "#0d47a1",
}


def dn_badge(dn: int) -> str:
    color = DN_COLORS.get(dn, "#888")
    return f'<span style="background:{color};color:white;padding:2px 7px;border-radius:3px;font-weight:700">DN{dn}</span>'


# ---------------------------------------------------------------------------
nodes  = st.session_state.nodes
edges  = st.session_state.edges
sp     = st.session_state.system_params

if not nodes or not edges:
    st.warning("Das Netzwerk ist leer. Bitte zuerst im Netzwerk-Editor Knoten und Verbindungen anlegen.")
    st.page_link("pages/1_🔧_Network_Editor.py", label="Zum Netzwerk-Editor", icon="🔧")
    st.stop()

col_btn, col_params = st.columns([1, 2])
with col_btn:
    run_calc = st.button("Berechnung ausführen", type="primary", use_container_width=True)
with col_params:
    glycol_pct = int(sp.get("glycol_pct", 30))
    t_sup = sp.get("t_supply_C", 7.0)
    t_ret = sp.get("t_return_C", 12.0)
    v_main   = sp.get("v_max_main_ms", 1.5)
    v_branch = sp.get("v_max_branch_ms", 0.7)
    st.info(
        f"System: VL {t_sup}°C / RL {t_ret}°C — "
        f"{sp.get('glycol_type','Ethylenglykol')} {glycol_pct}% — "
        f"v_max Stamm: {v_main} m/s, Abzweig: {v_branch} m/s — "
        f"Netzwerk: {len(nodes)} Knoten, {len(edges)} Segmente"
    )

if run_calc:
    with st.spinner("Berechnung läuft…"):
        try:
            calc = NetworkCalculator(nodes, edges, sp)
            results = calc.run()
            # Write back sized DN to edge props
            for edge in st.session_state.edges:
                eid = edge["id"]
                dn = results["pipe_sizes"].get(eid)
                dp = results["dp_results"].get(eid, {}).get("dp_total_Pa")
                fl = results["edge_flows"].get(eid)
                if "props" not in edge:
                    edge["props"] = {}
                edge["props"]["dn_sized"] = dn
                edge["props"]["dp_Pa"] = dp
                edge["props"]["flow_lh"] = round(fl / 1000.0 * (1000.0 / 5.0), 1) if fl else None
            st.session_state.calc_results = results
            st.success("Berechnung abgeschlossen.")
        except Exception as e:
            st.error(f"Berechnungsfehler: {e}")
            import traceback
            st.code(traceback.format_exc())

results = st.session_state.calc_results

if not results:
    st.info("Bitte Berechnung ausführen.")
    st.stop()

# ---------------------------------------------------------------------------
# Velocity warnings — show per segment with red box
# ---------------------------------------------------------------------------
vel_warns = results.get("velocity_warnings", [])
if vel_warns:
    st.markdown("---")
    st.markdown("## ⚠️ Geschwindigkeitswarnungen")
    st.error(f"{len(vel_warns)} Segment(e) überschreiten den zulässigen Geschwindigkeitsgrenzwert!")
    for w in vel_warns:
        st.markdown(
            f'<div class="warn-box">'
            f'<strong>Segment {w["from"]} → {w["to"]}</strong> (DN{w["nominal_dn"]}): '
            f'v = {w["velocity_ms"]:.3f} m/s &gt; Grenzwert {w["v_limit_ms"]:.1f} m/s — '
            f'Bitte Rohrdurchmesser vergrössern oder Grenzwert anpassen.'
            f'</div>',
            unsafe_allow_html=True,
        )

# ---------------------------------------------------------------------------
# Overview metrics
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("## Systemübersicht")

pump    = results["pump_check"]
load    = results["load_check"]
vol     = results["water_volume"]
crit_dp = results["critical_path_dp_Pa"] / 1000.0

m1, m2, m3, m4, m5, m6 = st.columns(6)
m1.metric("Kälteleistung gesamt",      f"{load['total_indoor_kW']:.1f} kW",
          delta=f"{load['chiller_capacity_kW'] - load['total_indoor_kW']:.1f} kW Reserve")
m2.metric("Kältemaschinen-Kapaz.",     f"{load['chiller_capacity_kW']:.1f} kW",
          delta=f"{load['utilisation_pct']:.0f}% Auslastung")
m3.metric("Kritischer Druckverlust",   f"{crit_dp:.1f} kPa")
m4.metric("Verfüg. Pumpendruckhöhe",   f"{pump['pump_head_kPa']:.1f} kPa",
          delta=f"{pump['margin_kPa']:.1f} kPa Marge")
m5.metric("Systemwasserinhalt",        f"{vol['total_volume_L']:.1f} L",
          delta=f"Min. {vol['min_required_L']:.1f} L")
m6.metric("Rohrsegmente",              len(results["segment_summary"]))

# System checks
st.markdown("### Systemprüfungen")
c1, c2, c3, c4 = st.columns(4)

with c1:
    if load["adequate"]:
        st.markdown('<span class="ok-badge">✓ Kälteleistung ausreichend</span>', unsafe_allow_html=True)
        st.caption(f"{load['total_indoor_kW']:.1f} kW ≤ {load['chiller_capacity_kW']:.1f} kW")
    else:
        st.markdown('<span class="err-badge">✗ Kälteleistung überschritten</span>', unsafe_allow_html=True)
        st.caption(f"{load['total_indoor_kW']:.1f} kW > {load['chiller_capacity_kW']:.1f} kW")

with c2:
    if pump["adequate"]:
        st.markdown('<span class="ok-badge">✓ Pumpe ausreichend</span>', unsafe_allow_html=True)
        st.caption(f"{pump['pump_head_kPa']:.1f} kPa ≥ {pump['system_dp_kPa']:.1f} kPa")
    else:
        st.markdown('<span class="err-badge">✗ Pumpe unzureichend</span>', unsafe_allow_html=True)
        st.caption(f"{pump['pump_head_kPa']:.1f} kPa < {pump['system_dp_kPa']:.1f} kPa")

with c3:
    if vol["adequate"]:
        st.markdown('<span class="ok-badge">✓ Wasserinhalt ausreichend</span>', unsafe_allow_html=True)
        st.caption(f"{vol['total_volume_L']:.1f} L ≥ {vol['min_required_L']:.1f} L")
    else:
        st.markdown('<span class="err-badge">✗ Wasserinhalt zu gering</span>', unsafe_allow_html=True)
        st.caption(f"{vol['total_volume_L']:.1f} L < {vol['min_required_L']:.1f} L")

with c4:
    frost = check_frosting(t_sup, sp.get("glycol_type", "Ethylenglykol"), glycol_pct)
    if frost["safe"]:
        st.markdown('<span class="ok-badge">✓ Frostschutz ausreichend</span>', unsafe_allow_html=True)
        st.caption(f"Gefrierpunkt {frost['freeze_point_C']:.1f}°C, +{frost['safety_margin_K']:.1f} K")
    else:
        st.markdown('<span class="err-badge">✗ Frostschutz unzureichend</span>', unsafe_allow_html=True)
        st.caption(f"Gefrierpunkt {frost['freeze_point_C']:.1f}°C bei VL {t_sup}°C!")

# ---------------------------------------------------------------------------
# Segment results table
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("## Rohrsegment-Ergebnisse")

seg_data = results["segment_summary"]
df_seg   = pd.DataFrame(seg_data)

display_cols = {
    "edge_id":           "Segment-ID",
    "from":              "Von",
    "to":                "Nach",
    "flow_kW":           "Last [kW]",
    "nominal_dn":        "Rohr DN",
    "length_m":          "Länge [m]",
    "velocity_m_s":      "Geschw. [m/s]",
    "v_limit_ms":        "Grenzwert [m/s]",
    "velocity_exceeded": "v überschritten",
    "dp_pipe_Pa":        "ΔP Rohr [Pa]",
    "dp_fittings_Pa":    "ΔP Formteile [Pa]",
    "dp_total_kPa":      "ΔP gesamt [kPa]",
    "on_critical_path":  "Krit. Pfad",
}

df_display = df_seg[[c for c in display_cols if c in df_seg.columns]].copy()
df_display.rename(columns=display_cols, inplace=True)

for col, fmt in [
    ("Last [kW]",          "{:.2f}"),
    ("Länge [m]",          "{:.1f}"),
    ("Geschw. [m/s]",      "{:.3f}"),
    ("Grenzwert [m/s]",    "{:.1f}"),
    ("ΔP Rohr [Pa]",       "{:.1f}"),
    ("ΔP Formteile [Pa]",  "{:.1f}"),
    ("ΔP gesamt [kPa]",    "{:.3f}"),
]:
    if col in df_display.columns:
        df_display[col] = df_display[col].map(fmt.format)

st.dataframe(df_display, use_container_width=True, hide_index=True)

crit_edges = results.get("critical_path", [])
if crit_edges:
    st.info(f"Kritischer Pfad: {len(crit_edges)} Segmente — Gesamtdruckverlust: {crit_dp:.2f} kPa")

# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("## Visualisierungen")

chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    st.markdown("### Druckverluste pro Segment [kPa]")
    if seg_data:
        labels  = [f"{s['from'][:8]}→{s['to'][:8]}" for s in seg_data]
        dp_pipe = [s["dp_pipe_Pa"] / 1000.0 for s in seg_data]
        dp_fit  = [s["dp_fittings_Pa"] / 1000.0 for s in seg_data]

        fig_dp = go.Figure()
        fig_dp.add_bar(x=labels, y=dp_pipe, name="Rohrreibung", marker_color="#1976d2")
        fig_dp.add_bar(x=labels, y=dp_fit,  name="Formteile",   marker_color="#f57c00")
        fig_dp.update_layout(
            barmode="stack",
            xaxis_tickangle=-45,
            yaxis_title="Druckverlust [kPa]",
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            height=380,
            margin=dict(l=10, r=10, t=10, b=80),
        )
        st.plotly_chart(fig_dp, use_container_width=True)

with chart_col2:
    st.markdown("### Rohrdurchmesser-Verteilung")
    if seg_data:
        dn_counts  = {}
        dn_lengths = {}
        for s in seg_data:
            dn = s["nominal_dn"]
            l  = float(str(s.get("length_m", 0)).replace(",", "."))
            dn_counts[f"DN{dn}"]  = dn_counts.get(f"DN{dn}", 0) + 1
            dn_lengths[f"DN{dn}"] = dn_lengths.get(f"DN{dn}", 0.0) + l

        labels_dn = list(dn_counts.keys())
        lengths   = [dn_lengths[k] for k in labels_dn]
        counts    = [dn_counts[k]  for k in labels_dn]

        fig_dn = go.Figure()
        fig_dn.add_bar(
            x=labels_dn, y=lengths,
            marker_color=["#90caf9" if "20" in k else "#1976d2" for k in labels_dn],
            text=[f"{l:.1f}m ({c}×)" for l, c in zip(lengths, counts)],
            textposition="outside",
        )
        fig_dn.update_layout(
            yaxis_title="Gesamtlänge [m]",
            height=380,
            margin=dict(l=10, r=10, t=10, b=40),
            showlegend=False,
        )
        st.plotly_chart(fig_dn, use_container_width=True)

st.markdown("### Fliessgeschwindigkeiten pro Segment [m/s]")
if seg_data:
    labels_v   = [f"{s['from'][:10]}→{s['to'][:10]}" for s in seg_data]
    velocities = [s["velocity_m_s"] for s in seg_data]
    colors_v   = []
    for s in seg_data:
        v = s["velocity_m_s"]
        v_lim = s.get("v_limit_ms", v_main)
        if v > v_lim:
            colors_v.append("#d32f2f")  # exceeded — red
        elif v > v_lim * 0.85:
            colors_v.append("#f57c00")  # near limit — orange
        else:
            colors_v.append("#388e3c")  # ok — green

    fig_v = go.Figure()
    fig_v.add_bar(x=labels_v, y=velocities, marker_color=colors_v)
    fig_v.add_hline(y=v_main, line_dash="dash", line_color="#d32f2f",
                    annotation_text=f"Max. Hauptleitung {v_main} m/s", annotation_position="top right")
    fig_v.add_hline(y=v_branch, line_dash="dash", line_color="#f57c00",
                    annotation_text=f"Max. Stichleitung {v_branch} m/s", annotation_position="top right")
    fig_v.update_layout(
        xaxis_tickangle=-45,
        yaxis_title="Geschwindigkeit [m/s]",
        height=360,
        margin=dict(l=10, r=10, t=10, b=80),
        showlegend=False,
    )
    st.plotly_chart(fig_v, use_container_width=True)

# ---------------------------------------------------------------------------
# Systemwasserinhalt — water/glycol breakdown
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("## Systemwasserinhalt")
st.markdown("Aufschlüsselung des Gesamtvolumens nach Komponenten und Wasser/Glykol-Anteil.")

total_vol_L  = vol["total_volume_L"]
pipe_vol_L   = vol.get("pipe_volume_L", total_vol_L)
fc_vol_L     = vol.get("fc_volume_L", 0.0)
evap_vol_L   = vol.get("chiller_evap_L", 0.0)
buffer_vol_L = vol.get("buffer_tank_L", 0.0)

glycol_pct_val = float(sp.get("glycol_pct", 30))
water_vol_L  = total_vol_L * (1 - glycol_pct_val / 100.0)
glycol_vol_L = total_vol_L * (glycol_pct_val / 100.0)

# Volume breakdown table
vol_table = []
if pipe_vol_L > 0:
    vol_table.append({"Komponente": "Rohrleitungen", "Volumen [L]": round(pipe_vol_L, 2), "Anteil [%]": round(pipe_vol_L / total_vol_L * 100, 1) if total_vol_L > 0 else 0})
if fc_vol_L > 0:
    vol_table.append({"Komponente": "Gebläsekonvektoren", "Volumen [L]": round(fc_vol_L, 2), "Anteil [%]": round(fc_vol_L / total_vol_L * 100, 1) if total_vol_L > 0 else 0})
if evap_vol_L > 0:
    vol_table.append({"Komponente": "Verdampfer Kältemaschine", "Volumen [L]": round(evap_vol_L, 2), "Anteil [%]": round(evap_vol_L / total_vol_L * 100, 1) if total_vol_L > 0 else 0})
if buffer_vol_L > 0:
    vol_table.append({"Komponente": "Pufferspeicher", "Volumen [L]": round(buffer_vol_L, 2), "Anteil [%]": round(buffer_vol_L / total_vol_L * 100, 1) if total_vol_L > 0 else 0})
vol_table.append({"Komponente": "Gesamtvolumen", "Volumen [L]": round(total_vol_L, 2), "Anteil [%]": 100.0})

vol_col1, vol_col2, vol_col3 = st.columns(3)

with vol_col1:
    st.metric("Gesamtvolumen",          f"{total_vol_L:.1f} L (100%)")
    st.metric(f"Wasseranteil ({100-glycol_pct_val:.0f}%)",  f"{water_vol_L:.1f} L")
    st.metric(f"Glykolanteil ({glycol_pct_val:.0f}%)",     f"{glycol_vol_L:.1f} L")
    st.markdown("---")
    st.dataframe(pd.DataFrame(vol_table), use_container_width=True, hide_index=True)

with vol_col2:
    # Pie chart — component breakdown
    if vol_table and total_vol_L > 0:
        labels_pie  = [r["Komponente"] for r in vol_table if r["Komponente"] != "Gesamtvolumen"]
        values_pie  = [r["Volumen [L]"] for r in vol_table if r["Komponente"] != "Gesamtvolumen"]
        if labels_pie:
            fig_pie = go.Figure(go.Pie(
                labels=labels_pie,
                values=values_pie,
                hole=0.35,
                marker_colors=["#1976d2", "#2e7d32", "#f57c00", "#7b1fa2"],
            ))
            fig_pie.update_layout(
                title="Volumenaufteilung nach Komponenten",
                height=320,
                margin=dict(l=10, r=10, t=50, b=10),
                showlegend=True,
                legend=dict(orientation="v"),
            )
            st.plotly_chart(fig_pie, use_container_width=True)

with vol_col3:
    # Pie chart — water vs glycol
    if total_vol_L > 0 and glycol_pct_val > 0:
        fig_wg = go.Figure(go.Pie(
            labels=[f"Wasser ({100-glycol_pct_val:.0f}%)", f"Glykol ({glycol_pct_val:.0f}%)"],
            values=[round(water_vol_L, 2), round(glycol_vol_L, 2)],
            hole=0.35,
            marker_colors=["#42a5f5", "#26a69a"],
        ))
        fig_wg.update_layout(
            title=f"Wasser/Glykol-Aufteilung ({sp.get('glycol_type','EG')} {glycol_pct_val:.0f}%)",
            height=320,
            margin=dict(l=10, r=10, t=50, b=10),
        )
        st.plotly_chart(fig_wg, use_container_width=True)

# Per-DN water volume breakdown
if vol.get("volume_by_dn"):
    st.markdown("**Wasserinhalt nach Rohrdurchmesser (Leitungen)**")
    dn_vol_rows = []
    for dn in sorted(vol["volume_by_dn"].keys()):
        v_dn = vol["volume_by_dn"][dn]
        dn_vol_rows.append({
            "Rohr DN": f"DN{dn}",
            "Wasserinhalt [L]": round(v_dn, 3),
            "Anteil [%]": round(v_dn / pipe_vol_L * 100, 1) if pipe_vol_L > 0 else 0,
        })
    st.dataframe(pd.DataFrame(dn_vol_rows), use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Fluid properties
# ---------------------------------------------------------------------------
st.markdown("---")
with st.expander("Flüssigkeitseigenschaften", expanded=False):
    props = get_fluid_properties(glycol_pct)
    col_p1, col_p2, col_p3, col_p4 = st.columns(4)
    col_p1.metric("Dichte",         f"{props['density_kg_m3']:.1f} kg/m³")
    col_p2.metric("Viskosität",     f"{props['viscosity_Pa_s']*1000:.3f} mPa·s")
    col_p3.metric("Wärmekapazität", f"{props['cp_J_kgK']:.0f} J/(kg·K)")
    col_p4.metric("Rauigkeit",      f"{props['roughness_mm']:.3f} mm")
    st.caption(
        f"Glykollösung: {sp.get('glycol_type','Ethylenglykol')} {glycol_pct}% — "
        f"VL {props['t_supply_C']}°C / RL {props['t_return_C']}°C"
    )

# ---------------------------------------------------------------------------
# Pump adequacy detail
# ---------------------------------------------------------------------------
st.markdown("---")
with st.expander("Pumpeneignung — Detail", expanded=True):
    c1, c2, c3 = st.columns(3)
    c1.metric("Verfügbare Pumpendruckhöhe",       f"{pump['pump_head_kPa']:.1f} kPa")
    c2.metric("Systemdruckverlust (krit. Pfad)",  f"{pump['system_dp_kPa']:.1f} kPa",
              delta=f"Marge: {pump['margin_kPa']:.1f} kPa",
              delta_color="normal" if pump["adequate"] else "inverse")
    c3.metric("Pumpenauslastung",                 f"{100 - pump.get('margin_pct', 0):.0f} %")

    if pump["adequate"]:
        st.success(
            f"Pumpe ist ausreichend dimensioniert. "
            f"Marge: {pump['margin_kPa']:.1f} kPa ({pump.get('margin_pct',0):.0f}% der Pumpendruckhöhe)"
        )
    else:
        st.error(
            f"Pumpendruckhöhe {pump['pump_head_kPa']:.1f} kPa ist kleiner als "
            f"Systemdruckverlust {pump['system_dp_kPa']:.1f} kPa! "
            f"Pumpendaten prüfen oder Netz optimieren."
        )

    if crit_edges and seg_data:
        st.markdown("**Druckverlust-Wasserfall (kritischer Pfad)**")
        crit_segs  = [s for s in seg_data if s["edge_id"] in crit_edges]
        wf_labels  = [f"{s['from'][:8]}→{s['to'][:8]}" for s in crit_segs]
        wf_dp      = [s["dp_total_kPa"] for s in crit_segs]

        from data.component_library import get_fan_coil_dp_kPa
        fc_nodes = [n for n in nodes if n.get("type") == "FAN_COIL"]
        if fc_nodes:
            fc_node  = fc_nodes[0]
            fc_props = fc_node.get("props", {})
            fc_model = fc_props.get("model", fc_node.get("model", "Kampmann_KaCool_W_Size4"))
            try:
                if fc_model == "custom":
                    fc_dp = float(fc_props.get("dp_kPa", 0.0))
                else:
                    fc_dp = get_fan_coil_dp_kPa(fc_model)
            except Exception:
                fc_dp = 0.0
            wf_labels.append("Gebläsekonvektor")
            wf_dp.append(fc_dp)

        fig_wf = go.Figure(go.Waterfall(
            name="Druckverlust",
            orientation="v",
            x=wf_labels,
            y=wf_dp,
            connector=dict(line=dict(color="#888")),
            increasing=dict(marker_color="#1976d2"),
            totals=dict(marker_color="#1a237e"),
        ))
        fig_wf.add_hline(
            y=pump["pump_head_kPa"],
            line_dash="dash", line_color="#2e7d32",
            annotation_text=f"Pumpendruckhöhe {pump['pump_head_kPa']:.1f} kPa",
        )
        fig_wf.update_layout(
            yaxis_title="Druckverlust [kPa]",
            height=360,
            margin=dict(l=10, r=10, t=10, b=80),
            xaxis_tickangle=-45,
        )
        st.plotly_chart(fig_wf, use_container_width=True)

st.markdown("---")
st.page_link("pages/3_📋_Material_List.py", label="Weiter zur Materialliste", icon="📋")
