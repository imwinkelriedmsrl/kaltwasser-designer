"""
Netzwerk-Editor — Seite 1
Festes Layout mit Kältemaschine oben links + Drag-and-Drop.
"""

import streamlit as st
import json
import uuid
from typing import Dict, List, Any

from streamlit_agraph import agraph, Node, Edge, Config

from utils.helpers import (
    init_session_state,
    make_node_id,
    make_edge_id,
    network_to_json,
    network_from_json,
)
from data.component_library import NODE_TYPES, CHILLERS, FAN_COILS, get_chiller, get_fan_coil

# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Netzwerk-Editor | Kaltwasser Designer",
    layout="wide",
    page_icon="🔧",
)
init_session_state(st)

import os as _os
_logo_p = _os.path.join(_os.path.dirname(__file__), "..", "static", "imwinkelried_logo.png")
if _os.path.exists(_logo_p):
    st.logo(_logo_p, size="large", link="https://www.imwinkelried.ch")

st.markdown("""
<style>
.section-header {
    font-size: 1rem; font-weight: 700; color: #1565C0;
    border-bottom: 2px solid #1565C0; padding-bottom: 4px; margin-bottom: 12px;
}
.node-summary {
    background: #f0f4f8; border: 1px solid #c8d6e8; border-radius: 6px;
    padding: 8px 12px; margin-bottom: 6px; font-size: 0.88rem;
}
</style>
""", unsafe_allow_html=True)

st.markdown("# 🔧 Netzwerk-Editor")
st.markdown(
    "Geräte hinzufügen und mit Rohrsegmenten verbinden. "
    "Kältemaschine wird oben links platziert — Knoten können per Drag-and-Drop verschoben werden."
)

# ---------------------------------------------------------------------------
# Helper: label for a node
# ---------------------------------------------------------------------------

def node_display_label(node: Dict) -> str:
    lbl = node.get("label", node["id"])
    ntype = node.get("type", "")
    props = node.get("props", {})
    if ntype == "FAN_COIL":
        room = props.get("room", node.get("room", ""))
        if room:
            return f"{lbl}\n{room}"
    return lbl


def node_id_label(node: Dict) -> str:
    return f"{node.get('label', node['id'])} [{node['id'][:6]}]"


# ---------------------------------------------------------------------------
# Build agraph nodes + edges from session state — fixed positions
# ---------------------------------------------------------------------------

def _get_fixed_position(node: Dict, index_by_type: Dict[str, int]) -> Dict:
    """Return x, y fixed position for a node based on its type."""
    ntype = node.get("type", "FAN_COIL")
    positions = st.session_state.get("node_positions", {})
    nid = node["id"]

    # If user has dragged the node, use stored position
    if nid in positions:
        return positions[nid]

    # Otherwise assign default position by type
    idx = index_by_type.get(nid, 0)
    if ntype == "CHILLER":
        return {"x": 100 + idx * 200, "y": 100}
    elif ntype == "T_JUNCTION":
        return {"x": 300 + idx * 150, "y": 250}
    elif ntype == "FAN_COIL":
        return {"x": 100 + idx * 200, "y": 420}
    elif ntype == "AIR_VENT":
        return {"x": 650 + idx * 100, "y": 100}
    elif ntype == "FILL_DRAIN":
        return {"x": 650 + idx * 100, "y": 200}
    else:
        return {"x": 400 + idx * 150, "y": 300}


def build_agraph(nodes: List[Dict], edges: List[Dict]):
    ag_nodes = []
    ag_edges = []

    # Count index per type for position assignment
    type_counters: Dict[str, int] = {}
    index_by_type: Dict[str, int] = {}
    for n in nodes:
        ntype = n.get("type", "FAN_COIL")
        idx = type_counters.get(ntype, 0)
        index_by_type[n["id"]] = idx
        type_counters[ntype] = idx + 1

    for n in nodes:
        ntype = n.get("type", "FAN_COIL")
        color = NODE_TYPES.get(ntype, {}).get("color", "#888888")
        label = node_display_label(n)
        pos = _get_fixed_position(n, index_by_type)

        ag_nodes.append(
            Node(
                id=n["id"],
                label=label,
                size=25,
                color=color,
                font={"size": 11, "color": "#1a2332"},
                x=pos["x"],
                y=pos["y"],
                fixed=False,  # allow drag
            )
        )

    for e in edges:
        props = e.get("props", {})
        dn = props.get("dn_sized", None)
        length_m = e.get("length_m", props.get("length_m", 0.0))
        if dn:
            edge_label = f"DN{dn} / {length_m:.1f}m"
        else:
            edge_label = f"{length_m:.1f}m"
        ag_edges.append(
            Edge(
                source=e["source"],
                target=e["target"],
                label=edge_label,
                color="#5c8dc8",
                width=2,
            )
        )

    return ag_nodes, ag_edges


# ---------------------------------------------------------------------------
# agraph Config — fixed layout, no physics
# ---------------------------------------------------------------------------

AGRAPH_CONFIG = Config(
    width=900,
    height=600,
    directed=True,
    physics=False,
    hierarchical=False,
    nodeHighlightBehavior=True,
    highlightColor="#F7A7A6",
    collapsible=False,
    node={"labelProperty": "label", "renderLabel": True},
    link={"labelProperty": "label", "renderLabel": True},
)

# ---------------------------------------------------------------------------
# Generic form helpers
# ---------------------------------------------------------------------------

def _chiller_library_form(prefix: str) -> Dict:
    """Render library chiller selector. Returns extra props dict."""
    lib_keys = list(CHILLERS.keys())
    custom_ch = st.session_state.get("custom_chillers", [])
    all_keys = lib_keys + [f"__custom__{c['_key']}" for c in custom_ch]

    def fmt_key(k):
        if k.startswith("__custom__"):
            key = k.replace("__custom__", "")
            match = next((c for c in custom_ch if c["_key"] == key), None)
            return f"[Benutzerdef.] {match['model'] if match else key}"
        return f"{CHILLERS[k]['manufacturer']} {CHILLERS[k]['model']}"

    sel = st.selectbox("Modell", options=all_keys, format_func=fmt_key, key=f"{prefix}_lib_sel")

    if sel.startswith("__custom__"):
        key = sel.replace("__custom__", "")
        ch_data = next((c for c in custom_ch if c["_key"] == key), {})
        st.info(
            f"**{ch_data.get('model','—')}** — {ch_data.get('cooling_capacity_kW','?')} kW, "
            f"Pumpendruckhöhe {ch_data.get('pump_head_kPa','?')} kPa"
        )
        return {"model": "custom", **ch_data}
    else:
        ch = get_chiller(sel)
        st.info(
            f"**{ch['model']}** — {ch['cooling_capacity_kW']} kW Kälteleistung, "
            f"EER {ch['eer']}, Pumpe: {ch.get('pump_head_kPa', '?')} kPa"
        )
        return {"model": sel, "pump_head_kPa": ch["pump_head_kPa"]}


def _chiller_pump_fields(prefix: str, defaults: Dict) -> Dict:
    """Render pump fields for a chiller. Returns pump props dict."""
    st.markdown("**Pumpe**")
    pump_integrated = st.checkbox(
        "Pumpe integriert",
        value=bool(defaults.get("pump_integrated", True)),
        key=f"{prefix}_pump_int",
    )
    pump_head = st.number_input(
        "Pumpenförderhöhe [kPa]",
        value=float(defaults.get("pump_head_kPa", 96.8)),
        min_value=0.0, max_value=500.0, step=1.0,
        key=f"{prefix}_pump_head",
    )
    pump_flow = st.number_input(
        "Pumpenvolumenstrom max. [m³/h]",
        value=float(defaults.get("pump_flow_max_m3h", 5.5)),
        min_value=0.0, max_value=50.0, step=0.1,
        key=f"{prefix}_pump_flow",
    )
    pump_type = st.text_input(
        "Pumpentyp",
        value=str(defaults.get("pump_type", "Hocheffizienzpumpe EC")),
        key=f"{prefix}_pump_type",
    )
    return {
        "pump_integrated":    pump_integrated,
        "pump_head_kPa":      pump_head,
        "pump_flow_max_m3h":  pump_flow,
        "pump_type":          pump_type,
    }


def _chiller_auxiliary_fields(prefix: str, defaults: Dict) -> Dict:
    """Render expansion vessel, safety valve, buffer tank fields. Returns props dict."""
    st.markdown("**Ausdehnungsgefäss**")
    exp_int = st.checkbox(
        "Ausdehnungsgefäss integriert",
        value=bool(defaults.get("expansion_vessel_integrated", False)),
        key=f"{prefix}_exp_int",
    )
    exp_vol = st.number_input(
        "Volumen [L]",
        value=float(defaults.get("expansion_vessel_L", 8.0)),
        min_value=0.0, max_value=500.0, step=1.0,
        key=f"{prefix}_exp_vol",
    )

    st.markdown("**Sicherheitsventil**")
    sv_int = st.checkbox(
        "Sicherheitsventil integriert",
        value=bool(defaults.get("safety_valve_integrated", False)),
        key=f"{prefix}_sv_int",
    )
    sv_bar = st.number_input(
        "Ansprechdruck [bar]",
        value=float(defaults.get("safety_valve_bar", 3.0)),
        min_value=0.5, max_value=10.0, step=0.5,
        key=f"{prefix}_sv_bar",
    )

    st.markdown("**Pufferspeicher**")
    buf_int = st.checkbox(
        "Pufferspeicher integriert",
        value=bool(defaults.get("buffer_tank_integrated", False)),
        key=f"{prefix}_buf_int",
    )
    buf_vol = st.number_input(
        "Volumen [L]",
        value=float(defaults.get("buffer_tank_L", 0.0)),
        min_value=0.0, max_value=2000.0, step=10.0,
        key=f"{prefix}_buf_vol",
    )

    return {
        "expansion_vessel_integrated": exp_int,
        "expansion_vessel_L":          exp_vol,
        "safety_valve_integrated":     sv_int,
        "safety_valve_bar":            sv_bar,
        "buffer_tank_integrated":      buf_int,
        "buffer_tank_L":               buf_vol,
    }


def _chiller_custom_form(prefix: str) -> Dict:
    """Render custom chiller entry form. Returns props dict."""
    st.markdown("**Benutzerdefiniertes Aussengerät**")
    hersteller   = st.text_input("Hersteller", value="", key=f"{prefix}_hersteller")
    modell       = st.text_input("Modell", value="", key=f"{prefix}_modell")
    kaelteleist  = st.number_input("Kälteleistung [kW]", value=10.0, min_value=0.1, step=0.5, key=f"{prefix}_kaelteleist")
    leistaufn    = st.number_input("Leistungsaufnahme [kW]", value=3.0, min_value=0.0, step=0.1, key=f"{prefix}_leistaufn")
    eer          = st.number_input("EER", value=3.0, min_value=0.0, step=0.1, key=f"{prefix}_eer")
    t_sup        = st.number_input("Vorlauftemperatur [°C]", value=7.0, step=0.5, key=f"{prefix}_tsup")
    t_ret        = st.number_input("Rücklauftemperatur [°C]", value=12.0, step=0.5, key=f"{prefix}_tret")
    vol_m3h      = st.number_input("Volumenstrom [m³/h]", value=2.0, min_value=0.0, step=0.1, key=f"{prefix}_vol")
    dp_evap      = st.number_input("Druckverlust Verdampfer [kPa]", value=20.0, min_value=0.0, step=1.0, key=f"{prefix}_dpevap")
    pump_head_c  = st.number_input("Pumpenförderhöhe [kPa]", value=80.0, min_value=0.0, step=1.0, key=f"{prefix}_pumpheadc")
    kaeltemittel = st.text_input("Kältemittel", value="R32", key=f"{prefix}_kaeltemittel")
    gwp          = st.number_input("GWP Wert", value=675, min_value=0, step=1, key=f"{prefix}_gwp")
    anschluss    = st.text_input("Anschluss", value='1"', key=f"{prefix}_anschluss")
    schall       = st.number_input("Schallleistung [dB(A)]", value=70.0, min_value=0.0, step=1.0, key=f"{prefix}_schall")
    notizen      = st.text_area("Notizen", value="", key=f"{prefix}_notizen")

    _key = uuid.uuid4().hex[:8]
    return {
        "model":                 "custom",
        "_key":                  _key,
        "manufacturer":          hersteller,
        "model_name":            modell,
        "cooling_capacity_kW":   kaelteleist,
        "power_input_kW":        leistaufn,
        "eer":                   eer,
        "t_supply_C":            t_sup,
        "t_return_C":            t_ret,
        "flow_rate_m3h":         vol_m3h,
        "dp_evaporator_kPa":     dp_evap,
        "pump_head_kPa":         pump_head_c,
        "refrigerant":           kaeltemittel,
        "gwp":                   gwp,
        "connection_supply":     anschluss,
        "sound_power_dBa":       schall,
        "notes":                 notizen,
    }


def _fc_library_form(prefix: str) -> Dict:
    """Render library fan coil selector. Returns extra props dict."""
    lib_keys = list(FAN_COILS.keys())
    custom_fc = st.session_state.get("custom_fan_coils", [])
    all_keys = lib_keys + [f"__custom__{c['_key']}" for c in custom_fc]

    def fmt_key(k):
        if k.startswith("__custom__"):
            key = k.replace("__custom__", "")
            match = next((c for c in custom_fc if c["_key"] == key), None)
            return f"[Benutzerdef.] {match.get('model_name','?') if match else key}"
        return f"{FAN_COILS[k]['manufacturer']} {FAN_COILS[k]['model']}"

    sel = st.selectbox("Modell", options=all_keys, format_func=fmt_key, key=f"{prefix}_lib_sel")

    if sel.startswith("__custom__"):
        key = sel.replace("__custom__", "")
        fc_data = next((c for c in custom_fc if c["_key"] == key), {})
        st.info(
            f"**{fc_data.get('model_name','—')}** — "
            f"{fc_data.get('cooling_W','?')} W, {fc_data.get('flow_lh','?')} l/h"
        )
        return {"model": "custom", **fc_data}
    else:
        fc = get_fan_coil(sel)
        perf10 = fc["performance"][10]
        st.info(
            f"**{fc['model']}** bei 10V — {perf10['cooling_total_W']} W, "
            f"{perf10['airflow_m3h']} m³/h, {fc['water_flow_lh']} l/h, "
            f"{fc['water_resistance_kPa']} kPa"
        )
        return {
            "model":       sel,
            "cooling_W":   perf10["cooling_total_W"],
            "flow_lh":     fc["water_flow_lh"],
            "dp_kPa":      fc["water_resistance_kPa"],
            "connection":  fc.get("connection_supply", '½"'),
        }


def _fc_custom_form(prefix: str) -> Dict:
    """Render custom fan coil entry form. Returns props dict."""
    st.markdown("**Benutzerdefinierter Gebläsekonvektor**")
    hersteller  = st.text_input("Hersteller", value="", key=f"{prefix}_fc_hersteller")
    modell      = st.text_input("Modell", value="", key=f"{prefix}_fc_modell")
    kuehllst    = st.number_input("Kühlleistung [W] (Auslegungspunkt)", value=2000, min_value=1, step=50, key=f"{prefix}_fc_kuehl")
    vol_lh      = st.number_input("Volumenstrom [l/h]", value=300, min_value=1, step=10, key=f"{prefix}_fc_vol")
    dp_kpa      = st.number_input("Druckverlust [kPa]", value=20.0, min_value=0.0, step=0.5, key=f"{prefix}_fc_dp")
    anschluss   = st.text_input("Anschluss", value='½"', key=f"{prefix}_fc_anschluss")
    schall      = st.number_input("Schallleistung [dB(A)]", value=35.0, min_value=0.0, step=1.0, key=f"{prefix}_fc_schall")
    notizen     = st.text_area("Notizen", value="", key=f"{prefix}_fc_notizen")

    _key = uuid.uuid4().hex[:8]
    return {
        "model":        "custom",
        "_key":         _key,
        "manufacturer": hersteller,
        "model_name":   modell,
        "cooling_W":    kuehllst,
        "flow_lh":      vol_lh,
        "dp_kPa":       dp_kpa,
        "connection":   anschluss,
        "sound_dBa":    schall,
        "notes":        notizen,
    }


# ---------------------------------------------------------------------------
# Layout: left sidebar panel + right agraph canvas
# ---------------------------------------------------------------------------

panel_col, canvas_col = st.columns([3, 7])

# ── LEFT PANEL ───────────────────────────────────────────────────────────────
with panel_col:
    mode = st.radio(
        "Modus",
        options=["Knoten hinzufügen", "Verbindungen", "Bearbeiten", "Löschen", "Import/Export"],
        horizontal=False,
        key="editor_mode",
    )
    st.markdown("---")

    # -------------------------------------------------------------------------
    if mode == "Knoten hinzufügen":
        st.markdown('<div class="section-header">Knoten hinzufügen</div>', unsafe_allow_html=True)

        node_type = st.selectbox(
            "Gerätetyp",
            options=list(NODE_TYPES.keys()),
            format_func=lambda k: NODE_TYPES[k]["label"],
            key="add_node_type",
        )

        node_label = st.text_input(
            "Bezeichnung",
            value=f"{NODE_TYPES[node_type]['label'][:4]}-{len(st.session_state.nodes)+1:02d}",
            key="add_node_label",
        )

        extra_props: Dict = {}

        # --- CHILLER form ---
        if node_type == "CHILLER":
            st.markdown("**Aussengerät konfigurieren**")
            ch_source = st.radio(
                "Quelle",
                options=["Aus Bibliothek", "Benutzerdefiniert"],
                horizontal=True,
                key="add_ch_source",
            )
            if ch_source == "Aus Bibliothek":
                lib_props = _chiller_library_form("add_ch")
                # Load defaults from library if available
                ch_defaults = {}
                if lib_props.get("model") and lib_props["model"] != "custom":
                    try:
                        ch_defaults = get_chiller(lib_props["model"])
                    except Exception:
                        pass
                pump_defaults = {
                    "pump_integrated":   ch_defaults.get("pump_integrated", True),
                    "pump_head_kPa":     lib_props.get("pump_head_kPa", ch_defaults.get("pump_head_kPa", 96.8)),
                    "pump_flow_max_m3h": ch_defaults.get("pump_flow_max_m3h", 5.5),
                    "pump_type":         ch_defaults.get("pump_type", "Hocheffizienzpumpe EC"),
                }
                aux_defaults = {
                    "expansion_vessel_integrated": ch_defaults.get("expansion_vessel_integrated", False),
                    "expansion_vessel_L":          ch_defaults.get("expansion_vessel_L", 8.0),
                    "safety_valve_integrated":     ch_defaults.get("safety_valve_integrated", False),
                    "safety_valve_bar":            ch_defaults.get("safety_valve_bar", 3.0),
                    "buffer_tank_integrated":      ch_defaults.get("buffer_tank_integrated", False),
                    "buffer_tank_L":               ch_defaults.get("buffer_tank_L", 0.0),
                }
                pump_props = _chiller_pump_fields("add_ch", pump_defaults)
                aux_props  = _chiller_auxiliary_fields("add_ch_aux", aux_defaults)
                extra_props = {**lib_props, **pump_props, **aux_props}
            else:
                custom_props = _chiller_custom_form("add_ch")
                pump_props = _chiller_pump_fields("add_ch_cust", {
                    "pump_head_kPa": custom_props.get("pump_head_kPa", 80.0),
                })
                aux_props = _chiller_auxiliary_fields("add_ch_cust_aux", {})
                extra_props = {**custom_props, **pump_props, **aux_props}

        # --- FAN_COIL form ---
        elif node_type == "FAN_COIL":
            st.markdown("**Innengerät konfigurieren**")
            fc_source = st.radio(
                "Quelle",
                options=["Aus Bibliothek", "Benutzerdefiniert"],
                horizontal=True,
                key="add_fc_source",
            )
            if fc_source == "Aus Bibliothek":
                extra_props = _fc_library_form("add_fc")
            else:
                extra_props = _fc_custom_form("add_fc")

            room = st.text_input("Raumbez.", value="", key="add_fc_room")
            extra_props["room"] = room

        if st.button("Knoten hinzufügen", use_container_width=True, type="primary", key="btn_add_node"):
            new_node = {
                "id":    make_node_id(),
                "type":  node_type,
                "label": node_label,
                "props": extra_props,
            }
            # Save custom items to session state for reuse and library
            if node_type == "CHILLER" and extra_props.get("model") == "custom":
                key_val = extra_props.get("_key", "")
                if key_val and not any(c.get("_key") == key_val for c in st.session_state.custom_chillers):
                    st.session_state.custom_chillers.append(extra_props)
            if node_type == "FAN_COIL" and extra_props.get("model") == "custom":
                key_val = extra_props.get("_key", "")
                if key_val and not any(c.get("_key") == key_val for c in st.session_state.custom_fan_coils):
                    st.session_state.custom_fan_coils.append(extra_props)

            st.session_state.nodes.append(new_node)
            st.session_state.calc_results = None
            st.success(f"Knoten '{node_label}' hinzugefügt.")
            st.rerun()

        # "In Bibliothek speichern" button for library items
        if node_type in ("CHILLER", "FAN_COIL"):
            st.markdown("---")
            if st.button("In Bibliothek speichern", use_container_width=True, key="btn_save_lib"):
                if node_type == "CHILLER" and extra_props.get("model") == "custom":
                    key_val = extra_props.get("_key", uuid.uuid4().hex[:8])
                    extra_props["_key"] = key_val
                    if not any(c.get("_key") == key_val for c in st.session_state.custom_chillers):
                        st.session_state.custom_chillers.append(dict(extra_props))
                        st.success("Aussengerät in Bibliothek gespeichert.")
                    else:
                        st.info("Gerät bereits in Bibliothek.")
                elif node_type == "FAN_COIL" and extra_props.get("model") == "custom":
                    key_val = extra_props.get("_key", uuid.uuid4().hex[:8])
                    extra_props["_key"] = key_val
                    if not any(c.get("_key") == key_val for c in st.session_state.custom_fan_coils):
                        st.session_state.custom_fan_coils.append(dict(extra_props))
                        st.success("Innengerät in Bibliothek gespeichert.")
                    else:
                        st.info("Gerät bereits in Bibliothek.")
                else:
                    st.info("Nur benutzerdefinierte Geräte können in der Bibliothek gespeichert werden.")

    # -------------------------------------------------------------------------
    elif mode == "Verbindungen":
        st.markdown('<div class="section-header">Rohrsegment verbinden</div>', unsafe_allow_html=True)

        node_ids = [n["id"] for n in st.session_state.nodes]
        node_labels_map = {n["id"]: node_id_label(n) for n in st.session_state.nodes}

        if len(node_ids) < 2:
            st.info("Mindestens 2 Knoten erforderlich.")
        else:
            src_id = st.selectbox(
                "Von (Quelle)",
                options=node_ids,
                format_func=lambda k: node_labels_map.get(k, k),
                key="edge_src",
            )
            tgt_options = [n for n in node_ids if n != src_id]
            tgt_id = st.selectbox(
                "Nach (Ziel)",
                options=tgt_options,
                format_func=lambda k: node_labels_map.get(k, k),
                key="edge_tgt",
            )
            length_m = st.number_input(
                "Rohrlänge [m]", value=5.0, min_value=0.1, step=0.5, key="edge_len"
            )

            st.markdown("**Formteile (Anzahl)**")
            fc1, fc2 = st.columns(2)
            with fc1:
                n_elbow = st.number_input("Bögen 90°",           value=0, min_value=0, step=1, key="f_elbow")
                n_t_thr = st.number_input("T-Stück Durchgang",   value=0, min_value=0, step=1, key="f_t_thr")
                n_coupl = st.number_input("Kupplungen",           value=0, min_value=0, step=1, key="f_coupl")
            with fc2:
                n_t_br  = st.number_input("T-Stück Abzweig",     value=0, min_value=0, step=1, key="f_t_br")
                n_iso   = st.number_input("Absperrventile",       value=0, min_value=0, step=1, key="f_iso")
                n_bal   = st.number_input("Regulierventile",      value=0, min_value=0, step=1, key="f_bal")

            fittings_raw = {}
            if n_elbow > 0: fittings_raw["elbow_90"]       = int(n_elbow)
            if n_t_thr > 0: fittings_raw["t_through"]      = int(n_t_thr)
            if n_t_br  > 0: fittings_raw["t_branch"]       = int(n_t_br)
            if n_coupl > 0: fittings_raw["coupling"]        = int(n_coupl)
            if n_iso   > 0: fittings_raw["valve_isolation"] = int(n_iso)
            if n_bal   > 0: fittings_raw["valve_balancing"] = int(n_bal)

            edge_notes = st.text_input("Notizen (optional)", value="", key="edge_notes")

            if st.button("Rohrsegment hinzufügen", use_container_width=True, type="primary", key="btn_add_edge"):
                new_edge = {
                    "id":       make_edge_id(),
                    "source":   src_id,
                    "target":   tgt_id,
                    "length_m": float(length_m),
                    "fittings": fittings_raw,
                    "props": {
                        "length_m":    float(length_m),
                        "fittings_raw": fittings_raw,
                        "notes":       edge_notes,
                        "dn_sized":    None,
                        "dp_Pa":       None,
                        "flow_lh":     None,
                    },
                }
                st.session_state.edges.append(new_edge)
                st.session_state.calc_results = None
                st.success(f"Rohrsegment {length_m:.1f} m hinzugefügt.")
                st.rerun()

        # List existing edges
        st.markdown("---")
        st.markdown('<div class="section-header">Vorhandene Rohrsegmente</div>', unsafe_allow_html=True)
        node_map_label = {n["id"]: n.get("label", n["id"]) for n in st.session_state.nodes}
        if not st.session_state.edges:
            st.info("Noch keine Verbindungen.")
        else:
            for i, edge in enumerate(list(st.session_state.edges)):
                src_lbl = node_map_label.get(edge.get("source", ""), edge.get("source", ""))
                tgt_lbl = node_map_label.get(edge.get("target", ""), edge.get("target", ""))
                with st.expander(
                    f"{src_lbl} → {tgt_lbl}  {edge.get('length_m', 0):.1f} m  [{edge['id'][:8]}]",
                    expanded=False,
                ):
                    new_len = st.number_input(
                        "Länge [m]",
                        value=float(edge.get("length_m", 1.0)),
                        min_value=0.1, step=0.5,
                        key=f"elen_{edge['id']}",
                    )
                    st.session_state.edges[i]["length_m"] = new_len
                    if "props" in st.session_state.edges[i]:
                        st.session_state.edges[i]["props"]["length_m"] = new_len
                    fit = edge.get("fittings", {})
                    st.caption(f"Formteile: {fit if fit else 'keine'}")

    # -------------------------------------------------------------------------
    elif mode == "Bearbeiten":
        st.markdown('<div class="section-header">Knoten bearbeiten</div>', unsafe_allow_html=True)

        if not st.session_state.nodes:
            st.info("Keine Knoten vorhanden.")
        else:
            node_ids = [n["id"] for n in st.session_state.nodes]
            node_labels_map = {n["id"]: node_id_label(n) for n in st.session_state.nodes}

            sel_id = st.selectbox(
                "Knoten auswählen",
                options=node_ids,
                format_func=lambda k: node_labels_map.get(k, k),
                key="edit_node_sel",
            )
            idx = next((i for i, n in enumerate(st.session_state.nodes) if n["id"] == sel_id), None)
            if idx is not None:
                node = st.session_state.nodes[idx]
                new_label = st.text_input("Bezeichnung", value=node.get("label", ""), key=f"edit_lbl_{sel_id}")

                props = node.get("props", {})
                ntype = node.get("type", "")

                if ntype == "FAN_COIL":
                    new_room = st.text_input("Raumbez.", value=props.get("room", ""), key=f"edit_room_{sel_id}")
                    props["room"] = new_room

                if ntype == "CHILLER":
                    new_pump_head = st.number_input(
                        "Pumpenförderhöhe [kPa]",
                        value=float(props.get("pump_head_kPa", 96.8)),
                        min_value=0.0, max_value=500.0, step=1.0,
                        key=f"edit_pumphead_{sel_id}",
                    )
                    props["pump_head_kPa"] = new_pump_head

                    # Edit buffer/expansion/safety
                    st.markdown("**Ausdehnungsgefäss**")
                    props["expansion_vessel_integrated"] = st.checkbox(
                        "Integriert",
                        value=bool(props.get("expansion_vessel_integrated", False)),
                        key=f"edit_exp_int_{sel_id}",
                    )
                    props["expansion_vessel_L"] = st.number_input(
                        "Volumen [L]",
                        value=float(props.get("expansion_vessel_L", 8.0)),
                        min_value=0.0, step=1.0,
                        key=f"edit_exp_vol_{sel_id}",
                    )
                    st.markdown("**Sicherheitsventil**")
                    props["safety_valve_integrated"] = st.checkbox(
                        "Integriert",
                        value=bool(props.get("safety_valve_integrated", False)),
                        key=f"edit_sv_int_{sel_id}",
                    )
                    props["safety_valve_bar"] = st.number_input(
                        "Ansprechdruck [bar]",
                        value=float(props.get("safety_valve_bar", 3.0)),
                        min_value=0.5, step=0.5,
                        key=f"edit_sv_bar_{sel_id}",
                    )
                    st.markdown("**Pufferspeicher**")
                    props["buffer_tank_integrated"] = st.checkbox(
                        "Integriert",
                        value=bool(props.get("buffer_tank_integrated", False)),
                        key=f"edit_buf_int_{sel_id}",
                    )
                    props["buffer_tank_L"] = st.number_input(
                        "Volumen [L]",
                        value=float(props.get("buffer_tank_L", 0.0)),
                        min_value=0.0, step=5.0,
                        key=f"edit_buf_vol_{sel_id}",
                    )

                if st.button("Änderungen speichern", type="primary", key=f"save_edit_{sel_id}"):
                    st.session_state.nodes[idx]["label"] = new_label
                    st.session_state.nodes[idx]["props"] = props
                    st.session_state.calc_results = None
                    st.success("Gespeichert.")
                    st.rerun()

    # -------------------------------------------------------------------------
    elif mode == "Löschen":
        st.markdown('<div class="section-header">Knoten / Segment löschen</div>', unsafe_allow_html=True)

        st.markdown("**Knoten löschen**")
        if not st.session_state.nodes:
            st.info("Keine Knoten.")
        else:
            node_ids = [n["id"] for n in st.session_state.nodes]
            node_labels_map = {n["id"]: node_id_label(n) for n in st.session_state.nodes}
            del_node_id = st.selectbox(
                "Knoten auswählen",
                options=node_ids,
                format_func=lambda k: node_labels_map.get(k, k),
                key="del_node_sel",
            )
            if st.button("Knoten löschen", type="secondary", key="btn_del_node"):
                st.session_state.nodes = [n for n in st.session_state.nodes if n["id"] != del_node_id]
                st.session_state.edges = [
                    e for e in st.session_state.edges
                    if e["source"] != del_node_id and e["target"] != del_node_id
                ]
                # Remove stored position
                st.session_state.node_positions.pop(del_node_id, None)
                st.session_state.calc_results = None
                st.success("Knoten gelöscht.")
                st.rerun()

        st.markdown("---")
        st.markdown("**Rohrsegment löschen**")
        if not st.session_state.edges:
            st.info("Keine Rohrsegmente.")
        else:
            node_map_label = {n["id"]: n.get("label", n["id"]) for n in st.session_state.nodes}
            edge_ids = [e["id"] for e in st.session_state.edges]

            def fmt_edge(eid):
                e = next((x for x in st.session_state.edges if x["id"] == eid), {})
                src = node_map_label.get(e.get("source", ""), e.get("source", ""))
                tgt = node_map_label.get(e.get("target", ""), e.get("target", ""))
                return f"{src} → {tgt}  {e.get('length_m', 0):.1f}m  [{eid[:6]}]"

            del_edge_id = st.selectbox(
                "Segment auswählen",
                options=edge_ids,
                format_func=fmt_edge,
                key="del_edge_sel",
            )
            if st.button("Segment löschen", type="secondary", key="btn_del_edge"):
                st.session_state.edges = [e for e in st.session_state.edges if e["id"] != del_edge_id]
                st.session_state.calc_results = None
                st.success("Segment gelöscht.")
                st.rerun()

        st.markdown("---")
        if st.button("Gesamtes Netzwerk leeren", type="secondary", key="btn_clear_all"):
            st.session_state.nodes = []
            st.session_state.edges = []
            st.session_state.calc_results = None
            st.session_state.node_positions = {}
            st.rerun()

    # -------------------------------------------------------------------------
    elif mode == "Import/Export":
        st.markdown('<div class="section-header">Netzwerk speichern / laden</div>', unsafe_allow_html=True)

        if st.button("Als JSON exportieren", use_container_width=True, key="btn_export_json"):
            json_str = network_to_json(
                st.session_state.nodes,
                st.session_state.edges,
                st.session_state.system_params,
            )
            st.download_button(
                "JSON herunterladen",
                data=json_str,
                file_name=f"{st.session_state.system_params.get('project_name','network')}.json",
                mime="application/json",
                use_container_width=True,
            )

        st.markdown("---")
        uploaded = st.file_uploader("JSON importieren", type=["json"], key="net_import")
        if uploaded:
            try:
                json_str = uploaded.read().decode("utf-8")
                nodes, edges, sp = network_from_json(json_str)
                st.session_state.nodes = nodes
                st.session_state.edges = edges
                st.session_state.system_params = sp
                st.session_state.calc_results = None
                st.session_state.node_positions = {}
                st.success(f"Netzwerk geladen: {len(nodes)} Knoten, {len(edges)} Segmente.")
                st.rerun()
            except Exception as e:
                st.error(f"Importfehler: {e}")

        st.markdown("---")
        st.markdown('<div class="section-header">Beispielnetzwerk</div>', unsafe_allow_html=True)
        if st.button("Beispielnetzwerk laden", use_container_width=True, key="btn_load_example"):
            n_ch = {
                "id":    make_node_id(),
                "type":  "CHILLER",
                "label": "KM-01",
                "props": {
                    "model":                       "Climaveneta_iBX2_G07_27Y",
                    "pump_head_kPa":               96.8,
                    "pump_integrated":             True,
                    "pump_type":                   "Hocheffizienzpumpe EC",
                    "pump_flow_max_m3h":           5.5,
                    "expansion_vessel_integrated": True,
                    "expansion_vessel_L":          8.0,
                    "safety_valve_integrated":     True,
                    "safety_valve_bar":            3.0,
                    "buffer_tank_integrated":      True,
                    "buffer_tank_L":               60.0,
                },
            }
            n_tj = {
                "id":    make_node_id(),
                "type":  "T_JUNCTION",
                "label": "T-01",
                "props": {},
            }
            n_fc1 = {
                "id":    make_node_id(),
                "type":  "FAN_COIL",
                "label": "GK-01",
                "props": {
                    "model":       "Kampmann_KaCool_W_Size4",
                    "room":        "Büro EG",
                    "cooling_W":   4040,
                    "flow_lh":     696,
                    "dp_kPa":      67.6,
                    "connection":  '½"',
                },
            }
            n_fc2 = {
                "id":    make_node_id(),
                "type":  "FAN_COIL",
                "label": "GK-02",
                "props": {
                    "model":       "Kampmann_KaCool_W_Size2",
                    "room":        "Büro OG",
                    "cooling_W":   2290,
                    "flow_lh":     395,
                    "dp_kPa":      27.0,
                    "connection":  '½"',
                },
            }
            n_fc3 = {
                "id":    make_node_id(),
                "type":  "FAN_COIL",
                "label": "GK-03",
                "props": {
                    "model":       "Kampmann_KaCool_W_Size3",
                    "room":        "Sitzungszimmer",
                    "cooling_W":   3160,
                    "flow_lh":     545,
                    "dp_kPa":      47.5,
                    "connection":  '½"',
                },
            }

            def make_edge(src, tgt, length, **fit):
                return {
                    "id":       make_edge_id(),
                    "source":   src["id"],
                    "target":   tgt["id"],
                    "length_m": length,
                    "fittings": fit if fit else {},
                    "props": {
                        "length_m":     length,
                        "fittings_raw": fit if fit else {},
                        "notes":        "",
                        "dn_sized":     None,
                        "dp_Pa":        None,
                        "flow_lh":      None,
                    },
                }

            e1 = make_edge(n_ch,  n_tj,  5.0, coupling=2)
            e2 = make_edge(n_tj,  n_fc1, 8.0, elbow_90=2, t_branch=1, valve_isolation=2)
            e3 = make_edge(n_tj,  n_fc2, 6.0, elbow_90=1, t_through=1, valve_isolation=2)
            e4 = make_edge(n_tj,  n_fc3, 9.0, elbow_90=2, t_branch=1, valve_isolation=2)

            st.session_state.nodes = [n_ch, n_tj, n_fc1, n_fc2, n_fc3]
            st.session_state.edges = [e1, e2, e3, e4]
            st.session_state.calc_results = None
            st.session_state.node_positions = {}
            st.success("Beispielnetzwerk geladen.")
            st.rerun()


# ── RIGHT PANEL: agraph canvas ───────────────────────────────────────────────
with canvas_col:
    st.markdown("### Netzwerk-Ansicht")
    st.caption("Kältemaschine oben links — Knoten können per Drag-and-Drop verschoben werden.")

    if not st.session_state.nodes:
        st.info(
            "Noch keine Knoten vorhanden. "
            "Fügen Sie links Geräte hinzu — Kältemaschine wird automatisch oben links platziert."
        )
    else:
        ag_nodes, ag_edges = build_agraph(st.session_state.nodes, st.session_state.edges)
        return_value = agraph(nodes=ag_nodes, edges=ag_edges, config=AGRAPH_CONFIG)

        # Store node positions if agraph returns position data
        if return_value and isinstance(return_value, dict):
            positions = return_value.get("nodes", {})
            if positions and isinstance(positions, dict):
                for nid, pos_data in positions.items():
                    if isinstance(pos_data, dict) and "x" in pos_data:
                        st.session_state.node_positions[nid] = {
                            "x": pos_data["x"],
                            "y": pos_data["y"],
                        }

    # Node summary table
    if st.session_state.nodes:
        import pandas as pd
        st.markdown("#### Knotenübersicht")
        node_rows = []
        for n in st.session_state.nodes:
            type_label = NODE_TYPES.get(n.get("type", ""), {}).get("label", n.get("type", ""))
            props = n.get("props", {})
            model_str = props.get("model", n.get("model", ""))
            if model_str == "custom":
                model_str = f"[Benutzerdef.] {props.get('model_name', props.get('manufacturer', ''))}"
            room_str = props.get("room", n.get("room", ""))
            buf_str = ""
            if n.get("type") == "CHILLER":
                parts = []
                if props.get("buffer_tank_integrated"):
                    parts.append(f"Puffer {props.get('buffer_tank_L',0):.0f}L")
                if props.get("expansion_vessel_integrated"):
                    parts.append(f"AG {props.get('expansion_vessel_L',0):.0f}L")
                if props.get("safety_valve_integrated"):
                    parts.append(f"SV {props.get('safety_valve_bar',3):.1f}bar")
                buf_str = ", ".join(parts)
            node_rows.append({
                "ID":          n["id"][:8],
                "Typ":         type_label,
                "Bezeichnung": n.get("label", ""),
                "Modell/Info": model_str,
                "Raum":        room_str,
                "Integriert":  buf_str,
            })
        df_nodes = pd.DataFrame(node_rows)
        st.dataframe(df_nodes, use_container_width=True, hide_index=True)

    if st.session_state.edges:
        import pandas as pd
        st.markdown("#### Rohrsegmentübersicht")
        node_map_lbl = {n["id"]: n.get("label", n["id"]) for n in st.session_state.nodes}
        edge_rows = []
        for e in st.session_state.edges:
            props = e.get("props", {})
            fit_src = e.get("fittings", props.get("fittings_raw", {}))
            fit_str = ", ".join(f"{k}:{v}" for k, v in fit_src.items()) if fit_src else "—"
            dn = props.get("dn_sized")
            edge_rows.append({
                "ID":            e["id"][:8],
                "Von":           node_map_lbl.get(e["source"], e["source"]),
                "Nach":          node_map_lbl.get(e["target"], e["target"]),
                "Länge [m]":     e.get("length_m", 0),
                "Formteile":     fit_str,
                "DN (berechn.)": f"DN{dn}" if dn else "—",
            })
        df_edges = pd.DataFrame(edge_rows)
        st.dataframe(df_edges, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.page_link(
        "pages/2_📊_Hydraulic_Calculation.py",
        label="Weiter zur Hydraulikberechnung",
        icon="📊",
    )
