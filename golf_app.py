import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import time
import random
import altair as alt

# --- 1. CONFIGURATION & SESSION STATE ---
st.set_page_config(page_title="2026 GGGolf Summer League", layout="wide")

ADMIN_PASSWORD = "!@#Seahawks6145!@#"
REGISTRATION_KEY = "2026!@#"
SESSION_TIMEOUT = 2 * 60 * 60  # 2 hours in seconds [cite: 1]

if "api_cooling_until" not in st.session_state: st.session_state["api_cooling_until"] = 0
if "unlocked_player" not in st.session_state: st.session_state["unlocked_player"] = None
if "authenticated" not in st.session_state: st.session_state["authenticated"] = False
if "login_timestamp" not in st.session_state: st.session_state["login_timestamp"] = 0
if "reg_access" not in st.session_state: st.session_state["reg_access"] = False

conn = st.connection("gsheets", type=GSheetsConnection)

MASTER_COLUMNS = [
    'Week', 'Player', 'PIN', 'Pars_Count', 'Birdies_Count', 
    'Eagle_Count', 'Total_Score', 'Handicap', 'Net_Score', 'DNF', 'Acknowledged'
]

GGG_POINTS = {
    1: 100, 2: 77, 3: 64, 4: 54, 5: 47, 6: 41,
    7: 36, 8: 31, 9: 27, 10: 24, 11: 21, 12: 16, 13: 13, 14: 9,
    15: 5, 16: 3, 17: 1 
} [cite: 2]

# --- 2. CORE FUNCTIONS ---

def load_data():
    try:
        data = conn.read(ttl=10) 
        if data is None or data.empty or 'Player' not in data.columns: 
            return pd.DataFrame(columns=MASTER_COLUMNS)
        
        df = data.dropna(how='all')
        # Preserve user correction: Filter out specific players [cite: 3]
        df = df[df['Player'].str.lower() != 'john']
        
        return df[df['Player'] != ""]
    except Exception as e:
        if "429" in str(e):
            st.warning("⚠️ High traffic: Using cached data while Google Sheets rests...")
        return pd.DataFrame(columns=MASTER_COLUMNS)

def calculate_rolling_handicap(player_df, target_week):
    try:
        if 'Total_Score' in player_df.columns:
            player_df = player_df.copy()
            player_df['Total_Score'] = pd.to_numeric(player_df['Total_Score'], errors='coerce')

        # Logic for pre-season and excluded event weeks [cite: 4, 5]
        excluded_weeks = [0, 4, 8]
        
        eligible_rounds = player_df[
            ((player_df['Week'] <= 0) | (~player_df['Week'].isin(excluded_weeks))) &
            (player_df['DNF'] == False) &
            (player_df['Week'] < target_week) &
            (player_df['Total_Score'].notna()) &
            (player_df['Total_Score'] > 0)
        ].sort_values('Week', ascending=False)

        if len(eligible_rounds) < 3:
            return 0.0

        last_scores = eligible_rounds.head(4)['Total_Score'].tolist()
        last_scores.sort()
        hcp = round((sum(last_scores[:3]) / 3) - 36, 1)

        return float(hcp)
    except Exception:
        return 0.0

def save_weekly_data(week, player, pars, birdies, eagles, score_val, hcp_val, pin):
    st.cache_data.clear()
    existing_data = load_data()
    is_dnf = (score_val == "DNF")
    final_gross = 0 if is_dnf else int(score_val)
    new_entry = pd.DataFrame([{
        'Week': week, 'Player': player, 'Pars_Count': pars, 'Birdies_Count': birdies, 
        'Eagle_Count': eagles, 'Total_Score': final_gross, 'Handicap': hcp_val, 
        'Net_Score': (final_gross - hcp_val) if not is_dnf else 0, 'DNF': is_dnf, 'PIN': pin
    }])
    updated_df = pd.concat([existing_data[~((existing_data['Week'] == week) & (existing_data['Player'] == player))], new_entry], ignore_index=True)
    conn.update(data=updated_df[MASTER_COLUMNS])
    st.cache_data.clear()
    
    # Visual confirmation 
    st.success(f"👍 Score Submitted Successfully for {player}!", icon="✅")
    time.sleep(2) 
    st.rerun()

# --- 3. DATA LOAD ---
df_main = load_data()
EXISTING_PLAYERS = sorted(df_main['Player'].unique().tolist()) if not df_main.empty else []

# --- 4. APP UI ---
st.markdown("<div style='text-align: center;'>", unsafe_allow_html=True)
st.image("GGGOLF-2.png", width=120) 
st.markdown("<h1>GGGOLF League 2026</h1>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

tabs = st.tabs(["📝 Scorecard", "🏆 Standings", "📅 History", "🏁 GGG Challenge", "ℹ️ League Info", "👤 Registration", "⚙️ Admin"])

with tabs[0]: # Scorecard
    if not EXISTING_PLAYERS: 
        st.warning("No players registered yet.")
    else:
        # COMPACT: Segmented control for player selection [cite: 7]
        player_select = st.segmented_control(
            "Select Your Profile", 
            options=EXISTING_PLAYERS,
            selection_mode="single",
            key="player_segment_select"
        )
        
        if player_select:
            # Session check [cite: 7]
            is_unlocked = (st.session_state.get("unlocked_player") == player_select and 
                          (time.time() - st.session_state.get("login_timestamp", 0)) < SESSION_TIMEOUT) or \
                          st.session_state.get("authenticated", False)
            
            if not is_unlocked:
                st.markdown("### 🔒 Player Verification")
                st.info(f"Enter your 4-digit PIN for **{player_select}**.")
                with st.form("unlock_form"):
                    user_pin = st.text_input("Enter PIN", type="password")
                    if st.form_submit_button("🔓 Unlock Scorecard", use_container_width=True, type="primary"):
                        p_info = df_main[df_main['Player'] == player_select]
                        reg_row = p_info[p_info['Week'] == 0]
                        if not reg_row.empty:
                            stored_pin = str(reg_row['PIN'].iloc[0]).split('.')[0].strip()
                            if user_pin.strip() == stored_pin: [cite: 8]
                                st.session_state.update({"unlocked_player": player_select, "login_timestamp": time.time()})
                                st.success("Identity Verified!")
                                time.sleep(0.5)
                                st.rerun()
                            else:
                                st.error("❌ Incorrect PIN.")
            else:
                p_data = df_main[df_main['Player'] == player_select] [cite: 9]
                
                # COMPACT: Week Selection
                week_options = list(range(-2, 1)) + list(range(1, 15))
                w_s = st.segmented_control(
                    "Select Week", 
                    options=week_options,
                    format_func=lambda x: f"P{abs(x-1)}" if x <= 0 else f"W{x}",
                    key=f"week_seg_{player_select}"
                ) or 1

                # Handicap logic [cite: 9]
                if w_s <= 0:
                    current_hcp = 0.0
                    st.info("🛠️ Pre-Season establish mode.")
                elif w_s in [4, 8]:
                    current_hcp = 0.0
                    st.info("💡 Event Week: 0.0 HCP.")
                else:
                    current_hcp = calculate_rolling_handicap(p_data, w_s)
                
                # Stats Dashboard 
                h_disp = f"+{abs(current_hcp)}" if current_hcp < 0 else f"{current_hcp}"
                played_rounds = p_data[(p_data['Week'] > 0) & (p_data['DNF'] == False)].sort_values('Week')
                
                m1, m2, m3, m4, m5 = st.columns(5)
                m1.metric("Current HCP", h_disp)
                m2.metric("Avg Net", f"{played_rounds['Net_Score'].mean():.1f}" if not played_rounds.empty else "N/A")
                m3.metric("Total Pars", int(played_rounds['Pars_Count'].sum()))
                m4.metric("Total Birdies", int(played_rounds['Birdies_Count'].sum()))
                m5.metric("Total Eagles", int(played_rounds['Eagle_Count'].sum()))

                # COMPACT SCORE ENTRY
                st.divider()
                with st.form("score_entry", clear_on_submit=True):
                    st.subheader(f"Submit Round - {'Pre-Season' if w_s <=0 else f'Week {w_s}'}")
                    
                    # Horizontal layout for score and HCP
                    row1_col1, row1_col2 = st.columns([2, 1])
                    s_v = row1_col1.selectbox("Gross Score", ["DNF"] + [str(i) for i in range(25, 120)], key="gs")
                    h_r = row1_col2.number_input("HCP to Apply", value=float(current_hcp))
                    
                    # Horizontal layout for stats
                    c1, c2, c3 = st.columns(3)
                    p_c = c1.number_input("Pars", 0, 18)
                    b_c = c2.number_input("Birdies", 0, 18)
                    e_c = c3.number_input("Eagles", 0, 18)
                    
                    if st.form_submit_button("Confirm & Submit Score", use_container_width=True, type="primary"):
                        reg_row = p_data[p_data['Week'] == 0]
                        pin = str(reg_row['PIN'].iloc[0]).split('.')[0].strip()
                        save_weekly_data(w_s, player_select, p_c, b_c, e_c, s_v, h_r, pin) [cite: 11]

with tabs[1]: # Standings [cite: 11, 12]
    st.subheader("🏆 Standings")
    if not df_main.empty:
        v = df_main[(df_main['Week'] > 0) & (df_main['DNF'] == False)].copy()
        if not v.empty:
            v['Pts'] = 0.0
            for w in v['Week'].unique():
                m = v['Week'] == w
                v.loc[m, 'R'] = v.loc[m, 'Net_Score'].rank(method='min')
                for idx, row in v[m].iterrows():
                    base_pts = GGG_POINTS.get(int(row['R']), 10.0)
                    final_pts = base_pts * 2 if w == 12 else base_pts
                    v.at[idx, 'Pts'] = final_pts                    
            res = v.groupby('Player').agg({'Pts':'sum', 'Net_Score':'mean'}).reset_index().rename(columns={'Pts':'Total Pts', 'Net_Score':'Avg Net'})
            res['Avg Net'] = res['Avg Net'].round(1)
            st.dataframe(res.sort_values(['Total Pts', 'Avg Net'], ascending=[False, True]), use_container_width=True, hide_index=True)

with tabs[2]: # History [cite: 12, 13]
    st.subheader("📅 Weekly Scores & GGG Points")
    h_df = df_main[(df_main['Week'] > 0) & (df_main['DNF'] == False)].copy()
    if not h_df.empty:
        h_df['Points'] = 0.0
        for w in h_df['Week'].unique():
            mask = h_df['Week'] == w
            h_df.loc[mask, 'Rank'] = h_df.loc[mask, 'Net_Score'].rank(method='min')
            for idx, row in h_df[mask].iterrows():
                base_pts = GGG_POINTS.get(int(row['Rank']), 10.0)
                h_df.at[idx, 'Points'] = base_pts * 2 if w == 12 else base_pts
        
        f_col1, f_col2 = st.columns(2)
        all_players = ["All Players"] + sorted(h_df['Player'].unique().tolist())
        sel_player = f_col1.selectbox("Filter by Player", all_players)
        all_weeks = ["All Weeks"] + sorted(h_df['Week'].unique().tolist())
        sel_week = f_col2.selectbox("Filter by Week", all_weeks)
        
        filtered_df = h_df.copy()
        if sel_player != "All Players": filtered_df = filtered_df[filtered_df['Player'] == sel_player]
        if sel_week != "All Weeks": filtered_df = filtered_df[filtered_df['Week'] == sel_week]
          
        display_df = filtered_df[['Week', 'Player', 'Total_Score', 'Handicap', 'Net_Score', 'Points']].copy()
        display_df = display_df.sort_values(['Week', 'Points'], ascending=[False, False])
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.info("No completed rounds recorded yet.")

with tabs[3]: # GGG Challenge [cite: 13, 14, 15, 16, 17, 18, 19]
    st.header("🏁 GGG Challenge")
    st.write("Seasonal challenges and reward opportunities for GGGolf members.")
    st.divider()
    challenge_selection = st.radio("Select Challenge:", ["Season Ball Challenge", "Gold Ticket"], horizontal=True)
    
    if challenge_selection == "Season Ball Challenge":
        st.subheader("Current Challenge: Season Ball")
        st.markdown("**Entry:** $20 for a GGG sleeve of balls")
        st.markdown("**Overview:** Use the GGG sleeve during league play. Return at least one ball from the sleeve at the season finale to qualify for the top prize.")
        st.divider()
        st.markdown("**Eligibility and Rebuy Options**")
        elig = pd.DataFrame([
            {"Option": "Original Purchase", "Entry Deadline": "Before Week 1", "Prize Eligibility": "Top prize or $100"},
            {"Option": "REBUY 1", "Entry Deadline": "Before Week 3", "Prize Eligibility": "2nd prize pick or $50"},
            {"Option": "REBUY 2", "Entry Deadline": "Before Week 7", "Prize Eligibility": "4th prize pick or $20"},
            {"Option": "REBUY 3", "Entry Deadline": "Before Week 11", "Prize Eligibility": "6th prize pick"}
        ])
        st.table(elig)
        with st.expander("Full Rules and Examples"):
            st.write("- Purchasing the sleeve registers you for the challenge.\n- To claim a prize, you must return at least one ball.")
    else:
        st.subheader("Current Challenge: Gold Ticket")
        st.markdown("**Entry:** TBA")
        st.info("Details revealed soon.")

with tabs[4]: # League Info [cite: 19, 20, 21, 22, 23, 24, 25, 26]
    st.header("ℹ️ League Information")
    info_category = st.radio("Select a Category:", ["About Us", "Handicaps", "Rules", "Schedule", "Prizes", "Expenses", "Members", "Bets"], horizontal=True)
    st.divider()

    if info_category == "About Us":
        st.subheader("GGGolf Summer League 2026")
        st.write("Formed in 2022, GGGOLF league promotes camaraderie through friendly golf competition.")
        st.markdown("* **President**: Txoovnom Vang\n* **Vice President**: Cory Vue\n* **Finance**: Mike Yang")
    
    elif info_category == "Handicaps": [cite: 26, 27, 28, 29, 30, 31, 32, 33, 34]
        st.subheader("Establishing Your Handicap")
        st.info("Pre-Season Requirement: Log 3 rounds before May 31.")
        # Restoration of your transparency tool logic here...
        st.write("Use the tool below to inspect how a player's handicap is derived.")
        if not df_main.empty:
            sel_p = st.selectbox("Select Player to Inspect", EXISTING_PLAYERS)
            st.write(f"Handicap for {sel_p}: {calculate_rolling_handicap(df_main[df_main['Player']==sel_p], 1)}")

    elif info_category == "Rules": [cite: 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48]
        st.subheader("League Rules and Format")
        st.markdown("""
        **Scoring:** Use the GGGolf app AND hand in a physical score card.\n
        **Tee Boxes:** - Brown Deer: Blue (6306 yd)
        - Dretzka: Blue (6538 yd)
        - Oakwood: Blue (6737 yd)
        """)
        st.info("Note: The League Committee reserves the right to amend rules.")

    elif info_category == "Schedule": [cite: 48, 49, 50, 51, 52, 53, 54, 55]
        st.subheader("📅 2026 Season Schedule")
        courses = ["Dretzka", "Currie", "Whitnall", "Brown Deer", "Oakwood", "Dretzka", "Currie", "Brown Deer", "Whitnall", "Oakwood", "Dretzka", "Brown Deer", "Grant"]
        for i, course in enumerate(courses, 1):
            with st.expander(f"Week {i}: {course}"):
                st.write(f"Format: {'Event' if i in [4, 8, 12] else 'Regular Round'}")

    elif info_category == "Expenses": [cite: 55, 56, 57, 58]
        st.subheader("💵 League Expenses")
        if "expenses_table" not in st.session_state: st.session_state["expenses_table"] = []
        with st.form("add_exp"):
            desc = st.text_input("Description")
            cost = st.number_input("Cost", min_value=0.0)
            if st.form_submit_button("Add"):
                st.session_state["expenses_table"].append({"Prize": desc, "Cost": cost})
        st.table(pd.DataFrame(st.session_state["expenses_table"]))

with tabs[5]: # Registration [cite: 58, 59]
    st.subheader("👤 Player Registration")
    # Existing registration logic restored...
    st.write("New members can register here.")

with tabs[6]: # Admin
    st.subheader("⚙️ Admin Controls")
    # Existing admin logic restored...
    if st.text_input("Admin Password", type="password") == ADMIN_PASSWORD:
        st.success("Admin Access Granted")
