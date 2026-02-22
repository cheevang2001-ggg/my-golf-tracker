import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import time

# --- STEP 1: CONFIGURATION ---
st.set_page_config(page_title="2026 GGGolf Summer League", layout="wide") 

# Session State for Security and UI Persistence
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

# --- STEP 2: FUNCTIONS (QUOTA-SAFE & INTEGER-FORCED) ---

def load_data():
    """Loads main league data with 10s cache to avoid Quota 429 errors."""
    try:
        data = conn.read(ttl=10)
        df = data.dropna(how='all')
        rename_map = {'Gross Score': 'Total_Score', 'Pars': 'Pars_Count', 'Birdies': 'Birdies_Count', 'Eagles': 'Eagle_Count'}
        return df.rename(columns=rename_map)
    except Exception as e:
        if "429" in str(e): st.warning("🐢 Google API limit reached. Cooling down for 10s...")
        return pd.DataFrame()

def load_live_data():
    """Loads live scores with 5s cache."""
    try:
        df = conn.read(worksheet="LiveScores", ttl=5)
        return df.dropna(how='all')
    except:
        return pd.DataFrame(columns=['Player'] + [f"Hole {i}" for i in range(1, 10)])

def update_live_hole(player, hole_col, strokes):
    """Updates a single hole, forcing whole numbers and bypassing cache for the write."""
    try:
        # Step A: Get freshest data directly for the write operation
        df_live = conn.read(worksheet="LiveScores", ttl=0)
        
        # Step B: Sanitize all hole columns to integers
        for i in range(1, 10):
            col = f"Hole {i}"
            if col not in df_live.columns: df_live[col] = 0
            df_live[col] = pd.to_numeric(df_live[col], errors='coerce').fillna(0).astype(int)

        # Step C: Update existing player or add new row
        if player in df_live['Player'].values:
            df_live.loc[df_live['Player'] == player, hole_col] = int(strokes)
        else:
            new_row = {col: 0 for col in df_live.columns if col != 'Player'}
            new_row['Player'] = player
            new_row[hole_col] = int(strokes)
            df_live = pd.concat([df_live, pd.DataFrame([new_row])], ignore_index=True)
        
        # Step D: Push back to GSheets
        conn.update(worksheet="LiveScores", data=df_live)
        st.cache_data.clear() # Clear cache so everyone sees the update
        st.toast(f"Hole {hole_col} updated for {player}!")
    except Exception as e:
        st.error(f"Write conflict or Quota error: {e}")

def calculate_rolling_handicap(player_df):
    rounds = player_df[(player_df['Week'] > 0) & (player_df['DNF'] == False)].sort_values('Week', ascending=False)
    starting_hcp_row = player_df[player_df['Week'] == 0]
    starting_hcp = float(starting_hcp_row['Handicap'].values[0]) if not starting_hcp_row.empty else 10.0
    if len(rounds) == 0: return starting_hcp
    last_4 = rounds.head(4)['Total_Score'].tolist()
    if len(last_4) >= 4:
        last_4.sort()
        best_3 = last_4[:3] 
        return round(sum(best_3) / 3 - 36, 1)
    else:
        return round(sum(last_4) / len(last_4) - 36, 1)

def save_weekly_data(week, player, pars, birdies, eagles, score_val, hcp_val, pin):
    st.cache_data.clear()
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
    st.cache_data.clear()
    st.rerun()

# --- STEP 3: DATA PROCESSING ---
df_main = load_data()
if not df_main.empty and 'Player' in df_main.columns:
    EXISTING_PLAYERS = sorted(df_main['Player'].unique().tolist())
    df_main['Week'] = pd.to_numeric(df_main['Week'], errors='coerce').fillna(0)
    df_main['Net_Score'] = pd.to_numeric(df_main['Net_Score'], errors='coerce').fillna(0)
    df_main['DNF'] = df_main.get('DNF', False).astype(bool)
else: EXISTING_PLAYERS = []

# --- STEP 4: UI ---
st.markdown("<div style='text-align: center;'>", unsafe_allow_html=True)
st.image("GGGOLF-2.png", width=120) 
st.markdown("<h1>GGGolf Summer League 2026</h1>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

tabs = st.tabs(["📝 Scorecard", "🏆 Standings", "🔴 Live Round", "📅 History", "ℹ️ League Info", "👤 Registration", "⚙️ Admin"])

with tabs[0]: # Weekly Totals Scorecard
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
                    save_weekly_data(week_select, player_select, s_p, s_b, s_e, score_select, hcp_in, str(p_info.iloc[0].get('PIN', '')).split('.')[0].strip())

with tabs[1]: # League Standings
    st.subheader("🏆 League Standings")
    if not df_main.empty:
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
    
    col_ref, col_empty = st.columns([1, 4])
    if col_ref.checkbox("Auto-Refresh (30s)", value=True):
        st.info("🕒 Board is live. Auto-refreshing in the background.")

    df_live = load_live_data()
    holes = [f"Hole {i}" for i in range(1, 10)]
    
    # Input section for the unlocked player
    if st.session_state["unlocked_player"]:
        with st.expander(f"Update Your Live Card: {st.session_state['unlocked_player']}", expanded=True):
            c1, c2, c3 = st.columns([2, 1, 1])
            target_hole = c1.selectbox("Select Hole", holes)
            target_strokes = c2.number_input("Strokes", 1, 15, 4)
            if c3.button("Post Score", use_container_width=True):
                update_live_hole(st.session_state["unlocked_player"], target_hole, target_strokes)
                st.rerun()
    else:
        st.warning("⚠️ Unlock your profile in the **Scorecard** tab to post live scores.")

    st.divider()
    
    # Live Display with Whole Number Formatting
    if not df_live.empty:
        # Force all hole values and total to integers
        for col in holes:
            df_live[col] = pd.to_numeric(df_live[col], errors='coerce').fillna(0).astype(int)
        
        df_live['Total'] = df_live[holes].sum(axis=1).astype(int)
        
        def highlight_me(row):
            if row.Player == st.session_state["unlocked_player"]:
                return ['background-color: #2e7d32; color: white'] * len(row)
            return [''] * len(row)

        display_cols = ['Player'] + holes + ['Total']
        styled_live = df_live[display_cols].sort_values("Total").style.apply(highlight_me, axis=1)
        st.dataframe(styled_live, use_container_width=True, hide_index=True)
    else:
        st.info("No live scores recorded yet.")

with tabs[3]: # Season History
    st.subheader("📅 Weekly History")
    if not df_main.empty:
        hist = df_main[df_main['Week'] > 0].copy()
        st.dataframe(hist.sort_values(["Week", "Player"], ascending=[False, True]), use_container_width=True, hide_index=True)

with tabs[4]: # League Info & Schedule
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
        st.markdown("### ⚖️ League Rules\n* **Handicap:** Best 3 of last 4.\n* **Par 36 Base:** All scores normalized to 9 holes.")

with tabs[5]: # Registration
    st.header("👤 Player Registration")
    with st.form("reg"):
        n_n, n_p, n_h = st.text_input("Name"), st.text_input("4-Digit PIN", max_chars=4), st.number_input("Starting Handicap", 0.0, 36.0, 10.0)
        if st.form_submit_button("Register"):
            if n_n and len(n_p) == 4:
                new_p = pd.DataFrame([{"Week": 0, "Player": n_n, "PIN": n_p, "Handicap": n_h, "DNF": True, "Pars_Count": 0, "Birdies_Count": 0, "Eagle_Count": 0}])
                conn.update(data=pd.concat([df_main, new_p], ignore_index=True))
                st.cache_data.clear()
                st.success(f"Registered {n_n}! Welcome to the league.")
                st.rerun()

with tabs[6]: # Admin Controls
    st.subheader("⚙️ Admin Controls")
    if st.text_input("Admin Password", type="password") == ADMIN_PASSWORD:
        st.session_state["authenticated"] = True
        c1, c2 = st.columns(2)
        if c1.button("Refresh All Data"):
            st.cache_data.clear()
            st.rerun()
        if c2.button("🚨 RESET LIVE BOARD"):
            reset_df = pd.DataFrame(columns=['Player'] + [f"Hole {i}" for i in range(1, 10)])
            conn.update(worksheet="LiveScores", data=reset_df)
            st.cache_data.clear()
            st.warning("Live Board Cleared!")
            st.rerun()
