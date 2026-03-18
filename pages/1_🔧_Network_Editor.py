"""
Netzwerk-Editor — Seite 1
Graphisches Zeichnen des Kaltwasser-Rohrnetzes.
"""

import streamlit as st
import plotly.graph_objects as go
import json
import math
from typing import Dict, List, Any, Optional

from utils.helpers import init_session_state, make_node_id, make_edge_id, network_to_json, network_from_json
from data.component_library import NODE_TYPES, CHILLERS, FAN_COILS, get_chiller, get_fan_coil

# ---------------------------------------------------------------------------
st.set_page_config(page_title="Netzwerk-Editor | Kaltwasser Designer", layout="wide", page_icon="🔧")
init_session_state(st)

# Custom CSS
st.markdown("""
<style>
.node-panel { background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 8px; padding: 12px; margin-bottom: 8px; }
.edge-panel { background: #fff8e1; border: 1px solid #ffe082; border-radius: 8px; padding: 12px; margin-bottom: 8px; }
.section-header { font-size: 1rem; font-weight: 700; color: #1565C0; border-bottom: 2px solid #1565C0; padding-bottom: 4px; margin-bottom: 12px; }
</style>
""", unsafe_allow_html=True)

st.markdown("# 🔧 Netzwerk-Editor")
st.markdown("Kaltwasser-Rohrnetz zeichnen: Geräte hinzufügen und mit Rohrsegmenten verbinden.")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NODE_COLORS = {
    "CHILLER":               "#1565C0",
    "FAN_COIL":              "#2E7D32",
    "T_JUNCTION":            "#F57F17",
    "PUMP":                  "#6A1B9A",
    "DISTRIBUTION_MANIFOLD": "#AD1457",
    "AIR_VENT":              "#00838F",
    "FILL_DRAIN":            "#558B2F",
}

NODE_SYMBOLS = {
    "CHILLER":               "square",
    "FAN_COIL":              "circle",
    "T_JUNCTION":            "diamond",
    "PUMP":                  "triangle-up",
    "DISTRIBUTION_MANIFOLD": "star",
    "AIR_VENT":              "x",
    "FILL_DRAIN":            "cross",
}


def get_node_label(node: Dict) -> str:
    label = node.get("label", node["id"])
    ntype = node.get("type", "")
    if ntype == "FAN_COIL":
        room = node.get("room", "")
        v = node.get("voltage", 10)
        label = f"{label}<br>({room}) {v}V"
    return label


def build_plotly_figure(nodes: List[Dict], edges: List[Dict]) -> go.Figure:
    """Build an interactive Plotly network figure."""
    fig = go.Figure()

    if not nodes:
        fig.add_annotation(
            text="Noch keine Knoten vorhanden.<br>Geräte links hinzufügen →",
            xref="paper", yref="paper", x=0.5, y=0.5,
            showarrow=False, font=dict(size=16, color="#888"),
        )
        fig.update_layout(
            xaxis=dict(visible=False), yaxis=dict(visible=False),
            plot_bgcolor="#f9fafb", paper_bgcolor="#f9fafb",
            height=500,
        )
        return fig

    node_map = {n["id"]: n for n in nodes}

    # Draw edges first
    for edge in edges:
        src = node_map.get(edge["source"])
        tgt = node_map.get(edge["target"])
        if not src or not tgt:
            continue
        x0, y0 = src.get("x", 0), src.get("y", 0)
        x1, y1 = tgt.get("x", 0), tgt.get("y", 0)
        length_m = edge.get("length_m", 0.0)

        # Edge line
        fig.add_trace(go.Scatter(
            x=[x0, x1, None], y=[y0, y1, None],
            mode="lines",
            line=dict(width=3, color="#5c8dc8"),
            hoverinfo="skip",
            showlegend=False,
        ))
        # Edge label (midpoint)
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        edge_id_short = edge.get("id", "")[:6]
        fig.add_trace(go.Scatter(
            x=[mx], y=[my],
            mode="text",
            text=[f"  {length_m:.1f}m"],
            textfont=dict(size=11, color="#1565C0"),
            hovertemplate=(
                f"<b>Segment {edge_id_short}</b><br>"
                f"Länge: {length_m:.2f} m<br>"
                f"Von: {edge.get('source','')}<br>"
                f"Nach: {edge.get('target','')}<extra></extra>"
            ),
            showlegend=False,
        ))

    # Draw nodes (grouped by type for legend)
    for ntype, type_info in NODE_TYPES.items():
        type_nodes = [n for n in nodes if n.get("type") == ntype]
        if not type_nodes:
            continue

        xs = [n.get("x", 0) for n in type_nodes]
        ys = [n.get("y", 0) for n in type_nodes]
        labels = [n.get("label", n["id"]) for n in type_nodes]
        hover_texts = []
        for n in type_nodes:
            ht = f"<b>{n.get('label', n['id'])}</b><br>Typ: {type_info['label']}"
            if ntype == "FAN_COIL":
                ht += f"<br>Raum: {n.get('room','—')}<br>Spannung: {n.get('voltage',10)}V"
            elif ntype == "CHILLER":
                ht += f"<br>Modell: {n.get('model','—')}"
            ht += "<extra></extra>"
            hover_texts.append(ht)

        fig.add_trace(go.Scatter(
            x=xs, y=ys,
            mode="markers+text",
            marker=dict(
                size=22,
                color=NODE_COLORS.get(ntype, "#888"),
                symbol=NODE_SYMBOLS.get(ntype, "circle"),
                line=dict(width=2, color="white"),
            ),
            text=labels,
            textposition="top center",
            textfont=dict(size=10),
            hovertemplate=hover_texts,
            name=type_info["label"],
        ))

    fig.update_layout(
        showlegend=True,
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
            bgcolor="rgba(255,255,255,0.8)", bordercolor="#ddd", borderwidth=1,
        ),
        plot_bgcolor="#f0f4f8",
        paper_bgcolor="#ffffff",
        xaxis=dict(
            title="X [m]",
            showgrid=True, gridcolor="#dde",
            zeroline=True, zerolinecolor="#aab",
        ),
        yaxis=dict(
            title="Y [m]",
            showgrid=True, gridcolor="#dde",
            zeroline=True, zerolinecolor="#aab",
            scaleanchor="x",
        ),
        height=560,
        margin=dict(l=20, r=20, t=40, b=20),
        dragmode="pan",
    )
    return fig


# ---------------------------------------------------------------------------
# Layout: sidebar panel (left) + main canvas (right)
# ---------------------------------------------------------------------------
panel_col, canvas_col = st.columns([1, 2])

# ── LEFT PANEL ──────────────────────────────────────────────────────────────
with panel_col:
    tab_nodes, tab_edges, tab_io = st.tabs(["Knoten", "Verbindungen", "Import/Export"])

    # ---- TAB: Knoten ----
    with tab_nodes:
        st.markdown('<div class="section-header">Knoten hinzufügen</div>', unsafe_allow_html=True)

        node_type = st.selectbox(
            "Gerätetyp",
            options=list(NODE_TYPES.keys()),
            format_func=lambda k: NODE_TYPES[k]["label"],
            key="new_node_type",
        )

        node_label = st.text_input("Bezeichnung", value=f"Neues {NODE_TYPES[node_type]['label']}", key="new_node_label")

        col_x, col_y = st.columns(2)
        with col_x:
            node_x = st.number_input("X-Position [m]", value=0.0, step=1.0, key="new_node_x")
        with col_y:
            node_y = st.number_input("Y-Position [m]", value=0.0, step=1.0, key="new_node_y")

        # Type-specific fields
        extra_fields = {}
        if node_type == "CHILLER":
            model_key = st.selectbox(
                "Modell",
                options=list(CHILLERS.keys()),
                format_func=lambda k: CHILLERS[k]["model"],
                key="new_chiller_model",
            )
            extra_fields["model"] = model_key
            ch = get_chiller(model_key)
            st.info(
                f"**{ch['model']}** — {ch['cooling_capacity_kW']} kW Kälteleistung, "
                f"EER {ch['eer']}, Pumpendruckhöhe {ch['pump_head_kPa']} kPa"
            )

        elif node_type == "FAN_COIL":
            fc_model_key = st.selectbox(
                "Modell",
                options=list(FAN_COILS.keys()),
                format_func=lambda k: FAN_COILS[k]["model"],
                key="new_fc_model",
            )
            extra_fields["model"] = fc_model_key
            room = st.text_input("Raumbezeichnung", value="Raum 1", key="new_fc_room")
            voltage = st.selectbox("Betriebsspannung [V]", options=[10, 8, 6, 4, 2], index=0, key="new_fc_voltage")
            extra_fields["room"] = room
            extra_fields["voltage"] = voltage
            fc = get_fan_coil(fc_model_key)
            perf = fc["performance"][voltage]
            st.info(
                f"**{fc['model']}** bei {voltage}V — {perf['cooling_total_W']} W Kühlleistung, "
                f"{perf['airflow_m3h']} m³/h Luftvolumen"
            )

        if st.button("➕ Knoten hinzufügen", use_container_width=True, type="primary"):
            new_node = {
                "id":    make_node_id(),
                "type":  node_type,
                "label": node_label,
                "x":     float(node_x),
                "y":     float(node_y),
                **extra_fields,
            }
            st.session_state.nodes.append(new_node)
            st.session_state.calc_results = None
            st.success(f"Knoten '{node_label}' hinzugefügt.")
            st.rerun()

        st.markdown("---")
        st.markdown('<div class="section-header">Vorhandene Knoten</div>', unsafe_allow_html=True)

        if not st.session_state.nodes:
            st.info("Noch keine Knoten vorhanden.")
        else:
            for i, node in enumerate(list(st.session_state.nodes)):
                with st.expander(
                    f"{NODE_TYPES.get(node['type'], {}).get('label','?')} — {node['label']} [{node['id'][:8]}]",
                    expanded=False,
                ):
                    c1, c2 = st.columns(2)
                    new_label = c1.text_input("Bezeichnung", value=node.get("label", ""), key=f"lbl_{node['id']}")
                    new_x = c1.number_input("X [m]", value=float(node.get("x", 0)), step=1.0, key=f"x_{node['id']}")
                    new_y = c2.number_input("Y [m]", value=float(node.get("y", 0)), step=1.0, key=f"y_{node['id']}")

                    if node.get("type") == "FAN_COIL":
                        new_room = c1.text_input("Raum", value=node.get("room", ""), key=f"rm_{node['id']}")
                        new_v = c2.selectbox("Spannung [V]", options=[10,8,6,4,2],
                                             index=[10,8,6,4,2].index(int(node.get("voltage",10))),
                                             key=f"v_{node['id']}")
                        st.session_state.nodes[i]["room"] = new_room
                        st.session_state.nodes[i]["voltage"] = new_v

                    st.session_state.nodes[i]["label"] = new_label
                    st.session_state.nodes[i]["x"] = new_x
                    st.session_state.nodes[i]["y"] = new_y

                    if st.button("🗑️ Löschen", key=f"del_node_{node['id']}", type="secondary"):
                        # Remove node and all connected edges
                        st.session_state.nodes = [n for n in st.session_state.nodes if n["id"] != node["id"]]
                        st.session_state.edges = [e for e in st.session_state.edges
                                                   if e["source"] != node["id"] and e["target"] != node["id"]]
                        st.session_state.calc_results = None
                        st.rerun()

    # ---- TAB: Verbindungen ----
    with tab_edges:
        st.markdown('<div class="section-header">Rohrsegment verbinden</div>', unsafe_allow_html=True)

        node_ids = [n["id"] for n in st.session_state.nodes]
        node_labels_map = {n["id"]: f"{n.get('label','?')} [{n['id'][:6]}]" for n in st.session_state.nodes}

        if len(node_ids) < 2:
            st.info("Mindestens 2 Knoten erforderlich.")
        else:
            src_id = st.selectbox(
                "Von (Quelle)",
                options=node_ids,
                format_func=lambda k: node_labels_map.get(k, k),
                key="edge_src",
            )
            tgt_id = st.selectbox(
                "Nach (Ziel)",
                options=[n for n in node_ids if n != src_id],
                format_func=lambda k: node_labels_map.get(k, k),
                key="edge_tgt",
            )
            length_m = st.number_input("Rohrlänge [m]", value=5.0, min_value=0.1, step=0.5, key="edge_len")

            st.markdown("**Formteile (Anzahl)**")
            f_col1, f_col2 = st.columns(2)
            with f_col1:
                n_elbow  = st.number_input("Bögen 90°", value=0, min_value=0, step=1, key="f_elbow")
                n_t_thr  = st.number_input("T-Stück Durchgang", value=0, min_value=0, step=1, key="f_t_thr")
                n_coupl  = st.number_input("Kupplungen", value=0, min_value=0, step=1, key="f_coupl")
            with f_col2:
                n_t_br   = st.number_input("T-Stück Abzweig", value=0, min_value=0, step=1, key="f_t_br")
                n_iso    = st.number_input("Absperrventile", value=0, min_value=0, step=1, key="f_iso")
                n_bal    = st.number_input("Regulierventile", value=0, min_value=0, step=1, key="f_bal")

            fittings = {}
            if n_elbow > 0: fittings["elbow_90"]         = int(n_elbow)
            if n_t_thr > 0: fittings["t_through"]        = int(n_t_thr)
            if n_t_br  > 0: fittings["t_branch"]         = int(n_t_br)
            if n_coupl > 0: fittings["coupling"]          = int(n_coupl)
            if n_iso   > 0: fittings["valve_isolation"]   = int(n_iso)
            if n_bal   > 0: fittings["valve_balancing"]   = int(n_bal)

            edge_label = st.text_input("Bezeichnung (optional)", value="", key="edge_lbl")

            if st.button("➕ Rohrsegment hinzufügen", use_container_width=True, type="primary"):
                new_edge = {
                    "id":       make_edge_id(),
                    "source":   src_id,
                    "target":   tgt_id,
                    "length_m": float(length_m),
                    "fittings": fittings,
                    "label":    edge_label,
                }
                st.session_state.edges.append(new_edge)
                st.session_state.calc_results = None
                st.success(f"Rohrsegment hinzugefügt ({length_m:.1f} m).")
                st.rerun()

        st.markdown("---")
        st.markdown('<div class="section-header">Vorhandene Rohrsegmente</div>', unsafe_allow_html=True)

        if not st.session_state.edges:
            st.info("Noch keine Verbindungen vorhanden.")
        else:
            for i, edge in enumerate(list(st.session_state.edges)):
                src_lbl = node_labels_map.get(edge.get("source", ""), edge.get("source", ""))
                tgt_lbl = node_labels_map.get(edge.get("target", ""), edge.get("target", ""))
                with st.expander(
                    f"📏 {src_lbl} → {tgt_lbl} — {edge.get('length_m', 0):.1f} m  [{edge['id'][:8]}]",
                    expanded=False,
                ):
                    new_len = st.number_input(
                        "Länge [m]", value=float(edge.get("length_m", 1.0)),
                        min_value=0.1, step=0.5, key=f"elen_{edge['id']}"
                    )
                    st.session_state.edges[i]["length_m"] = new_len

                    fit = edge.get("fittings", {})
                    st.caption(f"Formteile: {fit if fit else 'keine'}")

                    if st.button("🗑️ Löschen", key=f"del_edge_{edge['id']}", type="secondary"):
                        st.session_state.edges = [e for e in st.session_state.edges if e["id"] != edge["id"]]
                        st.session_state.calc_results = None
                        st.rerun()

    # ---- TAB: Import/Export ----
    with tab_io:
        st.markdown('<div class="section-header">Netzwerk speichern / laden</div>', unsafe_allow_html=True)

        # Export
        if st.button("📥 Als JSON exportieren", use_container_width=True):
            json_str = network_to_json(
                st.session_state.nodes,
                st.session_state.edges,
                st.session_state.system_params,
            )
            st.download_button(
                "💾 JSON herunterladen",
                data=json_str,
                file_name=f"{st.session_state.system_params.get('project_name','network')}.json",
                mime="application/json",
                use_container_width=True,
            )

        st.markdown("---")
        # Import
        uploaded = st.file_uploader("📤 JSON importieren", type=["json"], key="net_import")
        if uploaded:
            try:
                json_str = uploaded.read().decode("utf-8")
                nodes, edges, sp = network_from_json(json_str)
                st.session_state.nodes  = nodes
                st.session_state.edges  = edges
                st.session_state.system_params = sp
                st.session_state.calc_results  = None
                st.success(f"Netzwerk geladen: {len(nodes)} Knoten, {len(edges)} Segmente.")
                st.rerun()
            except Exception as e:
                st.error(f"Importfehler: {e}")

        st.markdown("---")
        st.markdown('<div class="section-header">Beispielnetzwerk</div>', unsafe_allow_html=True)
        if st.button("🏗️ Beispielnetzwerk laden", use_container_width=True):
            # Create a sample network: 1 chiller → manifold → 3 fan coils
            from utils.helpers import make_node_id, make_edge_id
            n_ch  = {"id": make_node_id(), "type": "CHILLER",  "label": "Kältemaschine KM-1",
                      "model": "Climaveneta_iBX2_G07_27Y", "x": 0.0, "y": 0.0}
            n_man = {"id": make_node_id(), "type": "DISTRIBUTION_MANIFOLD", "label": "Verteiler V-1",
                      "x": 5.0, "y": 0.0}
            n_fc1 = {"id": make_node_id(), "type": "FAN_COIL", "label": "GK-1",
                      "model": "Kampmann_KaCool_W_Size4", "room": "Büro 1.01",
                      "voltage": 10, "x": 9.0, "y":  3.0}
            n_fc2 = {"id": make_node_id(), "type": "FAN_COIL", "label": "GK-2",
                      "model": "Kampmann_KaCool_W_Size4", "room": "Büro 1.02",
                      "voltage": 8,  "x": 9.0, "y":  0.0}
            n_fc3 = {"id": make_node_id(), "type": "FAN_COIL", "label": "GK-3",
                      "model": "Kampmann_KaCool_W_Size4", "room": "Sitzungszimmer",
                      "voltage": 10, "x": 9.0, "y": -3.0}

            e1 = {"id": make_edge_id(), "source": n_ch["id"],  "target": n_man["id"],
                   "length_m": 5.0, "fittings": {"coupling": 2}, "label": "VL/RL Hauptleitung"}
            e2 = {"id": make_edge_id(), "source": n_man["id"], "target": n_fc1["id"],
                   "length_m": 8.0, "fittings": {"elbow_90": 2, "t_branch": 1, "valve_isolation": 2},
                   "label": "Stichleitung GK-1"}
            e3 = {"id": make_edge_id(), "source": n_man["id"], "target": n_fc2["id"],
                   "length_m": 6.0, "fittings": {"elbow_90": 1, "t_through": 1, "valve_isolation": 2},
                   "label": "Stichleitung GK-2"}
            e4 = {"id": make_edge_id(), "source": n_man["id"], "target": n_fc3["id"],
                   "length_m": 9.0, "fittings": {"elbow_90": 2, "t_branch": 1, "valve_isolation": 2},
                   "label": "Stichleitung GK-3"}

            st.session_state.nodes = [n_ch, n_man, n_fc1, n_fc2, n_fc3]
            st.session_state.edges = [e1, e2, e3, e4]
            st.session_state.calc_results = None
            st.success("Beispielnetzwerk geladen (1 Kältemaschine, 1 Verteiler, 3 Gebläsekonvektoren).")
            st.rerun()

        if st.button("🗑️ Netzwerk leeren", use_container_width=True, type="secondary"):
            st.session_state.nodes = []
            st.session_state.edges = []
            st.session_state.calc_results = None
            st.rerun()


# ── RIGHT PANEL: Network canvas ───────────────────────────────────────────
with canvas_col:
    st.markdown("### Netzwerk-Ansicht")

    fig = build_plotly_figure(st.session_state.nodes, st.session_state.edges)
    st.plotly_chart(fig, use_container_width=True, key="network_canvas")

    # Summary table
    if st.session_state.nodes:
        st.markdown("#### Knotenübersicht")
        node_rows = []
        for n in st.session_state.nodes:
            type_label = NODE_TYPES.get(n.get("type",""), {}).get("label", n.get("type",""))
            row = {
                "ID":          n["id"][:8],
                "Typ":         type_label,
                "Bezeichnung": n.get("label", ""),
                "X [m]":       n.get("x", 0),
                "Y [m]":       n.get("y", 0),
                "Zusatz":      n.get("room", n.get("model", "")),
            }
            node_rows.append(row)
        import pandas as pd
        df_nodes = pd.DataFrame(node_rows)
        st.dataframe(df_nodes, use_container_width=True, hide_index=True)

    if st.session_state.edges:
        st.markdown("#### Rohrsegmentübersicht")
        node_map_label = {n["id"]: n.get("label", n["id"]) for n in st.session_state.nodes}
        edge_rows = []
        for e in st.session_state.edges:
            fit_str = ", ".join(f"{k}:{v}" for k, v in e.get("fittings", {}).items()) or "—"
            edge_rows.append({
                "ID":          e["id"][:8],
                "Von":         node_map_label.get(e["source"], e["source"]),
                "Nach":        node_map_label.get(e["target"], e["target"]),
                "Länge [m]":   e.get("length_m", 0),
                "Formteile":   fit_str,
            })
        import pandas as pd
        df_edges = pd.DataFrame(edge_rows)
        st.dataframe(df_edges, use_container_width=True, hide_index=True)

    # Quick-navigate
    st.markdown("---")
    st.markdown("*Netzwerk fertig? Weiter zur Hydraulikberechnung →*")
    st.page_link("pages/2_📊_Hydraulic_Calculation.py", label="📊 Zur Hydraulikberechnung", icon="📊")
