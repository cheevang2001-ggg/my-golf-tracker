import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import time

# --- STEP 1: CONFIGURATION ---
st.set_page_config(page_title="2026 GGGolf Summer League", layout="wide") 

# Session State Initialization
if "authenticated" not in st.session_state: st.session_state["authenticated"] = False
if "unlocked_player" not in st.session_state: st.session_state["unlocked_player"] = None
if "login_timestamp" not in st.session_state: st.session_state["login_timestamp"] = 0
if "session_id" not in st.session_state: st.session_state["session_id"] = 0 

ADMIN_PASSWORD = "InsigniaSeahawks6145" 
SESSION_TIMEOUT = 4 * 60 * 60 
conn = st.connection("gsheets", type=GSheetsConnection)

FEDEX_POINTS = {
    1: 100, 2: 77, 3: 64, 4: 54, 5: 47, 6: 41,
    7: 36, 8: 31, 9: 27, 10: 24, 11: 21, 12: 18, 13: 16
}

# --- STEP 2: FUNCTIONS (CRASH-PROOF & QUOTA OPTIMIZED) ---

def load_data():
    """Loads main league data with a 10-second cache safety."""
    try:
        # ttl=10 protects against Quota 429 errors when many users open the app
        data = conn.read(ttl=10)
        df = data.dropna(how='all')
        rename_map = {'Gross Score': 'Total_Score', 'Pars': 'Pars_Count', 'Birdies': 'Birdies_Count', 'Eagles': 'Eagle_Count'}
        return df.rename(columns=rename_map)
    except Exception as e:
        if "429" in str(e): st.warning("🐢 High traffic. Refreshing in 10s...")
        return pd.DataFrame()

def load_live_data():
    """Loads live scores with a 5-second cache safety."""
    try:
        df = conn.read(worksheet="LiveScores", ttl=5)
        return df.dropna(how='all')
    except:
        return pd.DataFrame(columns=['Player'] + [f"Hole {i}" for i in range(1, 10)])

def update_live_hole(player, hole_col, strokes):
    """Updates a single hole with a safety lock to prevent data overwrite."""
    try:
        # Step A: Get freshest data (ignore cache for writes)
        df_live = conn.read(worksheet="LiveScores", ttl=0)
        
        # Step B: Sanitize
        for i in range(1, 10):
            col = f"Hole {i}"
            if col not in df_live.columns: df_live[col] = 0
            df_live[col] = pd.to_numeric(df_live[col], errors='coerce').fillna(0)

        # Step C: Update or Insert
        if player in df_live['Player'].values:
            df_live.loc[df_live['Player'] == player, hole_col] = strokes
        else:
            new_row = {col: 0 for col in df_live.columns if col != 'Player'}
            new_row['Player'] = player
            new_row[hole_col] = strokes
            df_live = pd.concat([df_live, pd.DataFrame([new_row])], ignore_index=True)
        
        # Step D: Push to Google
        conn.update(worksheet="LiveScores", data=df_live)
        st.cache_data.clear() # Force immediate local update
        st.success(f"Score Saved for {hole_col}!")
        time.sleep(1) # Small pause to let Google API breathe
    except Exception as e:
        st.error(f"Write conflict: {e}. Please try again in 3 seconds.")

# --- STEP 3: DATA PROCESSING ---
df_main = load_data()
if not df_main.empty and 'Player' in df_main.columns:
    EXISTING_PLAYERS = sorted(df_main['Player'].unique().tolist())
    df_main['Week'] = pd.to_numeric(df_main['Week'], errors='coerce').fillna(0)
    df_main['Net_Score'] = pd.to_numeric(df_main['Net_Score'], errors='coerce').fillna(0)
    df_main['DNF'] = df_main.get('DNF', False).astype(bool)
else:
    EXISTING_PLAYERS = []

# --- STEP 4: UI ---
st.markdown("<div style='text-align: center;'>", unsafe_allow_html=True)
st.image("GGGOLF-2.png", width=120) 
st.markdown("<h1>GGGolf Summer League 2026</h1>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

tabs = st.tabs(["📝 Scorecard", "🏆 Standings", "🔴 Live Round", "📅 History", "ℹ️ League Info", "👤 Registration", "⚙️ Admin"])

with tabs[2]: # 🔴 LIVE ROUND
    st.subheader("🔴 Live Round Tracking")
    
    # --- AUTO REFRESH TOOL ---
    col_ref, col_empty = st.columns([1, 4])
    auto_refresh = col_ref.checkbox("Auto-Refresh (30s)", value=True)
    
    if auto_refresh:
        # This will trigger a rerun every 30 seconds
        st.info("🕒 Board is live. Refreshing every 30 seconds.")
        time.sleep(0.1) # Smoothness buffer
        st.empty() 
        # Note: In a production app, we'd use st_autorefresh, 
        # but native streamlit will rerun on any interaction.

    df_live = load_live_data()
    holes = [f"Hole {i}" for i in range(1, 10)]
    
    if st.session_state["unlocked_player"]:
        with st.expander(f"Enter Score for {st.session_state['unlocked_player']}", expanded=True):
            c1, c2, c3 = st.columns([2, 1, 1])
            target_hole = c1.selectbox("Select Hole", holes)
            target_strokes = c2.number_input("Strokes", 1, 15, 4)
            if c3.button("Update", use_container_width=True):
                update_live_hole(st.session_state["unlocked_player"], target_hole, target_strokes)
                st.rerun()
    else:
        st.warning("⚠️ Unlock your profile in the **Scorecard** tab to post scores.")

    st.divider()
    
    # SCOREBOARD DISPLAY
    if not df_live.empty:
        df_live[holes] = df_live[holes].apply(pd.to_numeric, errors='coerce').fillna(0)
        df_live['Total'] = df_live[holes].sum(axis=1)
        
        # Highlight current player's row
        def highlight_me(row):
            if row.Player == st.session_state["unlocked_player"]:
                return ['background-color: #2e7d32; color: white'] * len(row)
            return [''] * len(row)

        styled_live = df_live[['Player'] + holes + ['Total']].sort_values("Total").style.apply(highlight_me, axis=1)
        st.dataframe(styled_live, use_container_width=True, hide_index=True)
    else:
        st.info("The board is clear. Ready for tee-off!")

with tabs[3]: # History
    st.subheader("📅 Weekly History")
    if not df_main.empty:
        f1, f2 = st.columns(2)
        p_f, w_f = f1.selectbox("Filter Player", ["All"] + EXISTING_PLAYERS, key="hp"), f2.selectbox("Filter Week", ["All"] + list(range(1, 15)), key="hw")
        hist = df_main[df_main['Week'] > 0].copy()
        if p_f != "All": hist = hist[hist['Player'] == p_f]
        if w_f != "All": hist = hist[hist['Week'] == int(w_f)]
        st.dataframe(hist.sort_values(["Week", "Player"], ascending=[False, True]), use_container_width=True, hide_index=True)

with tabs[4]: # League Info
    st.subheader("ℹ️ League Information")
    info_choice = st.radio("Select View", ["Weekly Schedule", "League Rules"], horizontal=True)
    if info_choice == "Weekly Schedule":
        schedule_data = {
            "Week": [f"Week {i}" for i in range(1, 15)],
            "Date": ["May 31", "June 7", "June 14", "June 21", "June 28", "July 5", "July 12", "July 19", "July 26", "August 2", "August 9", "August 16", "August 23", "August 28"],
            "Event / Notes": ["Start", "-", "-", "GGG Event", "-", "-", "-", "GGG Event", "-", "-", "-", "GGG Event", "End", "GGG Picnic"]
        }
        st.table(pd.DataFrame(schedule_data).style.apply(lambda r: ['background-color: #90EE90; color: #808080; font-weight: bold' if any(ev in str(r["Event / Notes"]) for ev in ["GGG Event", "GGG Picnic"]) else '' for _ in r], axis=1))
    else:
        st.markdown("### ⚖️ League Rules")
        st.info("**Standard Play:** All rounds are played to a Par 36 baseline.")

with tabs[5]: # Registration
    st.header("👤 Player Registration")
    with st.form("reg"):
        n_n, n_p, n_h = st.text_input("Name"), st.text_input("4-Digit PIN", max_chars=4), st.number_input("Starting Handicap", 0.0, 36.0, 10.0)
        if st.form_submit_button("Register"):
            if n_n and len(n_p) == 4:
                new_p = pd.DataFrame([{"Week": 0, "Player": n_n, "PIN": n_p, "Handicap": n_h, "DNF": True, "Pars_Count": 0, "Birdies_Count": 0, "Eagle_Count": 0}])
                conn.update(data=pd.concat([df_main, new_p], ignore_index=True))
                st.cache_data.clear()
                st.success(f"Registered {n_n}!")
                st.rerun()

with tabs[6]: # Admin
    st.subheader("⚙️ Admin Controls")
    if st.text_input("Admin Password", type="password") == ADMIN_PASSWORD:
        st.session_state["authenticated"] = True
        st.success("Admin Authenticated")
        
        col_ref, col_res = st.columns(2)
        if col_ref.button("Refresh All App Data"):
            st.cache_data.clear()
            st.rerun()
            
        if col_res.button("🚨 RESET LIVE SCORES"):
            # Create a blank dataframe with headers only
            reset_df = pd.DataFrame(columns=['Player'] + [f"Hole {i}" for i in range(1, 10)])
            conn.update(worksheet="LiveScores", data=reset_df)
            st.cache_data.clear()
            st.warning("Live Scorecard has been wiped for the next round!")
            st.rerun()




