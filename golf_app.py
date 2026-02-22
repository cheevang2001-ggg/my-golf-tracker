import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import time
import altair as alt

# --- 1. CONFIGURATION & SESSION STATE ---
st.set_page_config(page_title="2026 GGGolf Summer League", layout="wide")

# Static Security Keys
ADMIN_PASSWORD = "InsigniaSeahawks6145"
REGISTRATION_KEY = "GG2026"
SESSION_TIMEOUT = 4 * 60 * 60  # 4 Hours

# Initialize Session States
state_defaults = {
    "authenticated": False,
    "unlocked_player": None,
    "login_timestamp": 0,
    "session_id": 0,
    "reg_access": False
}
for key, value in state_defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

conn = st.connection("gsheets", type=GSheetsConnection)

FEDEX_POINTS = {
    1: 100, 2: 77, 3: 64, 4: 54, 5: 47, 6: 41,
    7: 36, 8: 31, 9: 27, 10: 24, 11: 21, 12: 18, 13: 16
}

# --- 2. CORE FUNCTIONS ---

def load_data():
    """Fetches data from GSheets and cleans numeric types to prevent app crashes."""
    try:
        # Use a short TTL (2s) so new registrations appear quickly
        data = conn.read(ttl=2)
        if data is None or data.empty:
            return pd.DataFrame()
        
        df = data.dropna(how='all')
        
        # Standardize Column Names
        rename_map = {
            'Gross Score': 'Total_Score', 
            'Pars': 'Pars_Count', 
            'Birdies': 'Birdies_Count', 
            'Eagles': 'Eagle_Count'
        }
        df = df.rename(columns=rename_map)

# --- ADD THE NEW LIVE FUNCTIONS HERE (Approx Line 55) ---

def load_live_data():
    """Specifically pulls from the LiveScores worksheet."""
    hole_cols = [str(i) for i in range(1, 10)]
    try:
        df = conn.read(worksheet="LiveScores", ttl=2)
        if df is None or df.empty:
            return pd.DataFrame(columns=['Player'] + hole_cols)
        
        df.columns = [str(c).strip() for c in df.columns]
        for col in hole_cols:
            if col not in df.columns:
                df[col] = 0
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
        
        return df
    except:
        return pd.DataFrame(columns=['Player'] + hole_cols)

def update_live_score(player, hole, strokes):
    """Updates a single hole for a player in the LiveScores sheet."""
    df_live = load_live_data()
    hole_col = str(hole)
    
    if player in df_live['Player'].values:
        df_live.loc[df_live['Player'] == player, hole_col] = int(strokes)
    else:
        new_row = {str(i): 0 for i in range(1, 10)}
        new_row['Player'] = player
        new_row[hole_col] = int(strokes)
        df_live = pd.concat([df_live, pd.DataFrame([new_row])], ignore_index=True)
    
    conn.update(worksheet="LiveScores", data=df_live)
    st.cache_data.clear()
        
        # Clean Numeric Columns - This prevents the 'Blank Tab' issue
        numeric_cols = ['Week', 'Total_Score', 'Net_Score', 'Pars_Count', 'Birdies_Count', 'Eagle_Count', 'Handicap']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        # Ensure DNF is boolean
        if 'DNF' in df.columns:
            df['DNF'] = df['DNF'].astype(bool)
        else:
            df['DNF'] = False
            
        # Remove any ghost rows with no player name
        if 'Player' in df.columns:
            df = df[df['Player'].notna() & (df['Player'] != "")]
            
        return df
    except Exception as e:
        st.error(f"Data Load Error: {e}")
        return pd.DataFrame()

def calculate_rolling_handicap(player_df):
    """Calculates HCP based on Best 3 of last 4 rounds, excluding Weeks 4, 8, 12."""
    try:
        # Exclude Registration (0) and GGG Special Events
        excluded_weeks = [0, 4, 8, 12]
        rounds = player_df[(~player_df['Week'].isin(excluded_weeks)) & (player_df['DNF'] == False)]
        rounds = rounds.sort_values('Week', ascending=False)
        
        # Get baseline from Registration Row (Week 0)
        starting_hcp_row = player_df[player_df['Week'] == 0]
        starting_hcp = 10.0
        if not starting_hcp_row.empty:
            val = starting_hcp_row['Handicap'].iloc[0]
            starting_hcp = float(val) if pd.notnull(val) else 10.0
            
        if len(rounds) == 0:
            return starting_hcp
        
        last_4_scores = rounds.head(4)['Total_Score'].tolist()
        if len(last_4_scores) >= 4:
            last_4_scores.sort()
            best_3 = last_4_scores[:3] 
            return round(sum(best_3) / 3 - 36, 1)
        else:
            return round(sum(last_4_scores) / len(last_4_scores) - 36, 1)
    except:
        return 10.0

def save_weekly_data(week, player, pars, birdies, eagles, score_val, hcp_val, pin):
    """Writes scores to the sheet and clears cache for an immediate update."""
    st.cache_data.clear()
    existing_data = load_data()
    is_dnf = (score_val == "DNF")
    final_gross = 0 if is_dnf else int(score_val)
    final_net = 0 if is_dnf else (final_gross - hcp_val)
    
    new_entry = pd.DataFrame([{
        'Week': week, 'Player': player, 'Pars_Count': pars, 
        'Birdies_Count': birdies, 'Eagle_Count': eagles, 
        'Total_Score': final_gross, 'Handicap': hcp_val, 
        'Net_Score': final_net, 'DNF': is_dnf, 'PIN': pin
    }])
    
    # Overwrite if player already posted for this week
    if not existing_data.empty:
        updated_df = existing_data[~((existing_data['Week'] == week) & (existing_data['Player'] == player))]
        final_df = pd.concat([updated_df, new_entry], ignore_index=True)
    else:
        final_df = new_entry
        
    conn.update(data=final_df)
    st.cache_data.clear()
    st.rerun()

# --- 3. DATA PROCESSING ---
df_main = load_data()
EXISTING_PLAYERS = sorted(df_main['Player'].unique().tolist()) if not df_main.empty else []

# --- 4. APP UI ---
st.markdown("<div style='text-align: center;'>", unsafe_allow_html=True)
st.image("GGGOLF-2.png", width=120) 
st.markdown("<h1>GGGolf Summer League 2026</h1>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

tabs = st.tabs(["📝 Scorecard", "🏆 Standings", "🔴 Live Round", "📅 History", "ℹ️ League Info", "👤 Registration", "⚙️ Admin"])

# --- TAB 0: SCORECARD & DASHBOARD ---
with tabs[0]:
    if not EXISTING_PLAYERS:
        st.warning("No players registered yet. Please go to the Registration tab.")
    else:
        player_select = st.selectbox("Select Player", EXISTING_PLAYERS)
        
        # Security: PIN Unlock
        current_time = time.time()
        is_unlocked = (st.session_state["unlocked_player"] == player_select and (current_time - st.session_state["login_timestamp"]) < SESSION_TIMEOUT)
        if st.session_state["authenticated"]: is_unlocked = True

        if not is_unlocked:
            st.info(f"🔒 {player_select} is locked.")
            user_pin = st.text_input("Enter 4-Digit PIN", type="password", key=f"pin_{player_select}")
            if user_pin:
                p_info = df_main[df_main['Player'] == player_select]
                # Match PIN from the Week 0 (registration) row
                stored_pin = str(p_info[p_info['Week'] == 0]['PIN'].iloc[0]).split('.')[0].strip() if not p_info.empty else ""
                if user_pin.strip() == stored_pin:
                    st.session_state["unlocked_player"] = player_select
                    st.session_state["login_timestamp"] = current_time
                    st.rerun()
                else: st.error("❌ Incorrect PIN.")
        else:
            # Player Dashboard
            p_data = df_main[df_main['Player'] == player_select]
            played_rounds = p_data[(p_data['Week'] > 0) & (p_data['DNF'] == False)].sort_values('Week')
            current_hcp = calculate_rolling_handicap(p_data)

            st.markdown(f"### 📊 {player_select}'s Performance")
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("HCP", f"{current_hcp:.1f}")
            m2.metric("Avg Net", f"{played_rounds['Net_Score'].mean():.1f}" if not played_rounds.empty else "N/A")
            m3.metric("Total Pars", int(played_rounds['Pars_Count'].sum()))
            m4.metric("Birdies", int(played_rounds['Birdies_Count'].sum()))
            m5.metric("Eagles", int(played_rounds['Eagle_Count'].sum()))

            if not played_rounds.empty:
                # Custom Altair Chart: Inverted Y-axis, Whole Number X-axis
                base = alt.Chart(played_rounds).encode(x=alt.X('Week:O', title="League Week"))
                line = base.mark_line(color='#2e7d32', size=3).encode(
                    y=alt.Y('Net_Score:Q', title="Net Score", scale=alt.Scale(reverse=True, zero=False))
                )
                dots = base.mark_point(color='#2e7d32', size=100, filled=True).encode(
                    y=alt.Y('Net_Score:Q', scale=alt.Scale(reverse=True, zero=False))
                )
                st.altair_chart((line + dots).properties(height=350), use_container_width=True)

            st.divider()
            # Weekly Entry
            week_sel = st.selectbox("Select Week to Post", range(1, 15))
            if week_sel in [4, 8, 12]: st.warning("Note: This is a GGG Event (No HCP impact)")
            
            with st.form("score_entry", clear_on_submit=True):
                score_val = st.selectbox("Gross Score", ["DNF"] + [str(i) for i in range(25, 120)])
                hcp_round = st.number_input("Handicap for this round", 0.0, 40.0, value=float(current_hcp), step=0.1)
                c1, c2, c3 = st.columns(3)
                p_cnt = c1.number_input("Pars", 0, 18)
                b_cnt = c2.number_input("Birdies", 0, 18)
                e_cnt = c3.number_input("Eagles", 0, 18)
                if st.form_submit_button("Submit Score"):
                    pin = str(p_data[p_data['Week'] == 0]['PIN'].iloc[0]).split('.')[0].strip()
                    save_weekly_data(week_sel, player_select, p_cnt, b_cnt, e_cnt, score_val, hcp_round, pin)

# --- TAB 1: STANDINGS ---
with tabs[1]:
    st.subheader("🏆 Season Standings")
    if not df_main.empty:
        standings_df = df_main[df_main['Week'] > 0].copy()
        standings_df['Points'] = 0.0
        # Calculate Weekly Ranks/Points
        for w in standings_df['Week'].unique():
            week_mask = (standings_df['Week'] == w) & (standings_df['DNF'] == False)
            if week_mask.any():
                standings_df.loc[week_mask, 'Rank'] = standings_df.loc[week_mask, 'Net_Score'].rank(method='min')
                for idx, row in standings_df[week_mask].iterrows():
                    standings_df.at[idx, 'Points'] = FEDEX_POINTS.get(int(row['Rank']), 10.0)
        
        final_standings = standings_df.groupby('Player')['Points'].sum().reset_index()
        final_standings = final_standings.sort_values('Points', ascending=False).reset_index(drop=True)
        final_standings.index += 1
        st.dataframe(final_standings, use_container_width=True)

# --- TAB 2: LIVE ROUND ---
with tabs[2]:
    st.subheader("🔴 Live Round Tracking")
    
    # Check if a player is logged in to allow editing
    current_player = st.session_state.get("unlocked_player")
    
    if current_player:
        with st.expander(f"Update Score for {current_player}", expanded=True):
            c1, c2, c3 = st.columns([2, 1, 1])
            hole_to_update = c1.selectbox("Hole", range(1, 10), key="live_hole")
            strokes_to_add = c2.number_input("Strokes", 1, 15, 4, key="live_strokes")
            if c3.button("Post to Board", use_container_width=True):
                update_live_score(current_player, hole_to_update, strokes_to_add)
                st.toast(f"Hole {hole_to_update} updated!")
                time.sleep(1)
                st.rerun()
    else:
        st.warning("⚠️ Please unlock your profile in the **Scorecard** tab to post live scores.")

    st.divider()

    # Display the Board
    live_df = load_live_data()
    if not live_df.empty:
        hole_cols = [str(i) for i in range(1, 10)]
        live_df['Total'] = live_df[hole_cols].sum(axis=1)
        
        # Style the dataframe so the logged-in player is highlighted
        def highlight_current(row):
            if row.Player == current_player:
                return ['background-color: #2e7d32; color: white'] * len(row)
            return [''] * len(row)

        styled_board = live_df[['Player'] + hole_cols + ['Total']].sort_values("Total", ascending=True).style.apply(highlight_current, axis=1)
        
        st.dataframe(styled_board, use_container_width=True, hide_index=True)
    else:
        st.info("The live board is currently empty. Start posting scores!")

# --- TAB 4: INFO ---
with tabs[4]:
    st.subheader("ℹ️ League Rules")
    st.markdown("""
    - **Handicap:** Best 3 of last 4 (Week 0 is initial baseline).
    - **Exclusions:** Weeks 4, 8, and 12 (GGG Events) do not count toward rolling HCP.
    - **Scoring:** Par is 36.
    """)

# --- TAB 5: SECURE REGISTRATION ---
with tabs[5]:
    st.header("👤 Player Registration")
    if not st.session_state["reg_access"]:
        with st.form("gatekeeper"):
            access_code = st.text_input("League Registration Key", type="password")
            if st.form_submit_button("Unlock Registration"):
                if access_code == REGISTRATION_KEY:
                    st.session_state["reg_access"] = True
                    st.rerun()
                else: st.error("Invalid Key.")
    else:
        with st.form("reg_final", clear_on_submit=True):
            n_name = st.text_input("Player Full Name")
            n_pin = st.text_input("Create 4-Digit PIN (for logins)", max_chars=4)
            n_hcp = st.number_input("Starting Handicap", 0.0, 40.0, 10.0)
            if st.form_submit_button("Complete Registration"):
                if n_name and len(n_pin) == 4:
                    with st.status("Syncing with Database..."):
                        new_player_row = pd.DataFrame([{"Week": 0, "Player": n_name, "PIN": n_pin, "Handicap": n_hcp, "DNF": True}])
                        updated_df = pd.concat([df_main, new_player_row], ignore_index=True)
                        conn.update(data=updated_df)
                        st.cache_data.clear()
                        time.sleep(2)
                    st.success(f"Registered {n_name}! Go to Scorecard tab.")
                    st.session_state["reg_access"] = False
                    st.rerun()

# --- TAB 6: ADMIN ---
with tabs[6]:
    st.subheader("⚙️ Admin Controls")
    if st.text_input("Admin Password", type="password") == ADMIN_PASSWORD:
        st.session_state["authenticated"] = True
        if st.button("Refresh All App Data"):
            st.cache_data.clear()
            st.rerun()

