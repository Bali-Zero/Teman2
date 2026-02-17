import streamlit as st

import requests

import pandas as pd

import plotly.express as px

import pyotp

import time



# --- CONFIGURAZIONE ---

API_URL = "http://127.0.0.1:8000"

TIMEOUT_SECS = 30 * 60  # 30 Minuti



st.set_page_config(page_title="Nuzantara Prime", layout="wide", page_icon="💎")



# --- 🔐 GATEKEEPER SYSTEM ---

# >>> INCOLLA QUI SOTTO LA CHIAVE GENERATA DA SETUP_AUTH.PY <<<

MASTER_KEY = "jatkom-rypnEr-7pipre" 



def check_session():

    """Gestisce Login, Logout e Timeout."""

    

    # 1. Inizializzazione Stato

    if "authenticated" not in st.session_state:

        st.session_state.authenticated = False

    if "last_activity" not in st.session_state:

        st.session_state.last_activity = 0



    # 2. Controllo Timeout (Auto-Logout)

    if st.session_state.authenticated:

        now = time.time()

        elapsed = now - st.session_state.last_activity

        

        if elapsed > TIMEOUT_SECS:

            st.session_state.authenticated = False

            st.warning("⏱️ Sessione scaduta per inattività (30 min). Effettua nuovamente il login.")

            time.sleep(2)

            st.rerun()

        

        # Aggiorna timer attività

        st.session_state.last_activity = now



    # 3. Interfaccia Login (Se non autenticato)

    if not st.session_state.authenticated:

        st.markdown("<br><br><br>", unsafe_allow_html=True)

        st.markdown("<h1 style='text-align: center;'>💎 Nuzantara Prime</h1>", unsafe_allow_html=True)

        st.markdown("<p style='text-align: center; color: #666;'>Secure Intelligence Access | 2FA Required</p>", unsafe_allow_html=True)

        

        col1, col2, col3 = st.columns([1,1,1])

        with col2:

            code_input = st.text_input("Codice Authenticator", max_chars=6, type="password")

            

            if st.button("🔓 SBLOCCA SISTEMA", use_container_width=True):

                try:

                    totp = pyotp.TOTP(MASTER_KEY)

                    if totp.verify(code_input, valid_window=1):

                        st.session_state.authenticated = True

                        st.session_state.last_activity = time.time()

                        st.success("✅ Accesso Autorizzato.")

                        time.sleep(0.5)

                        st.rerun()

                    else:

                        st.error("⛔ Codice Errato.")

                except:

                    st.error("⚠️ Errore Configurazione Chiave (Controlla MASTER_KEY)")

        

        return False # Blocca esecuzione resto dello script



    return True # Utente autenticato



# --- BLOCCO DI SICUREZZA ---

if not check_session():

    st.stop()



# ==========================================

# 🚀 ZONA PROTETTA (WAR ROOM)

# ==========================================



# --- SIDEBAR & LOGOUT MANUALE ---

st.sidebar.title("💎 PRIME")

st.sidebar.caption(f"Sessione attiva. Timeout: 30m")



if st.sidebar.button("🔒 Logout Sicuro"):

    st.session_state.authenticated = False

    st.rerun()



mode = st.sidebar.radio("Modulo Operativo:", ["🧭 Zone Finder", "🧮 ROI Calculator", "⚔️ Arena (Compare)"])



# --- FUNZIONI API ---

@st.cache_data(ttl=600) # Cache per 10 minuti per velocità

def get_zones():

    try:

        return requests.get(f"{API_URL}/zones").json()

    except:

        st.sidebar.error("⚠️ API Offline")

        return {}



zones = get_zones()

zone_options = list(zones.keys()) if zones else []



# --- MODULO 1: FINDER ---

if mode == "🧭 Zone Finder":

    st.title("🧭 Opportunity Finder")

    col1, col2 = st.columns(2)

    with col1:

        budget = st.slider("Budget Totale (USD)", 50_000, 1_000_000, 250_000, step=10_000)

    with col2:

        min_roi = st.slider("ROI Minimo (%)", 5.0, 20.0, 10.0)

        

    if st.button("🔍 Scansiona Mercato"):

        with st.spinner("Analisi Urbanistica in corso..."):

            try:

                payload = {"budget_usd": budget, "min_roi": min_roi}

                resp = requests.post(f"{API_URL}/finder", json=payload).json()

                hits = resp.get("top_opportunities", [])

                

                if hits:

                    st.success(f"Trovate {len(hits)} opportunità strategiche!")

                    df = pd.DataFrame(hits)

                    display_df = df[["zone", "land_size_are", "projected_roi", "total_investment_usd", "strategy"]]

                    display_df.columns = ["Zona", "Are", "ROI Max", "Investimento ($)", "Strategia"]

                    st.dataframe(display_df.style.format({"ROI Max": "{:.2f}%", "Investimento ($)": "${:,.0f}"}), use_container_width=True)

                else:

                    st.warning("Nessuna zona soddisfa i criteri.")

            except Exception as e:

                st.error(f"Errore API: {e}")



# --- MODULO 2: CALCULATOR ---

elif mode == "🧮 ROI Calculator":

    st.title("🧮 Deep ROI Analysis")

    c1, c2, c3 = st.columns(3)

    with c1: zone = st.selectbox("Zona", zone_options, index=0)

    with c2: size = st.number_input("Mq", 100, 10000, 500)

    with c3: price = st.number_input("Prezzo IDR", 100_000_000, 100_000_000_000, 3_250_000_000, step=50_000_000)



    if st.button("🚀 Calcola"):

        payload = {"land_size_m2": size, "price_total_idr": price, "zone_code": zone}

        resp = requests.post(f"{API_URL}/calculator", json=payload).json()

        

        matrix = resp["financial_matrix"]

        rows = []

        for bk, yields in matrix.items():

            row = {"Costruzione": bk}

            for yk, m in yields.items():

                icon = "🔥" if m['roi'] > 12 else "✅" if m['roi'] > 8 else "⚠️" if m['roi'] < 4 else ""

                row[yk] = f"{m['roi']:.2f}% {icon}"

            rows.append(row)

        st.table(pd.DataFrame(rows).set_index("Costruzione"))



# --- MODULO 3: ARENA ---

elif mode == "⚔️ Arena (Compare)":

    st.title("⚔️ Investment Face-Off")

    cA, cB = st.columns(2)

    with cA:

        st.subheader("Opzione A")

        zA = st.selectbox("Zona A", zone_options, key="zA")

        sA = st.number_input("Mq A", value=500, key="sA")

        pA = st.number_input("Prezzo A", value=3_250_000_000, key="pA")

    with cB:

        st.subheader("Opzione B")

        zB = st.selectbox("Zona B", zone_options, index=1, key="zB")

        sB = st.number_input("Mq B", value=500, key="sB")

        pB = st.number_input("Prezzo B", value=9_000_000_000, key="pB")



    if st.button("⚔️ COMBATTI"):

        payload = {

            "option_a": {"land_size_m2": sA, "price_total_idr": pA, "zone_code": zA},

            "option_b": {"land_size_m2": sB, "price_total_idr": pB, "zone_code": zB}

        }

        resp = requests.post(f"{API_URL}/compare", json=payload).json()

        

        winner = resp["winner"]

        color = "#d4edda" if winner == "A" else "#fff3cd" if winner == "TIE" else "#d1ecf1"

        st.markdown(f'<div style="background-color:{color};padding:20px;border-radius:10px;"><h3>🏆 VINCITORE: {winner}</h3>{resp["verdict"]}</div>', unsafe_allow_html=True)

        

        comp = resp["comparison"]

        c1, c2, c3 = st.columns(3)

        c1.metric("ROI A vs B", comp["roi_best_scenario"]["A"], delta=comp["roi_best_scenario"]["delta"])

        c2.metric("Break Even", comp["break_even_years"]["A"], delta=comp["break_even_years"]["delta"], delta_color="inverse")

        c3.metric("Efficienza", comp["capital_efficiency"]["A"], delta=comp["capital_efficiency"]["delta"])
