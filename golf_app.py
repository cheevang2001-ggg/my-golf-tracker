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

# --- STEP 2: REFINED DATA LOADING ---

def load_data():
    """Loads data with a very short TTL to ensure registration updates show up quickly."""
    try:
        # Lowering TTL to 2 seconds for high-frequency updates during registration
        data = conn.read(ttl=2) 
        df = data.dropna(how='all')
        rename_map = {'Gross Score': 'Total_Score', 'Pars': 'Pars_Count', 'Birdies': 'Birdies_Count', 'Eagles': 'Eagle_Count'}
        return df.rename(columns=rename_map)
    except Exception as e:
        return pd.DataFrame()

# ... [calculate_rolling_handicap and load_live_data remain same] ...

def calculate_rolling_handicap(player_df):
    try:
        excluded_weeks = [0, 4, 8, 12]
        rounds = player_df[(~player_df['Week'].isin(excluded_weeks)) & (player_df['DNF'] == False)].sort_values('Week', ascending=False)
        starting_hcp_row = player_df[player_df['Week'] == 0]
        starting_hcp = 10.0
        if not starting_hcp_row.empty:
            val = starting_hcp_row['Handicap'].values[0]
            starting_hcp = float(val) if pd.notnull(val) else 10.0
        if len(rounds) == 0:
            final_hcp = starting_hcp
        else:
            last_4 = rounds.head(4)['Total_Score'].tolist()
            if len(last_4) >= 4:
                last_4.sort(); best_3 = last_4[:3] 
                final_hcp = round(sum(best_3) / 3 - 36, 1)
            else:
                final_hcp = round(sum(last_4) / len(last_4) - 36, 1)
        return max(0.0, min(40.0, float(final_hcp)))
    except:
        return 10.0

def save_weekly_data(week, player, pars, birdies, eagles, score_val, hcp_val, pin):
    st.cache_data.clear() # Clear cache before saving
    existing_data = load_data()
    is_dnf = (score_val == "DNF")
    final_gross = 0 if is_dnf else int(score_val)
    final_net = 0 if is_dnf else (final_gross - hcp_val)
    new_entry = pd.DataFrame([{'Week': week, 'Player': player, 'Pars_Count': pars, 'Birdies_Count': birdies, 'Eagle_Count': eagles, 'Total_Score': final_gross, 'Handicap': hcp_val, 'Net_Score': final_net, 'DNF': is_dnf, 'PIN': pin}])
    if not existing_data.empty:
        updated_df = existing_data[~((existing_data['Week'] == week) & (existing_data['Player'] == player))]
        final_df = pd.concat([updated_df, new_entry], ignore_index=True)
    else: final_df = new_entry
    conn.update(data=final_df)
    st.cache_data.clear() # Clear cache after saving
    st.rerun()

# --- STEP 3: DATA PROCESSING ---
df_main = load_data()
if not df_main.empty and 'Player' in df_main.columns:
    EXISTING_PLAYERS = sorted(df_main['Player'].unique().tolist())
    df_main['Week'] = pd.to_numeric(df_main['Week'], errors='coerce').fillna(0).astype(int)
    # ... rest of numeric processing ...
else: EXISTING_PLAYERS = []

# --- STEP 4: UI ---
st.markdown("<div style='text-align: center;'>", unsafe_allow_html=True)
st.image("GGGOLF-2.png", width=120) 
st.markdown("<h1>GGGolf Summer League 2026</h1>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

tabs = st.tabs(["📝 Scorecard", "🏆 Standings", "🔴 Live Round", "📅 History", "ℹ️ League Info", "👤 Registration", "⚙️ Admin"])

# ... [Tabs 0 through 4 remain the same as previous logic] ...

with tabs[5]: # UPDATED PLAYER REGISTRATION
    st.header("👤 Player Registration")
    
    if not st.session_state["reg_access"]:
        st.info("🔐 This area is restricted to league members.")
        with st.form("reg_gatekeeper"):
            access_code = st.text_input("Enter League Registration Key", type="password")
            if st.form_submit_button("Verify Code"):
                if access_code == REGISTRATION_KEY:
                    st.session_state["reg_access"] = True
                    st.rerun()
                else:
                    st.error("❌ Invalid Key.")
    else:
        st.success("✅ Identity Verified.")
        with st.form("reg", clear_on_submit=True):
            n_n = st.text_input("Full Name")
            n_p = st.text_input("Create 4-Digit PIN", max_chars=4)
            n_h = st.number_input("Starting Handicap (0-36)", 0.0, 36.0, 10.0)
            
            if st.form_submit_button("Register Player"):
                if n_n and len(n_p) == 4:
                    with st.status("Registering with Google Sheets...", expanded=True) as status:
                        st.write("Writing data...")
                        new_p = pd.DataFrame([{"Week": 0, "Player": n_n, "PIN": n_p, "Handicap": n_h, "DNF": True, "Pars_Count": 0, "Birdies_Count": 0, "Eagle_Count": 0}])
                        conn.update(data=pd.concat([df_main, new_p], ignore_index=True))
                        
                        st.write("Forcing cache refresh...")
                        st.cache_data.clear() # This kills the local cache
                        time.sleep(2) # Gives Google API a heartbeat to sync
                        status.update(label="Registration Complete!", state="complete", expanded=False)
                    
                    st.success(f"Welcome, {n_n}! Check the Scorecard tab now.")
                    st.session_state["reg_access"] = False 
                    time.sleep(1)
                    st.rerun() # Forces the entire app to pull fresh data
                else:
                    st.error("Please provide a name and 4-digit PIN.")

with tabs[6]: # Admin
    st.subheader("⚙️ Admin Controls")
    if st.text_input("Admin Password", type="password") == ADMIN_PASSWORD:
        st.session_state["authenticated"] = True
        c1, c2 = st.columns(2)
        if c1.button("Refresh Cache"): st.cache_data.clear(); st.rerun()
        if c2.button("🚨 RESET LIVE BOARD"):
            conn.update(worksheet="LiveScores", data=pd.DataFrame(columns=['Player'] + [str(i) for i in range(1, 10)]))
            st.cache_data.clear(); st.warning("Live Board Cleared!"); st.rerun()

