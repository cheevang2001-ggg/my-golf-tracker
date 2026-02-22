import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import time

# --- STEP 1: CONFIGURATION ---
st.set_page_config(page_title="2026 GGGolf Summer League", layout="wide") 

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "unlocked_player" not in st.session_state:
    st.session_state["unlocked_player"] = None
if "login_timestamp" not in st.session_state:
    st.session_state["login_timestamp"] = 0
if "session_id" not in st.session_state:
    st.session_state["session_id"] = 0 

ADMIN_PASSWORD = "InsigniaSeahawks6145" 
SESSION_TIMEOUT = 4 * 60 * 60 
conn = st.connection("gsheets", type=GSheetsConnection)

FEDEX_POINTS = {
    1: 100, 2: 77, 3: 64, 4: 54, 5: 47, 6: 41,
    7: 36, 8: 31, 9: 27, 10: 24, 11: 21, 12: 18, 13: 16
}

# --- UPDATED STEP 2: FUNCTIONS (Quota Optimized) ---

def load_data():
    try:
        # Increased ttl to 5 seconds to prevent hitting Google's 60-req/min limit
        # This means scores update every 5 seconds instead of every 0 seconds
        data = conn.read(ttl=5) 
        df = data.dropna(how='all')
        rename_map = {'Gross Score': 'Total_Score', 'Pars': 'Pars_Count', 'Birdies': 'Birdies_Count', 'Eagles': 'Eagle_Count'}
        df = df.rename(columns=rename_map)
        return df
    except Exception as e:
        if "429" in str(e):
            st.error("🐢 Google is cooling down. Please wait 10 seconds and refresh.")
        else:
            st.error(f"Error loading main data: {e}")
        return pd.DataFrame()

def load_live_data():
    try:
        # Cache live scores for 3 seconds - fast enough for golf, slow enough for Google
        df = conn.read(worksheet="LiveScores", ttl=3)
        return df.dropna(how='all')
    except Exception:
        return pd.DataFrame(columns=['Player'] + [f"Hole {i}" for i in range(1, 10)])

def update_live_hole(player, hole_col, strokes):
    try:
        # When writing data, we bypass cache to ensure the update goes through
        df_live = load_live_data()
        
        for i in range(1, 10):
            col = f"Hole {i}"
            if col not in df_live.columns: df_live[col] = 0
            df_live[col] = pd.to_numeric(df_live[col], errors='coerce').fillna(0)

        if player in df_live['Player'].values:
            df_live.loc[df_live['Player'] == player, hole_col] = strokes
        else:
            new_row = {col: 0 for col in df_live.columns if col != 'Player'}
            new_row['Player'] = player
            new_row[hole_col] = strokes
            df_live = pd.concat([df_live, pd.DataFrame([new_row])], ignore_index=True)
        
        conn.update(worksheet="LiveScores", data=df_live)
        # Clear cache immediately after an update so the player sees their change
        st.cache_data.clear()
    except Exception as e:
        if "429" in str(e):
            st.warning("Whoa! Too many updates. Wait a moment before your next entry.")
        else:
            st.error(f"Failed to update Live Score: {e}")

# --- STEP 3: DATA PROCESSING (Now safe to call load_data) ---
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

with tabs[0]: # Scorecard Entry
    if not EXISTING_PLAYERS: st.warning("No players registered.")
    else:
        player_select = st.selectbox("Select Player", EXISTING_PLAYERS, key="p_sel")
        current_time = time.time()
        is_unlocked = (st.session_state["unlocked_player"] == player_select and (current_time - st.session_state["login_timestamp"]) < SESSION_TIMEOUT)
        if st.session_state["authenticated"]: is_unlocked = True

        if not is_unlocked:
            st.info(f"🔒 {player_select} is locked.")
            pin_key = f"pin_{player_select}_{st.session_state['session_id']}"
            user_pin_input = st.text_input("Enter PIN to Unlock", type="password", key=pin_key)
            if user_pin_input:
                p_info = df_main[df_main['Player'] == player_select]
                if not p_info.empty:
                    stored_pin = str(p_info.iloc[0].get('PIN', '')).split('.')[0].strip()
                    if user_pin_input.strip() == stored_pin:
                        st.session_state["unlocked_player"] = player_select
                        st.session_state["login_timestamp"] = current_time
                        st.rerun()
                    else: st.error("❌ Incorrect PIN.")
        else:
            c1, c2 = st.columns([5, 1])
            c1.success(f"✅ **{player_select} Unlocked**")
            if c2.button("Logout 🔓"):
                st.session_state["unlocked_player"], st.session_state["login_timestamp"] = None, 0
                st.session_state["session_id"] += 1
                st.rerun()
            p_data = df_main[df_main['Player'] == player_select]
            current_hcp = calculate_rolling_handicap(p_data)
            st.info(f"💡 Current Rolling Handicap: **{current_hcp}**")
            st.divider()
            week_select = st.selectbox("Select Week", range(1, 15))
            with st.form("score_entry", clear_on_submit=True):
                score_select = st.selectbox("Gross Score", ["DNF"] + [str(i) for i in range(25, 120)])
                hcp_in = st.number_input("Handicap", 0.0, 40.0, float(current_hcp), step=0.1)
                col1, col2, col3 = st.columns(3)
                s_p, s_b, s_e = col1.number_input("Pars", 0, 18, 0), col2.number_input("Birdies", 0, 18, 0), col3.number_input("Eagles", 0, 18, 0)
                if st.form_submit_button("Submit Final Weekly Score"):
                    p_info = df_main[df_main['Player'] == player_select]
                    save_data(week_select, player_select, s_p, s_b, s_e, score_select, hcp_in, str(p_info.iloc[0].get('PIN', '')).split('.')[0].strip())

with tabs[1]: # Standings
    st.subheader("🏆 League Standings")
    if not df_main.empty:
        # Re-calc pts logic
        df_main['GGG_pts'] = 0.0
        for w in df_main['Week'].unique():
            if w == 0: continue
            mask = (df_main['Week'] == w) & (df_main['DNF'] == False)
            if mask.any():
                week_scores = df_main.loc[mask, 'Net_Score']
                ranks = week_scores.rank(ascending=True, method='min')
                for idx, r_val in ranks.items():
                    df_main.at[idx, 'GGG_pts'] = float(FEDEX_POINTS.get(int(r_val), 10))
        
        standings = df_main.groupby('Player')['GGG_pts'].sum().reset_index()
        standings['Current Handicap'] = [calculate_rolling_handicap(df_main[df_main['Player'] == p]) for p in standings['Player']]
        standings = standings.sort_values(by='GGG_pts', ascending=False).reset_index(drop=True)
        standings.index += 1
        st.dataframe(standings[['Player', 'GGG_pts', 'Current Handicap']], use_container_width=True)

with tabs[2]: # 🔴 LIVE ROUND
    st.subheader("🔴 Live Round Tracking")
    df_live = load_live_data()
    holes = [f"Hole {i}" for i in range(1, 10)]
    
    if st.session_state["unlocked_player"]:
        st.markdown(f"#### Update your score: **{st.session_state['unlocked_player']}**")
        c1, c2, c3 = st.columns([2, 1, 1])
        target_hole = c1.selectbox("Select Hole", holes)
        target_strokes = c2.number_input("Strokes", 1, 15, 4)
        if c3.button("Update Hole", use_container_width=True):
            update_live_hole(st.session_state["unlocked_player"], target_hole, target_strokes)
            st.rerun()
    else:
        st.warning("⚠️ Please unlock your profile in the **Scorecard** tab to enter live scores.")

    st.divider()
    if not df_live.empty:
        # Calculate row-wise totals
        df_live[holes] = df_live[holes].apply(pd.to_numeric, errors='coerce').fillna(0)
        df_live['Total'] = df_live[holes].sum(axis=1)
        st.dataframe(df_live[['Player'] + holes + ['Total']].sort_values("Total"), use_container_width=True, hide_index=True)
    else:
        st.info("No live scores recorded for today yet.")

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



