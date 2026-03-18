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

init_session_state()

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
# Section 4 — Modbus TCP (Gebläsekonvektoren)
# ---------------------------------------------------------------------------

st.header("4. Modbus TCP — Gebläsekonvektoren")

st.markdown(
    """
Die Kampmann KaCool W Gebläsekonvektoren werden über **KaControl MC** Steuerplatinen
mit **Modbus TCP (Ethernet)** an den Loxone Miniserver angebunden.

**Netzwerkkonfiguration:**
Jedem Gebläsekonvektor wird eine eigene IP-Adresse zugewiesen.
Die Verbindung erfolgt über ein gewöhnliches Ethernet-Netzwerk (Cat5e oder besser).

**Modbus TCP Standardparameter:**
- Port: **502**
- Unit ID: entspricht dem letzten Oktett der IP-Adresse (konfigurierbar)
- Polling-Intervall: empfohlen **1 Sekunde** für Temperaturwerte, **100 ms** für Steuerbefehle
"""
)

use_modbus_tcp = st.checkbox(
    "Modbus TCP für Gebläsekonvektoren einplanen",
    value=st.session_state.lx_modbus_tcp_fc,
    key="cb_modbus_tcp",
)
st.session_state.lx_modbus_tcp_fc = use_modbus_tcp

if use_modbus_tcp:
    st.session_state.lx_fc_ip_start = st.text_input(
        "IP-Startadresse Gebläsekonvektoren",
        value=st.session_state.lx_fc_ip_start,
        help="Die erste IP-Adresse für den ersten Gebläsekonvektor. "
             "Weitere erhalten sequentielle Adressen (z.B. .100, .101, .102, ...).",
    )

    # Anzahl Gebläsekonvektoren aus Session State
    nodes = st.session_state.get("nodes", [])
    fc_nodes = [n for n in nodes if n.get("type") == "FAN_COIL"]
    n_fc = len(fc_nodes)

    if n_fc > 0:
        st.info(f"Im Netzwerk sind **{n_fc} Gebläsekonvektor(en)** definiert.")

        # IP-Tabelle generieren
        try:
            base_parts = st.session_state.lx_fc_ip_start.rsplit(".", 1)
            base_prefix = base_parts[0]
            base_last = int(base_parts[1])
            ip_rows = []
            for i, fc_node in enumerate(fc_nodes):
                ip = f"{base_prefix}.{base_last + i}"
                fc_label = fc_node.get("label", f"FK-{i+1}")
                ip_rows.append({
                    "Gerät": fc_label,
                    "IP-Adresse": ip,
                    "Modbus TCP Port": 502,
                    "Unit ID": base_last + i,
                })
            ip_df = pd.DataFrame(ip_rows)
            st.dataframe(ip_df, use_container_width=True)
        except (ValueError, IndexError):
            st.warning("Ungültige IP-Startadresse. Bitte im Format x.x.x.x eingeben.")
    else:
        st.info(
            "Keine Gebläsekonvektoren im Netzwerk definiert. "
            "Bitte zuerst Geräte im Netzwerk-Editor erfassen."
        )

st.divider()

# ---------------------------------------------------------------------------
# Section 5 — Weitere Module
# ---------------------------------------------------------------------------

st.header("5. Weitere Erweiterungsmodule")

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
# Section 6 — Materialliste Loxone
# ---------------------------------------------------------------------------

st.header("6. Materialliste Loxone")

st.markdown(
    "Automatisch generierte Loxone-Materialliste basierend auf den "
    "Konfigurationen in den Abschnitten 1–5."
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
