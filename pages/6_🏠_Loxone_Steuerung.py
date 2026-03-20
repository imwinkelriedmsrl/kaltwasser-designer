"""
Loxone Steuerung — Konfigurationshilfe für Loxone-Gebäudeautomation
im Zusammenspiel mit dem Kaltwasserkreislauf.

Dieses Modul hilft Planern bei der Auswahl von:
  - Loxone Miniserver (Standard / Compact / Go)
  - Bedienelemente (Touch, Touch Pure, Nano IO Air)
  - Modbus RTU Extension für das Aussengerät
  - Modbus TCP / KaControl MC für Gebläsekonvektoren
  - Optionale Erweiterungsmodule
  - Automatisch generierte Loxone-Materialliste
"""

import streamlit as st
import pandas as pd
from typing import Dict, Any, List

from data.component_library import LOXONE_PRODUCTS
from utils.helpers import init_session_state

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Loxone Steuerung – Kaltwasser Designer",
    page_icon="🏠",
    layout="wide",
)

init_session_state(st)

import os as _os
_logo_p = _os.path.join(_os.path.dirname(__file__), "..", "static", "imwinkelried_logo.png")
if _os.path.exists(_logo_p):
    st.logo(_logo_p, size="large", link="https://www.imwinkelried.ch")

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.title("🏠 Loxone Steuerung")
st.markdown(
    "Konfigurationshilfe für die Loxone-Gebäudeautomation. "
    "Weitere Informationen: "
    "[imwinkelried.ch](https://www.imwinkelried.ch) · "
    "[Loxone.com](https://www.loxone.com/dede/)"
)
st.divider()

# ---------------------------------------------------------------------------
# Helper: filter products by category
# ---------------------------------------------------------------------------

def _products_by_category(cat: str) -> Dict[str, Dict[str, Any]]:
    return {k: v for k, v in LOXONE_PRODUCTS.items() if v.get("category") == cat}


# ---------------------------------------------------------------------------
# State init for this page
# ---------------------------------------------------------------------------

if "lx_miniserver" not in st.session_state:
    st.session_state.lx_miniserver = "Miniserver"
if "lx_controls" not in st.session_state:
    st.session_state.lx_controls: Dict[str, int] = {}
if "lx_extensions" not in st.session_state:
    st.session_state.lx_extensions: Dict[str, int] = {}
if "lx_modbus_rtu_outdoor" not in st.session_state:
    st.session_state.lx_modbus_rtu_outdoor = True
if "lx_modbus_tcp_fc" not in st.session_state:
    st.session_state.lx_modbus_tcp_fc = True
if "lx_fc_ip_start" not in st.session_state:
    st.session_state.lx_fc_ip_start = "192.168.1.100"
if "lx_lamelle_ip_start" not in st.session_state:
    st.session_state.lx_lamelle_ip_start = "192.168.1.150"
if "lx_lamelle_enabled" not in st.session_state:
    st.session_state.lx_lamelle_enabled = True

# ---------------------------------------------------------------------------
# Section 1 — Miniserver Auswahl
# ---------------------------------------------------------------------------

st.header("1. Miniserver Auswahl")

miniserver_keys = list(_products_by_category("Miniserver").keys())
miniserver_labels = [LOXONE_PRODUCTS[k]["desc"] for k in miniserver_keys]

selected_ms_label = st.radio(
    "Miniserver-Variante",
    miniserver_labels,
    index=miniserver_keys.index(st.session_state.lx_miniserver)
    if st.session_state.lx_miniserver in miniserver_keys
    else 0,
    horizontal=True,
)
selected_ms_key = miniserver_keys[miniserver_labels.index(selected_ms_label)]
st.session_state.lx_miniserver = selected_ms_key

# Vergleichstabelle
ms_rows = []
for k in miniserver_keys:
    p = LOXONE_PRODUCTS[k]
    ms_rows.append({
        "Modell": p["desc"],
        "Artikel-Nr.": p["article"],
        "DI": p.get("digital_in", "–"),
        "AI": p.get("analog_in", "–"),
        "DO": p.get("digital_out", "–"),
        "AO": p.get("analog_out", "–"),
        "Modbus RTU": "✔" if p.get("modbus_rtu") else "–",
        "Modbus TCP": "✔" if p.get("modbus_tcp") else "–",
        "KNX": "✔" if p.get("knx") else "–",
    })

ms_df = pd.DataFrame(ms_rows).set_index("Modell")
st.dataframe(ms_df, use_container_width=True)

selected_ms = LOXONE_PRODUCTS[selected_ms_key]

# Hinweis bei Miniserver Go
if selected_ms_key == "Miniserver_Go":
    st.warning(
        "⚠ Der Miniserver Go verfügt über **keine eigenen I/O-Klemmen** und "
        "**kein Modbus RTU**. Für die Ansteuerung des Aussengeräts via Modbus RTU "
        "wird eine RS485 Extension benötigt, die jedoch über einen anderen "
        "Miniserver oder eine Tree-Verbindung angebunden werden muss. "
        "Prüfen Sie die Kompatibilität mit Ihrer Anlage."
    )

st.divider()

# ---------------------------------------------------------------------------
# Section 2 — Bedienung
# ---------------------------------------------------------------------------

st.header("2. Bedienelemente")

st.markdown(
    "Wählen Sie die gewünschten Bedienelemente. "
    "Diese werden in der Materialliste berücksichtigt."
)

control_products = _products_by_category("Bedienung")
col_ctrl = st.columns(len(control_products))

for i, (k, p) in enumerate(control_products.items()):
    with col_ctrl[i]:
        current_qty = st.session_state.lx_controls.get(k, 0)
        qty = st.number_input(
            p["desc"],
            min_value=0,
            max_value=20,
            value=current_qty,
            step=1,
            key=f"ctrl_{k}",
        )
        st.session_state.lx_controls[k] = qty

st.divider()

# ---------------------------------------------------------------------------
# Section 3 — Modbus RTU (Aussengerät)
# ---------------------------------------------------------------------------

st.header("3. Modbus RTU — Aussengerät")

st.markdown(
    """
Das Aussengerät (Kältemaschine) wird über **Modbus RTU (RS485)** angesteuert.
Dazu wird eine **RS485 Extension** am Loxone Miniserver benötigt.

**Verdrahtungshinweis:**
| Signal | Klemme Loxone RS485 Ext. | Klemme Aussengerät |
|--------|--------------------------|---------------------|
| A (+) | A | Modbus A |
| B (−) | B | Modbus B |
| GND | GND | COM / GND |

- Leitungstyp: **geschirmtes Twisted-Pair Kabel**, z.B. LiYCY 2×0,5 mm²
- Max. Leitungslänge: **1200 m** bei 9600 Baud
- Busabschluss (120 Ω) am letzten Teilnehmer aktivieren
- Empfohlene Baudrate: **9600 Baud**, Parität: **Even**, Stopbits: **1**
"""
)

use_rs485 = st.checkbox(
    "RS485 Extension für Aussengerät einplanen",
    value=st.session_state.lx_modbus_rtu_outdoor,
    key="cb_rs485",
)
st.session_state.lx_modbus_rtu_outdoor = use_rs485

if use_rs485:
    if not selected_ms.get("modbus_rtu", False):
        st.warning(
            "⚠ Der gewählte Miniserver unterstützt **kein natives Modbus RTU**. "
            "Die RS485 Extension ist dennoch erforderlich, prüfen Sie jedoch die "
            "Systemkonfiguration."
        )
    else:
        st.success("✔ Der gewählte Miniserver unterstützt Modbus RTU nativ über die RS485 Extension.")

st.divider()

# ---------------------------------------------------------------------------
# Section 4 — Modbus TCP (Gebläsekonvektoren & Lamellensteuerung)
# ---------------------------------------------------------------------------

st.header("4. Modbus TCP — Gebläsekonvektoren & Lamellensteuerung")

st.markdown(
    """
Die Kampmann KaCool W Gebläsekonvektoren werden über **KaControl MC** Steuerplatinen
mit **Modbus TCP (Ethernet)** an den Loxone Miniserver angebunden.
Jeder Gebläsekonvektor kann zusätzlich eine **separate Lamellensteuerung** (W55RP20)
mit eigener IP-Adresse besitzen.

**Modbus TCP Standardparameter:** Port **502** · Polling 2 s (Temp.), 10 s (Status)
"""
)

use_modbus_tcp = st.checkbox(
    "Modbus TCP für Gebläsekonvektoren einplanen",
    value=st.session_state.lx_modbus_tcp_fc,
    key="cb_modbus_tcp",
)
st.session_state.lx_modbus_tcp_fc = use_modbus_tcp

if use_modbus_tcp:
    col_ip1, col_ip2 = st.columns(2)
    with col_ip1:
        st.session_state.lx_fc_ip_start = st.text_input(
            "IP-Startadresse KaControl MC",
            value=st.session_state.lx_fc_ip_start,
            help="Erste IP für KaControl MC. Weitere FCUs erhalten sequentielle Adressen (.100, .101, ...).",
        )
    with col_ip2:
        use_lamelle = st.checkbox(
            "Lamellensteuerung (W55RP20) pro FCU",
            value=st.session_state.lx_lamelle_enabled,
            key="cb_lamelle",
        )
        st.session_state.lx_lamelle_enabled = use_lamelle

    if use_lamelle:
        st.session_state.lx_lamelle_ip_start = st.text_input(
            "IP-Startadresse Lamellensteuerung (W55RP20)",
            value=st.session_state.lx_lamelle_ip_start,
            help="Erste IP für W55RP20. Wird als Startadresse für neue Geräte verwendet.",
        )

    # Anzahl Gebläsekonvektoren aus Session State
    nodes = st.session_state.get("nodes", [])
    fc_nodes = [n for n in nodes if n.get("type") == "FAN_COIL"]
    n_fc = len(fc_nodes)

    if n_fc > 0:
        st.info(f"Im Netzwerk sind **{n_fc} Gebläsekonvektor(en)** definiert.")
    else:
        n_fc_manual = st.number_input(
            "Anzahl Gebläsekonvektoren (manuell, falls kein Netzwerk-Editor verwendet)",
            min_value=1, max_value=20, value=1, step=1, key="n_fc_manual",
        )
        fc_nodes = [{"label": f"FK-{i+1}"} for i in range(n_fc_manual)]

    # Editierbare IP-Tabelle: bestehende Einträge übernehmen, neue auto-generieren
    try:
        kc_parts = st.session_state.lx_fc_ip_start.rsplit(".", 1)
        kc_prefix = kc_parts[0]
        kc_last = int(kc_parts[1])
        lam_prefix, lam_last = None, None
        if use_lamelle:
            lam_parts = st.session_state.lx_lamelle_ip_start.rsplit(".", 1)
            lam_prefix = lam_parts[0]
            lam_last = int(lam_parts[1])
    except (ValueError, IndexError):
        st.warning("Ungültige IP-Adresse. Bitte im Format x.x.x.x eingeben.")
        kc_prefix, kc_last = "192.168.1", 100
        lam_prefix, lam_last = "192.168.1", 150

    stored_ips: Dict[str, Any] = st.session_state.lx_device_ips
    ip_rows = []
    for i, fc_node in enumerate(fc_nodes):
        fc_label = fc_node.get("label", f"FK-{i+1}")
        saved = stored_ips.get(fc_label, {})
        row: Dict[str, Any] = {
            "Gerät": fc_label,
            "KaControl MC IP": saved.get("kacontrol_ip", f"{kc_prefix}.{kc_last + i}"),
            "KaControl Port": int(saved.get("kacontrol_port", 502)),
        }
        if use_lamelle:
            row["Lamellen IP (W55RP20)"] = saved.get("lamelle_ip", f"{lam_prefix}.{lam_last + i}")
            row["Lamellen Port"] = int(saved.get("lamelle_port", 502))
        ip_rows.append(row)

    ip_df = pd.DataFrame(ip_rows)

    col_cfg = {
        "Gerät": st.column_config.TextColumn("Gerät", disabled=True),
        "KaControl MC IP": st.column_config.TextColumn("KaControl MC IP", width="medium"),
        "KaControl Port": st.column_config.NumberColumn("Port", min_value=1, max_value=65535, step=1, width="small"),
    }
    if use_lamelle:
        col_cfg["Lamellen IP (W55RP20)"] = st.column_config.TextColumn("Lamellen IP (W55RP20)", width="medium")
        col_cfg["Lamellen Port"] = st.column_config.NumberColumn("Port", min_value=1, max_value=65535, step=1, width="small")

    edited_df = st.data_editor(
        ip_df,
        column_config=col_cfg,
        use_container_width=True,
        hide_index=True,
        key="ip_editor",
    )

    # Geänderte IPs zurück in session_state speichern
    new_device_ips: Dict[str, Any] = {}
    for _, row in edited_df.iterrows():
        label = row["Gerät"]
        entry: Dict[str, Any] = {
            "kacontrol_ip": row["KaControl MC IP"],
            "kacontrol_port": int(row["KaControl Port"]),
        }
        if use_lamelle and "Lamellen IP (W55RP20)" in row:
            entry["lamelle_ip"] = row["Lamellen IP (W55RP20)"]
            entry["lamelle_port"] = int(row["Lamellen Port"])
        new_device_ips[label] = entry
    st.session_state.lx_device_ips = new_device_ips
    st.caption("💡 IP-Adressen direkt in der Tabelle anklicken und bearbeiten. Änderungen werden im Projekt gespeichert.")

st.divider()

# ---------------------------------------------------------------------------
# Section 5 — Modbus Datenpunkte
# ---------------------------------------------------------------------------

st.header("5. Modbus TCP — Datenpunkte")

tab_kc, tab_lam = st.tabs(["KaControl MC (FCU)", "Lamellensteuerung W55RP20"])

with tab_kc:
    st.markdown("**Input Register (FC4, Read only)**")
    ir_rows = [
        (1,   "Raumtemperatur Gerät 1",                          "°C", "1/10"),
        (11,  "Zulufttemperatur Gerät 1",                        "°C", "1/10"),
        (21,  "Aussentemperatur",                                "°C", "1/10"),
        (22,  "Rücklauftemperatur 2L",                           "°C", "1/10"),
        (23,  "Rücklauftemperatur 4L Heizen",                    "°C", "1/10"),
        (24,  "Rücklauftemperatur 4L Kühlen",                    "°C", "1/10"),
        (25,  "Vorlauftemperatur 2L",                            "°C", "1/10"),
        (26,  "Vorlauftemperatur 4L Heizen",                     "°C", "1/10"),
        (27,  "Vorlauftemperatur 4L Kühlen",                     "°C", "1/10"),
        (36,  "RT Sollwert 2L",                                  "°C", "1/10"),
        (37,  "RT Sollwert 4L Heizen",                           "°C", "1/10"),
        (38,  "RT Sollwert 4L Kühlen",                           "°C", "1/10"),
        (59,  "Signal Ventil 2L HeizenKühlen Gerät 1",           "%",  "1"),
        (69,  "Signal Ventilator Gerät 1",                       "%",  "1"),
        (79,  "Sammelstörung Gruppe",                            "–",  "1"),
        (80,  "Sammelmeldung Gruppe",                            "–",  "1"),
        (81,  "Sammelereignis Gruppe",                           "–",  "1"),
        (84,  "Zustand Ventil 2L HeizenKühlen",                  "–",  "1"),
        (85,  "Aktuelles Betriebsprogramm (1=Tag…4=Aus)",        "–",  "1"),
        (86,  "Betriebsart HK (1=Heizen, 2=Kühlen)",             "–",  "1"),
        (87,  "Ventilator SEL Status",                           "–",  "1"),
        (88,  "Frostschutzthermostat Status",                    "–",  "1"),
        (89,  "Kondensatpumpe Status",                           "–",  "1"),
        (90,  "BA Priorität 1",                                  "–",  "1"),
        (95,  "Filter Status",                                   "–",  "1"),
        (96,  "Grenzwertverletzung / Kurzschluss / Drahtbruch",  "–",  "1"),
        (97,  "Systemfehler",                                    "–",  "1"),
        (98,  "CAN-Fehler",                                      "–",  "1"),
        (101, "Betriebsstundengrenze SEL-Ventilator",            "–",  "1"),
        (102, "Wärmeanforderung Gruppe (0=nein, 1=ja)",          "–",  "1"),
        (103, "Kälteanforderung Gruppe (0=nein, 1=ja)",          "–",  "1"),
    ]
    st.dataframe(
        pd.DataFrame(ir_rows, columns=["Adresse", "Bezeichnung", "Einheit", "Auflösung"]),
        use_container_width=True, hide_index=True,
    )

    st.markdown("**Holding Register (FC3 lesen / FC16 schreiben)**")
    hr_rows = [
        (1,  "RT Basissollwert",                         "°C", "1/10", "210 (21,0°C)", "50–400"),
        (2,  "RT Offset Allgemein",                      "K",  "1/10", "0",            "-100–100"),
        (3,  "Raumtemperatur Istwert (GLT)",              "°C", "1/10", "50 (5,0°C)",   "–"),
        (4,  "Aussentemperatur Istwert (GLT)",            "°C", "1/10", "50 (5,0°C)",   "–"),
        (5,  "Quittierung",                              "–",  "1",    "0",            "0–1"),
        (6,  "Heartbeat",                                "–",  "1",    "0",            "0–1"),
        (7,  "Manuelle Auswahl GLT hohe Priorität",     "–",  "1",    "5",            "1–5 (5=deaktiv)"),
        (8,  "Manuelle Auswahl GLT geringe Priorität",  "–",  "1",    "5",            "1–5 (5=deaktiv)"),
        (9,  "Mode Temperaturregelung",                  "–",  "1",    "3 (Auto)",     "1=Heizen, 2=Kühlen, 3=Auto"),
        (11, "MSW Manuelle Stufenauswahl",              "–",  "1",    "6 (Auto)",     "1–5=Stufe, 6=Auto, 7=Aus"),
        (12, "Umschaltung HK GLT Vorgabe",              "–",  "1",    "1 (Heizen)",   "1=Heizen, 2=Kühlen"),
        (13, "Brandabschaltung GLT Vorgabe",            "–",  "1",    "0",            "0–1"),
        (14, "Sperre Regler Heizen",                    "–",  "1",    "0",            "0=freigegeben, 1=gesperrt"),
        (15, "Sperre Regler Kühlen",                    "–",  "1",    "0",            "0=freigegeben, 1=gesperrt"),
    ]
    st.dataframe(
        pd.DataFrame(hr_rows, columns=["Adresse", "Bezeichnung", "Einheit", "Auflösung", "Default", "Wertebereich"]),
        use_container_width=True, hide_index=True,
    )
    st.caption(
        "Gerät 1 = Adresse 1. Gerät 2 = Adresse 2 usw. (max. 10 Geräte pro KaControl MC). "
        "Für 4-Leiter: Ventil 4L Heizen (Adr. 39–48), Kühlen (Adr. 49–58) zusätzlich verfügbar."
    )

with tab_lam:
    st.markdown(
        "**W55RP20-EVB-PICO Lamellensteuerung** — Modbus TCP, separate IP pro FCU, Port 502"
    )
    col_lr, col_lw = st.columns(2)
    with col_lr:
        st.markdown("**Lesen (FC3)**")
        lam_read = [
            (1, "Status",                  "–"),
            (2, "Position Istwert",        "–"),
            (3, "MaxSchritte Istwert",     "–"),
            (4, "Geschwindigkeit Istwert", "ms"),
            (5, "Pos1 Istwert",            "–"),
            (6, "Pos2 Istwert",            "–"),
            (7, "Pos3 Istwert",            "–"),
            (8, "Pos4 Istwert",            "–"),
        ]
        st.dataframe(
            pd.DataFrame(lam_read, columns=["Adresse", "Bezeichnung", "Einheit"]),
            use_container_width=True, hide_index=True,
        )
    with col_lw:
        st.markdown("**Schreiben (FC6)**")
        lam_write = [
            (1, "Befehl (Fahren/Stop/Referenz)", "–"),
            (3, "MaxSchritte Setzen",             "–"),
            (4, "Geschwindigkeit Setzen",         "ms"),
            (5, "Position1 Setzen",               "–"),
            (6, "Position2 Setzen",               "–"),
            (7, "Position3 Setzen",               "–"),
            (8, "Position4 Setzen",               "–"),
        ]
        st.dataframe(
            pd.DataFrame(lam_write, columns=["Adresse", "Bezeichnung", "Einheit"]),
            use_container_width=True, hide_index=True,
        )
    st.caption(
        "Polling-Empfehlung: Position/Status alle 10 s · Konfigurationsregister (Pos1–4, Schritte) alle 60 s. "
        "Schreiben nur bei Änderung (FC6 Write Single Register)."
    )

st.divider()

# ---------------------------------------------------------------------------
# Section 6 — Weitere Module
# ---------------------------------------------------------------------------

st.header("6. Weitere Erweiterungsmodule")

st.markdown(
    "Optionale Loxone Erweiterungsmodule für zusätzliche Funktionen."
)

extension_products = _products_by_category("Extension")
# RS485 Extension wird in Section 3 bereits verwaltet, hier trotzdem anzeigen
# damit der Nutzer die Qty anpassen kann

col1, col2 = st.columns(2)
ext_items = list(extension_products.items())

for i, (k, p) in enumerate(ext_items):
    col = col1 if i % 2 == 0 else col2
    with col:
        # Wenn RS485 in Section 3 aktiviert, Mindestmenge = 1
        min_val = 1 if (k == "RS485_Extension" and use_rs485) else 0
        current_qty = st.session_state.lx_extensions.get(k, min_val)
        if k == "RS485_Extension" and use_rs485 and current_qty < 1:
            current_qty = 1
        qty = st.number_input(
            f"{p['desc']} (Art. {p['article']})",
            min_value=min_val,
            max_value=10,
            value=current_qty,
            step=1,
            key=f"ext_{k}",
        )
        st.session_state.lx_extensions[k] = qty
        if k == "RS485_Extension" and use_rs485:
            st.caption("Mindestens 1 Stück für Aussengerät (Modbus RTU) erforderlich.")

st.divider()

# ---------------------------------------------------------------------------
# Section 7 — Materialliste Loxone
# ---------------------------------------------------------------------------

st.header("7. Materialliste Loxone")

st.markdown(
    "Automatisch generierte Loxone-Materialliste basierend auf den "
    "Konfigurationen in den Abschnitten 1–6."
)

bom_rows: List[Dict[str, Any]] = []

# 1. Miniserver
ms_prod = LOXONE_PRODUCTS[selected_ms_key]
bom_rows.append({
    "Kategorie": "Miniserver",
    "Beschreibung": ms_prod["desc"],
    "Artikel-Nr.": ms_prod["article"],
    "Hersteller": ms_prod["manufacturer"],
    "Menge": 1,
    "Einheit": "Stk.",
})

# 2. Bedienelemente
for k, qty in st.session_state.lx_controls.items():
    if qty > 0 and k in LOXONE_PRODUCTS:
        p = LOXONE_PRODUCTS[k]
        bom_rows.append({
            "Kategorie": "Bedienung",
            "Beschreibung": p["desc"],
            "Artikel-Nr.": p["article"],
            "Hersteller": p["manufacturer"],
            "Menge": qty,
            "Einheit": "Stk.",
        })

# 3. Erweiterungsmodule
for k, qty in st.session_state.lx_extensions.items():
    if qty > 0 and k in LOXONE_PRODUCTS:
        p = LOXONE_PRODUCTS[k]
        bom_rows.append({
            "Kategorie": "Extension",
            "Beschreibung": p["desc"],
            "Artikel-Nr.": p["article"],
            "Hersteller": p["manufacturer"],
            "Menge": qty,
            "Einheit": "Stk.",
        })

# 4. Modbus RTU: RS485 Extension implizit (falls noch nicht in Extensions)
if use_rs485:
    rs485_in_bom = any(r["Artikel-Nr."] == LOXONE_PRODUCTS["RS485_Extension"]["article"] for r in bom_rows)
    if not rs485_in_bom:
        p = LOXONE_PRODUCTS["RS485_Extension"]
        bom_rows.append({
            "Kategorie": "Extension",
            "Beschreibung": p["desc"] + " (für Aussengerät Modbus RTU)",
            "Artikel-Nr.": p["article"],
            "Hersteller": p["manufacturer"],
            "Menge": 1,
            "Einheit": "Stk.",
        })

if bom_rows:
    bom_df = pd.DataFrame(bom_rows)

    # Zusammenfassung nach Kategorie
    summary = bom_df.groupby("Kategorie")["Menge"].sum().reset_index()
    summary.columns = ["Kategorie", "Anzahl Positionen (Stk.)"]

    col_bom, col_sum = st.columns([3, 1])
    with col_bom:
        st.subheader("Positionen")
        st.dataframe(bom_df, use_container_width=True, hide_index=True)
    with col_sum:
        st.subheader("Übersicht")
        st.dataframe(summary, use_container_width=True, hide_index=True)
        st.metric("Gesamtpositionen", len(bom_rows))

    # Export
    st.subheader("Export")
    csv_data = bom_df.to_csv(index=False, sep=";").encode("utf-8-sig")
    st.download_button(
        label="📥 Materialliste als CSV exportieren",
        data=csv_data,
        file_name="loxone_materialliste.csv",
        mime="text/csv",
    )
else:
    st.info("Keine Positionen in der Materialliste. Bitte Konfiguration in den Abschnitten 1–5 vornehmen.")

st.divider()

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

st.markdown(
    "<small>Loxone ist ein eingetragenes Warenzeichen der Loxone Electronics GmbH. "
    "Angaben ohne Gewähr. Für Planung und Projektierung wenden Sie sich an einen "
    "zertifizierten Loxone Partner. · "
    "<a href='https://www.imwinkelried.ch' target='_blank'>imwinkelried.ch</a></small>",
    unsafe_allow_html=True,
)
