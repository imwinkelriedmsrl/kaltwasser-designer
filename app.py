"""
Kaltwasser Designer — Hauptanwendung
=====================================
Streamlit multi-page app for chilled water system design.

Run with:
    streamlit run app.py
"""

import streamlit as st
from utils.helpers import init_session_state, DEFAULT_SYSTEM_PARAMS, project_to_json, project_from_json

# ---------------------------------------------------------------------------
# Page configuration (must be first Streamlit call)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Kaltwasser Designer",
    page_icon="❄️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Initialise session state
# ---------------------------------------------------------------------------
init_session_state(st)

# ---------------------------------------------------------------------------
# Logo (sidebar top)
# ---------------------------------------------------------------------------
import os
_logo_path = os.path.join(os.path.dirname(__file__), "static", "imwinkelried_logo.png")
if os.path.exists(_logo_path):
    st.logo(_logo_path, size="large", link="https://www.imwinkelried.ch")

# ---------------------------------------------------------------------------
# Custom CSS — engineering style
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    .main .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
    }

    section[data-testid="stSidebar"] {
        background-color: #1a2332;
        color: #e0e6f0;
    }
    section[data-testid="stSidebar"] .stMarkdown,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] .stSelectbox label,
    section[data-testid="stSidebar"] .stNumberInput label,
    section[data-testid="stSidebar"] .stTextInput label {
        color: #c8d6e8 !important;
    }
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3 {
        color: #7eb8f7 !important;
    }

    [data-testid="metric-container"] {
        background: #f0f4f8;
        border: 1px solid #d0dde8;
        border-radius: 8px;
        padding: 12px 16px;
    }

    .badge-ok {
        background: #d4edda; color: #155724;
        border: 1px solid #c3e6cb; border-radius: 4px;
        padding: 4px 10px; font-weight: 600; display: inline-block;
    }
    .badge-warn {
        background: #fff3cd; color: #856404;
        border: 1px solid #ffc107; border-radius: 4px;
        padding: 4px 10px; font-weight: 600; display: inline-block;
    }
    .badge-err {
        background: #f8d7da; color: #721c24;
        border: 1px solid #f5c6cb; border-radius: 4px;
        padding: 4px 10px; font-weight: 600; display: inline-block;
    }

    thead tr th {
        background-color: #1a2332 !important;
        color: white !important;
    }

    .app-header {
        background: linear-gradient(135deg, #1565C0 0%, #0D47A1 100%);
        color: white;
        padding: 16px 24px;
        border-radius: 10px;
        margin-bottom: 20px;
    }
    .app-header h1 { color: white; margin: 0; font-size: 1.8rem; }
    .app-header p  { color: #bbdefb; margin: 4px 0 0 0; font-size: 0.95rem; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Sidebar — project info and system parameters
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## ❄️ Kaltwasser Designer")
    st.markdown("---")

    st.markdown("### Projektinfo")
    sp = st.session_state.system_params

    sp["project_name"]   = st.text_input("Projektname",   value=sp.get("project_name",   "Kaltwasserprojekt"))
    sp["project_number"] = st.text_input("Projektnummer", value=sp.get("project_number", ""))
    sp["engineer"]       = st.text_input("Ingenieur",     value=sp.get("engineer",       ""))

    st.markdown("---")
    st.markdown("### Systemparameter")

    col1, col2 = st.columns(2)
    with col1:
        sp["t_supply_C"] = st.number_input(
            "VL-Temp. [°C]", value=float(sp.get("t_supply_C", 7.0)),
            min_value=2.0, max_value=15.0, step=0.5,
        )
    with col2:
        sp["t_return_C"] = st.number_input(
            "RL-Temp. [°C]", value=float(sp.get("t_return_C", 12.0)),
            min_value=5.0, max_value=20.0, step=0.5,
        )

    sp["delta_t_K"] = sp["t_return_C"] - sp["t_supply_C"]
    st.caption(f"ΔT = {sp['delta_t_K']:.1f} K")

    sp["glycol_type"] = st.selectbox(
        "Glykolart",
        options=["Ethylenglykol", "Propylenglykol"],
        index=0 if sp.get("glycol_type", "Ethylenglykol") == "Ethylenglykol" else 1,
    )
    sp["glycol_pct"] = st.slider(
        "Glykolkonzentration [%]",
        min_value=0, max_value=50, step=5,
        value=int(sp.get("glycol_pct", 30)),
    )

    from utils.helpers import check_frosting
    frost = check_frosting(sp["t_supply_C"], sp["glycol_type"], sp["glycol_pct"])
    fp = frost["freeze_point_C"]
    if frost["safe"]:
        st.success(f"Gefrierpunkt: {fp:.1f} °C  (+{frost['safety_margin_K']:.1f} K Sicherheit)")
    else:
        st.error(f"Gefrierpunkt {fp:.1f} °C — Frostschutz unzureichend!")

    st.markdown("---")
    st.markdown("### Rohrgeschwindigkeiten")
    v_main = st.number_input(
        "Max. Stammleitung [m/s]",
        value=float(sp.get("v_max_main_ms", 1.5)),
        min_value=0.3, max_value=3.0, step=0.1,
        key="sidebar_v_main",
    )
    v_branch = st.number_input(
        "Max. Abzweigleitung [m/s]",
        value=float(sp.get("v_max_branch_ms", 0.7)),
        min_value=0.3, max_value=2.0, step=0.1,
        key="sidebar_v_branch",
    )
    sp["v_max_main_ms"]   = v_main
    sp["v_max_branch_ms"] = v_branch

    st.markdown("---")
    st.markdown("### Auslegungsbedingungen")
    sp["t_ambient_design_C"] = st.number_input(
        "Aussentemp. Auslegung [°C]",
        value=float(sp.get("t_ambient_design_C", 32.0)),
        min_value=-10.0, max_value=50.0, step=1.0,
    )
    sp["altitude_m"] = st.number_input(
        "Höhenlage [m ü.M.]",
        value=int(sp.get("altitude_m", 400)),
        min_value=0, max_value=3000, step=50,
    )

    st.markdown("---")
    n_nodes = len(st.session_state.nodes)
    n_edges = len(st.session_state.edges)
    n_fc    = sum(1 for n in st.session_state.nodes if n.get("type") == "FAN_COIL")
    n_ch    = sum(1 for n in st.session_state.nodes if n.get("type") == "CHILLER")

    st.markdown("### Netzwerk-Status")
    st.markdown(f"""
- **Knoten:** {n_nodes} ({n_ch}× Kältemaschine, {n_fc}× GK)
- **Rohrsegmente:** {n_edges}
- **Berechnungsstatus:** {'Berechnet' if st.session_state.calc_results else 'Nicht berechnet'}
    """)

    st.session_state.system_params = sp

    # -----------------------------------------------------------------------
    # Projekt Speichern / Öffnen
    # -----------------------------------------------------------------------
    st.markdown("---")
    st.markdown("### 💾 Projekt")

    proj_name = sp.get("project_name", "Kaltwasserprojekt").replace(" ", "_")
    proj_json = project_to_json(st)
    st.download_button(
        label="📥 Projekt speichern (.json)",
        data=proj_json.encode("utf-8"),
        file_name=f"{proj_name}.json",
        mime="application/json",
        use_container_width=True,
    )

    uploaded = st.file_uploader(
        "📂 Projekt öffnen",
        type=["json"],
        key="proj_upload",
        label_visibility="collapsed",
        help="Kaltwasser Designer Projektdatei (.json) laden",
    )
    if uploaded is not None:
        try:
            project_from_json(uploaded.read().decode("utf-8"), st)
            st.success("Projekt geladen — Seite wird neu geladen …")
            st.rerun()
        except Exception as e:
            st.error(f"Fehler beim Laden: {e}")

    # Imwinkelried logo and link at the bottom of sidebar
    st.markdown("---")
    st.markdown(
        '<div style="text-align:center; padding:6px;">'
        '<small><a href="https://www.imwinkelried.ch" target="_blank" style="color:#7eb8f7;">imwinkelried.ch</a></small>'
        '</div>',
        unsafe_allow_html=True
    )

# ---------------------------------------------------------------------------
# Main page content
# ---------------------------------------------------------------------------
st.markdown("""
<div class="app-header">
  <h1>❄️ Kaltwasser Designer</h1>
  <p>Planungs- und Berechnungswerkzeug für Kaltwassersysteme mit Geberit FlowFit</p>
</div>
""", unsafe_allow_html=True)

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.page_link("pages/1_🔧_Network_Editor.py",         label="**Netzwerk-Editor**",    icon="🔧")
    st.caption("Rohrnetz zeichnen, Geräte konfigurieren")

with col2:
    st.page_link("pages/2_📊_Hydraulic_Calculation.py",  label="**Hydraulikberechnung**", icon="📊")
    st.caption("Durchflüsse, Druckverluste, Rohrdimensionierung")

with col3:
    st.page_link("pages/3_📋_Material_List.py",          label="**Materialliste**",       icon="📋")
    st.caption("Stückliste (BOM), Excel-Export")

with col4:
    st.page_link("pages/4_📈_Technical_Report.py",       label="**Technischer Bericht**", icon="📈")
    st.caption("Systemzusammenfassung, Ausdruck")

col5, col6 = st.columns(2)
with col5:
    st.page_link("pages/5_📚_Bibliothek.py",             label="**Bibliothek**",          icon="📚")
    st.caption("Geräte-Bibliothek verwalten, Import/Export")

with col6:
    st.page_link("pages/6_🏠_Loxone_Steuerung.py",       label="**Loxone Steuerung**",    icon="🏠")
    st.caption("Gebäudeautomation mit Loxone konfigurieren")

st.markdown("---")

st.markdown("## Schnellstart")

c1, c2 = st.columns([2, 1])
with c1:
    st.markdown("""
### Arbeitsschritte

1. **Netzwerk-Editor** öffnen — Kältemaschine und Gebläsekonvektoren hinzufügen
2. Geräte mit Rohrsegmenten verbinden (Längen und Formteile eingeben)
3. **Hydraulikberechnung** ausführen — automatische Rohrdimensionierung
4. **Materialliste** prüfen und als Excel exportieren
5. **Technischen Bericht** für die Dokumentation generieren
6. **Loxone Steuerung** für die Gebäudeautomation konfigurieren

### Systemauslegung

| Parameter | Wert |
|-----------|------|
| Vorlauftemperatur | 7 °C |
| Rücklauftemperatur | 12 °C |
| Temperaturdifferenz | 5 K |
| Rohrsystem | Geberit FlowFit (Ø20–Ø75) |
| Max. Geschwindigkeit (Hauptleitung) | 1.5 m/s (einstellbar) |
| Max. Geschwindigkeit (Stichleitung) | 0.7 m/s (einstellbar) |
| Max. spez. Druckverlust | 150 Pa/m |
    """)

with c2:
    st.markdown("### Verfügbare Geräte")

    st.markdown("**Aussengeräte (Kältemaschinen)**")
    st.info("""
**Climaveneta i-BX2-G07 27Y**
- Kälteleistung: 27.2 kW
- EER: 3.22
- Kältemittel: R32
- Pumpe integriert: 96.8 kPa
- Pufferspeicher 60 L integriert
- Ausdehnungsgefäss 8 L integriert
    """)

    st.markdown("**Innengeräte (Gebläsekonvektoren)**")
    st.success("""
**Kampmann KaCool W — 4 Grössen**
- Gr. 1: 1690 W / 291 l/h / 15.2 kPa
- Gr. 2: 2290 W / 395 l/h / 27.0 kPa
- Gr. 3: 3160 W / 545 l/h / 47.5 kPa
- Gr. 4: 4040 W / 696 l/h / 67.6 kPa
- Anschluss ½", Steuerung 0–10V
    """)

    st.markdown("**Rohrleitungssystem**")
    st.warning("""
**Geberit FlowFit**
- Ø20 bis Ø75 mm (DN16 entfernt)
- 30% / 40% Ethylenglykol
- Artikelnummern im Katalog
    """)

st.markdown("---")
st.markdown("""
<small style="color: #888;">
Kaltwasser Designer v3.0 — Werkzeug für HLK-Ingenieure |
Rohrdruckverlust-Daten: Geberit FlowFit |
Kältemaschine: Climaveneta i-BX2-G07 27Y |
Gebläsekonvektoren: Kampmann KaCool W Gr. 1–4 |
<a href="https://www.imwinkelried.ch" target="_blank">Imwinkelried Lüftung + Klima AG</a>
</small>
""", unsafe_allow_html=True)
