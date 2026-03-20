"""
Bibliothek — Seite 5
Geräte-Bibliothek verwalten: Aussengeräte, Innengeräte, Import/Export.
"""

import streamlit as st
import json
import uuid
import pandas as pd
from typing import Dict, List, Any

from utils.helpers import init_session_state, library_to_json, library_from_json
from data.component_library import CHILLERS, FAN_COILS, get_chiller, get_fan_coil

# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Bibliothek | Kaltwasser Designer",
    layout="wide",
    page_icon="📚",
)
init_session_state(st)

import os as _os
_logo_p = _os.path.join(_os.path.dirname(__file__), "..", "static", "imwinkelried_logo.png")
if _os.path.exists(_logo_p):
    st.logo(_logo_p, size="large", link="https://www.imwinkelried.ch")

st.markdown("""
<style>
.lib-header {
    font-size: 1.05rem; font-weight: 700; color: #1565C0;
    border-bottom: 2px solid #1565C0; padding-bottom: 4px; margin-bottom: 12px;
}
.lib-card {
    background: #f0f4f8; border: 1px solid #c8d6e8; border-radius: 6px;
    padding: 10px 14px; margin-bottom: 8px;
}
.readonly-badge {
    display: inline-block; background: #e3f2fd; color: #1565C0;
    padding: 2px 7px; border-radius: 3px; font-size: 0.8rem; font-weight: 600;
}
.custom-badge {
    display: inline-block; background: #e8f5e9; color: #2e7d32;
    padding: 2px 7px; border-radius: 3px; font-size: 0.8rem; font-weight: 600;
}
</style>
""", unsafe_allow_html=True)

st.markdown("# 📚 Geräte-Bibliothek")
st.markdown(
    "Verwalten Sie die Geräte-Bibliothek: Aussengeräte (Kältemaschinen) und "
    "Innengeräte (Gebläsekonvektoren). Werksbibliothek (read-only) + benutzerdefinierte Geräte."
)

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab1, tab2, tab3 = st.tabs(["🏭 Aussengeräte", "🌀 Innengeräte", "📥 Import/Export"])

# ============================================================================
# TAB 1: Aussengeräte (Chillers)
# ============================================================================
with tab1:
    st.markdown("## Aussengeräte (Kältemaschinen)")

    # --- Library devices ---
    st.markdown('<div class="lib-header">Werksbibliothek <span class="readonly-badge">Nur lesen</span></div>', unsafe_allow_html=True)

    lib_ch_rows = []
    for key, ch in CHILLERS.items():
        lib_ch_rows.append({
            "Schlüssel":        key,
            "Hersteller":       ch.get("manufacturer", "—"),
            "Modell":           ch.get("model", "—"),
            "Kälteleistung [kW]": ch.get("cooling_capacity_kW", "—"),
            "EER":              ch.get("eer", "—"),
            "Kältemittel":      ch.get("refrigerant", "—"),
            "Pumpe":            "Ja" if ch.get("pump_integrated") else "Nein",
            "Pumpenhöhe [kPa]": ch.get("pump_head_kPa", "—"),
            "Pufferspeicher":   f"{ch.get('buffer_tank_L','—')} L" if ch.get("buffer_tank_integrated") else "extern",
            "Artikelnummer":    ch.get("article", "—"),
        })

    df_lib_ch = pd.DataFrame(lib_ch_rows)
    st.dataframe(df_lib_ch, use_container_width=True, hide_index=True)

    # Clone to custom
    st.markdown("**Gerät klonen und benutzerdefiniert anpassen:**")
    clone_key = st.selectbox(
        "Gerät zum Klonen auswählen",
        options=list(CHILLERS.keys()),
        format_func=lambda k: f"{CHILLERS[k]['manufacturer']} {CHILLERS[k]['model']}",
        key="clone_ch_sel",
    )
    if st.button("In benutzerdefinierte Bibliothek klonen", key="btn_clone_ch"):
        src = get_chiller(clone_key)
        new_custom = dict(src)
        new_custom["_key"]       = uuid.uuid4().hex[:8]
        new_custom["model"]      = "custom"
        new_custom["model_name"] = f"{src['model']} (Kopie)"
        new_custom["manufacturer"] = src.get("manufacturer", "")
        st.session_state.custom_chillers.append(new_custom)
        st.success(f"'{src['model']}' wurde in die benutzerdefinierte Bibliothek geklont.")
        st.rerun()

    st.markdown("---")

    # --- Custom devices ---
    st.markdown('<div class="lib-header">Benutzerdefinierte Aussengeräte <span class="custom-badge">Benutzerdef.</span></div>', unsafe_allow_html=True)

    custom_ch = st.session_state.get("custom_chillers", [])

    if not custom_ch:
        st.info("Keine benutzerdefinierten Aussengeräte vorhanden. Neue Geräte im Netzwerk-Editor erstellen oder aus der Werksbibliothek klonen.")
    else:
        # Build display dataframe for data_editor
        custom_ch_rows = []
        for c in custom_ch:
            custom_ch_rows.append({
                "_key":             c.get("_key", ""),
                "Hersteller":       c.get("manufacturer", ""),
                "Modell":           c.get("model_name", c.get("model", "")),
                "Kälteleistung [kW]": c.get("cooling_capacity_kW", ""),
                "EER":              c.get("eer", ""),
                "Kältemittel":      c.get("refrigerant", ""),
                "Pumpe integriert": c.get("pump_integrated", False),
                "Pumpenhöhe [kPa]": c.get("pump_head_kPa", ""),
                "Pufferspeicher [L]": c.get("buffer_tank_L", 0),
                "Puffer integriert": c.get("buffer_tank_integrated", False),
                "Notizen":          c.get("notes", ""),
            })

        df_custom_ch = pd.DataFrame(custom_ch_rows)

        # Show editable dataframe (hide _key column)
        edit_cols = [c for c in df_custom_ch.columns if c != "_key"]
        st.markdown("**Inline bearbeiten:**")
        edited_df = st.data_editor(
            df_custom_ch[edit_cols],
            use_container_width=True,
            hide_index=True,
            key="edit_custom_ch",
            num_rows="fixed",
        )

        if st.button("Änderungen übernehmen", key="btn_save_custom_ch", type="primary"):
            # Apply edits back to session state
            for i, row in edited_df.iterrows():
                if i < len(st.session_state.custom_chillers):
                    for col in edit_cols:
                        field_map = {
                            "Hersteller":         "manufacturer",
                            "Modell":             "model_name",
                            "Kälteleistung [kW]": "cooling_capacity_kW",
                            "EER":                "eer",
                            "Kältemittel":        "refrigerant",
                            "Pumpe integriert":   "pump_integrated",
                            "Pumpenhöhe [kPa]":   "pump_head_kPa",
                            "Pufferspeicher [L]": "buffer_tank_L",
                            "Puffer integriert":  "buffer_tank_integrated",
                            "Notizen":            "notes",
                        }
                        if col in field_map:
                            st.session_state.custom_chillers[i][field_map[col]] = row[col]
            st.success("Änderungen gespeichert.")
            st.rerun()

        # Delete button per device
        st.markdown("**Gerät löschen:**")
        keys_ch = [c.get("_key", str(i)) for i, c in enumerate(custom_ch)]
        labels_ch = [f"{c.get('manufacturer','')} {c.get('model_name','?')}" for c in custom_ch]
        del_ch_idx = st.selectbox(
            "Zu löschendes Gerät",
            options=range(len(custom_ch)),
            format_func=lambda i: labels_ch[i] if i < len(labels_ch) else str(i),
            key="del_ch_idx",
        )
        if st.button("Aussengerät löschen", type="secondary", key="btn_del_custom_ch"):
            st.session_state.custom_chillers.pop(del_ch_idx)
            st.success("Gerät gelöscht.")
            st.rerun()

    # --- Add new custom chiller ---
    st.markdown("---")
    st.markdown('<div class="lib-header">Neues Aussengerät erstellen</div>', unsafe_allow_html=True)

    with st.expander("Neues benutzerdefiniertes Aussengerät", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            new_ch_manu   = st.text_input("Hersteller", key="new_ch_manu")
            new_ch_model  = st.text_input("Modell", key="new_ch_model")
            new_ch_kw     = st.number_input("Kälteleistung [kW]", value=10.0, key="new_ch_kw")
            new_ch_eer    = st.number_input("EER", value=3.0, key="new_ch_eer")
            new_ch_kalt   = st.text_input("Kältemittel", value="R32", key="new_ch_kalt")
        with c2:
            new_ch_pump_h = st.number_input("Pumpenförderhöhe [kPa]", value=80.0, key="new_ch_pump_h")
            new_ch_pump_i = st.checkbox("Pumpe integriert", value=True, key="new_ch_pump_i")
            new_ch_buf_i  = st.checkbox("Pufferspeicher integriert", value=False, key="new_ch_buf_i")
            new_ch_buf_l  = st.number_input("Pufferspeicher Volumen [L]", value=0.0, key="new_ch_buf_l")
            new_ch_note   = st.text_area("Notizen", key="new_ch_note")

        if st.button("Aussengerät zur Bibliothek hinzufügen", type="primary", key="btn_add_ch_lib"):
            new_entry = {
                "_key":                   uuid.uuid4().hex[:8],
                "model":                  "custom",
                "manufacturer":           new_ch_manu,
                "model_name":             new_ch_model,
                "cooling_capacity_kW":    new_ch_kw,
                "eer":                    new_ch_eer,
                "refrigerant":            new_ch_kalt,
                "pump_head_kPa":          new_ch_pump_h,
                "pump_integrated":        new_ch_pump_i,
                "buffer_tank_integrated": new_ch_buf_i,
                "buffer_tank_L":          new_ch_buf_l,
                "notes":                  new_ch_note,
            }
            st.session_state.custom_chillers.append(new_entry)
            st.success(f"'{new_ch_model}' zur Bibliothek hinzugefügt.")
            st.rerun()


# ============================================================================
# TAB 2: Innengeräte (Fan Coils)
# ============================================================================
with tab2:
    st.markdown("## Innengeräte (Gebläsekonvektoren)")

    # --- Library devices ---
    st.markdown('<div class="lib-header">Werksbibliothek <span class="readonly-badge">Nur lesen</span></div>', unsafe_allow_html=True)

    lib_fc_rows = []
    for key, fc in FAN_COILS.items():
        perf10 = fc["performance"].get(10, {})
        lib_fc_rows.append({
            "Schlüssel":            key,
            "Hersteller":           fc.get("manufacturer", "—"),
            "Modell":               fc.get("model", "—"),
            "Artikelnummer":        fc.get("article", "—"),
            "Kühlleistung 10V [W]": perf10.get("cooling_total_W", "—"),
            "Luftmenge 10V [m³/h]": perf10.get("airflow_m3h", "—"),
            "Schall 10V [dB(A)]":   perf10.get("sound_dBa", "—"),
            "Wasserfluss [l/h]":    fc.get("water_flow_lh", "—"),
            "Druckverlust [kPa]":   fc.get("water_resistance_kPa", "—"),
            "Wasservolumen [L]":    fc.get("water_volume_L", fc.get("water_content_L", "—")),
            "Anschluss":            fc.get("connection_supply", "—"),
        })

    df_lib_fc = pd.DataFrame(lib_fc_rows)
    st.dataframe(df_lib_fc, use_container_width=True, hide_index=True)

    # Clone to custom
    st.markdown("**Gerät klonen und benutzerdefiniert anpassen:**")
    clone_fc_key = st.selectbox(
        "Gerät zum Klonen auswählen",
        options=list(FAN_COILS.keys()),
        format_func=lambda k: f"{FAN_COILS[k]['manufacturer']} {FAN_COILS[k]['model']}",
        key="clone_fc_sel",
    )
    if st.button("In benutzerdefinierte Bibliothek klonen", key="btn_clone_fc"):
        src_fc = get_fan_coil(clone_fc_key)
        perf10_src = src_fc["performance"].get(10, {})
        new_fc_custom = {
            "_key":         uuid.uuid4().hex[:8],
            "model":        "custom",
            "manufacturer": src_fc.get("manufacturer", ""),
            "model_name":   f"{src_fc['model']} (Kopie)",
            "cooling_W":    perf10_src.get("cooling_total_W", 2000),
            "flow_lh":      src_fc.get("water_flow_lh", 300),
            "dp_kPa":       src_fc.get("water_resistance_kPa", 20),
            "connection":   src_fc.get("connection_supply", '½"'),
            "water_volume_L": src_fc.get("water_volume_L", src_fc.get("water_content_L", 1.0)),
            "notes":        "",
        }
        st.session_state.custom_fan_coils.append(new_fc_custom)
        st.success(f"'{src_fc['model']}' wurde in die benutzerdefinierte Bibliothek geklont.")
        st.rerun()

    st.markdown("---")

    # --- Custom devices ---
    st.markdown('<div class="lib-header">Benutzerdefinierte Innengeräte <span class="custom-badge">Benutzerdef.</span></div>', unsafe_allow_html=True)

    custom_fc = st.session_state.get("custom_fan_coils", [])

    if not custom_fc:
        st.info("Keine benutzerdefinierten Innengeräte vorhanden. Neue Geräte im Netzwerk-Editor erstellen oder aus der Werksbibliothek klonen.")
    else:
        custom_fc_rows = []
        for c in custom_fc:
            custom_fc_rows.append({
                "_key":             c.get("_key", ""),
                "Hersteller":       c.get("manufacturer", ""),
                "Modell":           c.get("model_name", ""),
                "Kühlleistung [W]": c.get("cooling_W", ""),
                "Volumenstrom [l/h]": c.get("flow_lh", ""),
                "Druckverlust [kPa]": c.get("dp_kPa", ""),
                "Anschluss":        c.get("connection", '½"'),
                "Wasservolumen [L]": c.get("water_volume_L", 1.0),
                "Notizen":          c.get("notes", ""),
            })

        df_custom_fc = pd.DataFrame(custom_fc_rows)
        edit_fc_cols = [c for c in df_custom_fc.columns if c != "_key"]

        st.markdown("**Inline bearbeiten:**")
        edited_fc_df = st.data_editor(
            df_custom_fc[edit_fc_cols],
            use_container_width=True,
            hide_index=True,
            key="edit_custom_fc",
            num_rows="fixed",
        )

        if st.button("Änderungen übernehmen", key="btn_save_custom_fc", type="primary"):
            for i, row in edited_fc_df.iterrows():
                if i < len(st.session_state.custom_fan_coils):
                    fc_field_map = {
                        "Hersteller":           "manufacturer",
                        "Modell":               "model_name",
                        "Kühlleistung [W]":     "cooling_W",
                        "Volumenstrom [l/h]":   "flow_lh",
                        "Druckverlust [kPa]":   "dp_kPa",
                        "Anschluss":            "connection",
                        "Wasservolumen [L]":    "water_volume_L",
                        "Notizen":              "notes",
                    }
                    for col in edit_fc_cols:
                        if col in fc_field_map:
                            st.session_state.custom_fan_coils[i][fc_field_map[col]] = row[col]
            st.success("Änderungen gespeichert.")
            st.rerun()

        # Delete
        st.markdown("**Gerät löschen:**")
        labels_fc = [f"{c.get('manufacturer','')} {c.get('model_name','?')}" for c in custom_fc]
        del_fc_idx = st.selectbox(
            "Zu löschendes Gerät",
            options=range(len(custom_fc)),
            format_func=lambda i: labels_fc[i] if i < len(labels_fc) else str(i),
            key="del_fc_idx",
        )
        if st.button("Innengerät löschen", type="secondary", key="btn_del_custom_fc"):
            st.session_state.custom_fan_coils.pop(del_fc_idx)
            st.success("Gerät gelöscht.")
            st.rerun()

    # --- Add new custom fan coil ---
    st.markdown("---")
    st.markdown('<div class="lib-header">Neues Innengerät erstellen</div>', unsafe_allow_html=True)

    with st.expander("Neues benutzerdefiniertes Innengerät", expanded=False):
        fc1, fc2 = st.columns(2)
        with fc1:
            new_fc_manu    = st.text_input("Hersteller", key="new_fc_manu")
            new_fc_model   = st.text_input("Modell", key="new_fc_model")
            new_fc_kw      = st.number_input("Kühlleistung [W]", value=2000, min_value=100, key="new_fc_kw")
            new_fc_flow    = st.number_input("Volumenstrom [l/h]", value=300, min_value=10, key="new_fc_flow")
        with fc2:
            new_fc_dp      = st.number_input("Druckverlust [kPa]", value=20.0, key="new_fc_dp")
            new_fc_conn    = st.text_input("Anschluss", value='½"', key="new_fc_conn")
            new_fc_wvol    = st.number_input("Wasservolumen [L]", value=1.0, min_value=0.1, key="new_fc_wvol")
            new_fc_note    = st.text_area("Notizen", key="new_fc_note")

        if st.button("Innengerät zur Bibliothek hinzufügen", type="primary", key="btn_add_fc_lib"):
            new_fc_entry = {
                "_key":          uuid.uuid4().hex[:8],
                "model":         "custom",
                "manufacturer":  new_fc_manu,
                "model_name":    new_fc_model,
                "cooling_W":     new_fc_kw,
                "flow_lh":       new_fc_flow,
                "dp_kPa":        new_fc_dp,
                "connection":    new_fc_conn,
                "water_volume_L": new_fc_wvol,
                "notes":         new_fc_note,
            }
            st.session_state.custom_fan_coils.append(new_fc_entry)
            st.success(f"'{new_fc_model}' zur Bibliothek hinzugefügt.")
            st.rerun()


# ============================================================================
# TAB 3: Import/Export
# ============================================================================
with tab3:
    st.markdown("## Import / Export der Bibliothek")
    st.markdown("Exportieren Sie Ihre benutzerdefinierten Geräte als JSON für die Weitergabe oder importieren Sie eine gespeicherte Bibliothek.")

    col_exp, col_imp = st.columns(2)

    with col_exp:
        st.markdown("### Export")
        n_ch_custom = len(st.session_state.get("custom_chillers", []))
        n_fc_custom = len(st.session_state.get("custom_fan_coils", []))
        st.info(f"Aktuell in der Bibliothek: {n_ch_custom} benutzerdefinierte Aussengeräte, {n_fc_custom} Innengeräte")

        if st.button("Bibliothek als JSON exportieren", use_container_width=True, type="primary", key="btn_export_lib"):
            json_str = library_to_json(
                st.session_state.get("custom_chillers", []),
                st.session_state.get("custom_fan_coils", []),
            )
            st.download_button(
                "JSON herunterladen",
                data=json_str,
                file_name="kaltwasser_bibliothek.json",
                mime="application/json",
                use_container_width=True,
                key="dl_lib_json",
            )

        st.markdown("---")
        st.markdown("### Gesamtes Netzwerk + Bibliothek exportieren")
        from utils.helpers import network_to_json
        if st.button("Netzwerk + Bibliothek exportieren", use_container_width=True, key="btn_export_all"):
            full_data = {
                "nodes": st.session_state.nodes,
                "edges": st.session_state.edges,
                "system_params": st.session_state.system_params,
                "custom_chillers": st.session_state.get("custom_chillers", []),
                "custom_fan_coils": st.session_state.get("custom_fan_coils", []),
            }
            full_json = json.dumps(full_data, indent=2, ensure_ascii=False)
            project_name = st.session_state.system_params.get("project_name", "Projekt").replace(" ", "_")
            st.download_button(
                "Vollständige Datei herunterladen",
                data=full_json,
                file_name=f"{project_name}_komplett.json",
                mime="application/json",
                use_container_width=True,
                key="dl_full_json",
            )

    with col_imp:
        st.markdown("### Import")
        st.markdown("Laden Sie eine zuvor exportierte Bibliothek oder ein vollständiges Projekt:")

        uploaded_lib = st.file_uploader(
            "JSON-Datei hochladen",
            type=["json"],
            key="lib_import",
            help="Bibliotheks-JSON oder vollständige Projektdatei",
        )

        if uploaded_lib:
            try:
                raw = uploaded_lib.read().decode("utf-8")
                data = json.loads(raw)

                if "custom_chillers" in data or "custom_fan_coils" in data:
                    n_ch_imp = len(data.get("custom_chillers", []))
                    n_fc_imp = len(data.get("custom_fan_coils", []))
                    st.info(f"Gefunden: {n_ch_imp} Aussengeräte, {n_fc_imp} Innengeräte")

                    import_mode = st.radio(
                        "Importmodus",
                        options=["Zusammenführen (Geräte hinzufügen)", "Ersetzen (bestehende Bibliothek überschreiben)"],
                        key="lib_import_mode",
                    )

                    col_a, col_b = st.columns(2)
                    with col_a:
                        if st.button("Bibliothek importieren", type="primary", key="btn_do_import_lib"):
                            if "Ersetzen" in import_mode:
                                st.session_state.custom_chillers  = data.get("custom_chillers", [])
                                st.session_state.custom_fan_coils = data.get("custom_fan_coils", [])
                            else:
                                # Merge — avoid duplicates by _key
                                existing_ch_keys = {c.get("_key") for c in st.session_state.custom_chillers}
                                existing_fc_keys = {c.get("_key") for c in st.session_state.custom_fan_coils}
                                for c in data.get("custom_chillers", []):
                                    if c.get("_key") not in existing_ch_keys:
                                        st.session_state.custom_chillers.append(c)
                                for c in data.get("custom_fan_coils", []):
                                    if c.get("_key") not in existing_fc_keys:
                                        st.session_state.custom_fan_coils.append(c)

                            # Also import network if present
                            if "nodes" in data:
                                st.session_state.nodes = data["nodes"]
                                st.session_state.edges = data["edges"]
                                st.session_state.system_params = data.get("system_params", st.session_state.system_params)
                                st.session_state.calc_results = None
                                st.success(
                                    f"Bibliothek und Netzwerk importiert. "
                                    f"Netzwerk: {len(data['nodes'])} Knoten, {len(data['edges'])} Segmente."
                                )
                            else:
                                st.success("Bibliothek importiert.")
                            st.rerun()

                    with col_b:
                        if st.button("Abbrechen", key="btn_cancel_import"):
                            st.rerun()
                else:
                    st.warning("Die hochgeladene Datei enthält keine Bibliotheksdaten (custom_chillers / custom_fan_coils).")

            except Exception as e:
                st.error(f"Importfehler: {e}")

    st.markdown("---")
    st.markdown("### Bibliothek zurücksetzen")
    col_rst1, col_rst2 = st.columns(2)
    with col_rst1:
        if st.button("Benutzerdefinierte Aussengeräte löschen", type="secondary", key="btn_reset_ch"):
            st.session_state.custom_chillers = []
            st.success("Benutzerdefinierte Aussengeräte gelöscht.")
            st.rerun()
    with col_rst2:
        if st.button("Benutzerdefinierte Innengeräte löschen", type="secondary", key="btn_reset_fc"):
            st.session_state.custom_fan_coils = []
            st.success("Benutzerdefinierte Innengeräte gelöscht.")
            st.rerun()
