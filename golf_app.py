import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import time
import altair as alt

# --- STEP 1: CONFIGURATION ---
st.set_page_config(page_title="2026 GGGolf Summer League", layout="wide") 

ADMIN_PASSWORD = "InsigniaSeahawks6145" 
REGISTRATION_KEY = "GG2026" 
SESSION_TIMEOUT = 4 * 60 * 60 

if "authenticated" not in st.session_state: st.session_state["authenticated"] = False
if "unlocked_player" not in st.session_state: st.session_state["unlocked_player"] = None
if "login_timestamp" not in st.session_state: st.session_state["login_timestamp"] = 0
if "session_id" not in st.session_state: st.session_state["session_id"] = 0 
if "reg_access" not in st.session_state: st.session_state["reg_access"] = False

conn = st.connection("gsheets", type=GSheetsConnection)

FEDEX_POINTS = {
    1: 100, 2: 77, 3: 64, 4: 54, 5: 47, 6: 41,
    7: 36, 8: 31, 9: 27, 10: 24, 11: 21, 12: 18, 13: 16
}

# --- STEP 2: CRASH-PROOF FUNCTIONS ---

def load_data():
    try:
        # Short TTL for fresh registration data
        data = conn.read(ttl=2)
        if data is None or data.empty:
            return pd.DataFrame()
        
        df = data.dropna(how='all')
        rename_map = {
            'Gross Score': 'Total_Score', 
            'Pars': 'Pars_Count', 
            'Birdies': 'Birdies_Count', 
            'Eagles': 'Eagle_Count'
        }
        df = df.rename(columns=rename_map)
        
        # ESSENTIAL: Fill NaNs for numeric columns so calculations don't fail
        cols_to_fix = ['Week', 'Total_Score', 'Net_Score', 'Pars_Count', 'Birdies_Count', 'Eagle_Count', 'Handicap']
        for col in cols_to_fix:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        if 'DNF' not in df.columns:
            df['DNF'] = False
        else:
            df['DNF'] = df['DNF'].astype(bool)
            
        return df
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return pd.DataFrame()

def calculate_rolling_handicap(player_df):
    try:
        excluded_weeks = [0, 4, 8, 12]
        # Only look at real rounds that aren't DNFs
        rounds = player_df[(~player_df['Week'].isin(excluded_weeks)) & (player_df['DNF'] == False)]
        rounds = rounds.sort_values('Week', ascending=False)
        
        # Get starting handicap from Week 0
        starting_hcp_row = player_df[player_df['Week'] == 0]
        starting_hcp = 10.0
        if not starting_hcp_row.empty:
            val = starting_hcp_row['Handicap'].iloc[0]
            starting_hcp = float(val) if pd.notnull(val) else 10.0
            
        if len(rounds) == 0:
            return starting_hcp
        
        last_4 = rounds.head(4)['Total_Score'].tolist()
        if len(last_4) >= 4:
            last_4.sort()
            best_3 = last_4[:3] 
            final_hcp = round(sum(best_3) / 3 - 36, 1)
        else:
            final_hcp = round(sum(last_4) / len(last_4) - 36, 1)
            
        return max(0.0, min(40.0, float(final_hcp)))
    except:
        return 10.0

# --- STEP 3: DATA PROCESSING ---
df_main = load_data()

if not df_main.empty and 'Player' in df_main.columns:
    # Filter out any rows where Player name is actually empty/NaN
    df_main = df_main[df_main['Player'].notna()]
    EXISTING_PLAYERS = sorted(df_main['Player'].unique().tolist())
else:
    EXISTING_PLAYERS = []

# --- STEP 4: UI ---
st.markdown("<div style='text-align: center;'>", unsafe_allow_html=True)
st.image("GGGOLF-2.png", width=120) 
st.markdown("<h1>GGGolf Summer League 2026</h1>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

tabs = st.tabs(["📝 Scorecard", "🏆 Standings", "🔴 Live Round", "📅 History", "ℹ️ League Info", "👤 Registration", "⚙️ Admin"])

with tabs[0]: # Scorecard
    if not EXISTING_PLAYERS:
        st.warning("No players registered yet. Head over to the Registration tab!")
    else:
        player_select = st.selectbox("Select Player", EXISTING_PLAYERS, key="p_sel")
        
        # Unlock Logic
        current_time = time.time()
        is_unlocked = (st.session_state["unlocked_player"] == player_select and (current_time - st.session_state["login_timestamp"]) < SESSION_TIMEOUT)
        if st.session_state["authenticated"]: is_unlocked = True

        if not is_unlocked:
            st.info(f"🔒 {player_select} is locked.")
            user_pin_input = st.text_input("Enter PIN", type="password", key=f"pin_{player_select}")
            if user_pin_input:
                p_info = df_main[df_main['Player'] == player_select]
                # Check PIN against Week 0 registration row
                stored_pin = str(p_info[p_info['Week'] == 0]['PIN'].iloc[0]).split('.')[0].strip() if not p_info.empty else ""
                if user_pin_input.strip() == stored_pin:
                    st.session_state["unlocked_player"] = player_select
                    st.session_state["login_timestamp"] = current_time
                    st.rerun()
                else: st.error("❌ Incorrect PIN.")
        else:
            # DASHBOARD
            p_data = df_main[df_main['Player'] == player_select]
            played_rounds = p_data[(p_data['Week'] > 0) & (p_data['DNF'] == False)].sort_values('Week')
            current_hcp = calculate_rolling_handicap(p_data)

            st.markdown(f"### 📊 {player_select}'s Dashboard")
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("HCP", f"{current_hcp:.1f}")
            m2.metric("Avg Net", f"{played_rounds['Net_Score'].mean():.1f}" if not played_rounds.empty else "N/A")
            m3.metric("Pars", int(played_rounds['Pars_Count'].sum()))
            m4.metric("Birdies", int(played_rounds['Birdies_Count'].sum()))
            m5.metric("Eagles", int(played_rounds['Eagle_Count'].sum()))

            if not played_rounds.empty:
                chart = alt.Chart(played_rounds).mark_line(color='#2e7d32', size=3).encode(
                    x=alt.X('Week:O'),
                    y=alt.Y('Net_Score:Q', scale=alt.Scale(reverse=True, zero=False)),
                    tooltip=['Week', 'Net_Score']
                ) + alt.Chart(played_rounds).mark_point(color='#2e7d32', size=100, filled=True).encode(
                    x='Week:O', y='Net_Score:Q'
                )
                st.altair_chart(chart.properties(height=300), use_container_width=True)

            st.divider()
            # SCORE SUBMISSION (Omitted for brevity, but same as before)

with tabs[5]: # Registration
    st.header("👤 Player Registration")
    if not st.session_state["reg_access"]:
        with st.form("gate"):
            if st.text_input("League Key", type="password") == REGISTRATION_KEY:
                if st.form_submit_button("Unlock"):
                    st.session_state["reg_access"] = True
                    st.rerun()
    else:
        with st.form("reg_form", clear_on_submit=True):
            n_name = st.text_input("Name")
            n_pin = st.text_input("PIN (4 digits)", max_chars=4)
            n_hcp = st.number_input("Starting HCP", 0.0, 36.0, 10.0)
            if st.form_submit_button("Register"):
                if n_name and len(n_pin) == 4:
                    # Append new row
                    new_row = pd.DataFrame([{"Week": 0, "Player": n_name, "PIN": n_pin, "Handicap": n_hcp, "DNF": True}])
                    updated_df = pd.concat([df_main, new_row], ignore_index=True)
                    conn.update(data=updated_df)
                    st.cache_data.clear()
                    st.session_state["reg_access"] = False
                    st.success("Success! Wait 2 seconds...")
                    time.sleep(2)
                    st.rerun()
                    
with tabs[6]: # Admin
    st.subheader("⚙️ Admin Controls")
    if st.text_input("Admin Password", type="password") == ADMIN_PASSWORD:
        st.session_state["authenticated"] = True
        c1, c2 = st.columns(2)
        if c1.button("Refresh Cache"): st.cache_data.clear(); st.rerun()
        if c2.button("🚨 RESET LIVE BOARD"):
            conn.update(worksheet="LiveScores", data=pd.DataFrame(columns=['Player'] + [str(i) for i in range(1, 10)]))
            st.cache_data.clear(); st.warning("Live Board Cleared!"); st.rerun()


