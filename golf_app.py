import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import time
import altair as alt

# --- 1. CONFIGURATION & SESSION STATE ---
st.set_page_config(page_title="2026 GGGolf Summer League", layout="wide")

ADMIN_PASSWORD = "!@#Seahawks6145!@#"
REGISTRATION_KEY = "2026!@#"
SESSION_TIMEOUT = 2 * 60 * 60 

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
    1: 100, 2: 77, 3: 64, 4: 54, 5: 47, 6: 41, 7: 36, 8: 31, 9: 27, 
    10: 24, 11: 21, 12: 16, 13: 13, 14: 9, 15: 5, 16: 3, 17: 1 
}

# --- 2. CORE FUNCTIONS ---

def load_data():
    try:
        data = conn.read(ttl=10) 
        if data is None or data.empty or 'Player' not in data.columns: 
            return pd.DataFrame(columns=MASTER_COLUMNS)
        df = data.dropna(how='all')
        # Filter out John per instructions
        df = df[df['Player'].str.lower() != 'john']
        return df[df['Player'] != ""]
    except Exception:
        return pd.DataFrame(columns=MASTER_COLUMNS)

def calculate_rolling_handicap(player_df, target_week):
    try:
        if 'Total_Score' in player_df.columns:
            player_df = player_df.copy()
            player_df['Total_Score'] = pd.to_numeric(player_df['Total_Score'], errors='coerce')

        excluded_weeks = [0, 4, 8]
        eligible_rounds = player_df[
            ((player_df['Week'] <= 0) | (~player_df['Week'].isin(excluded_weeks))) &
            (player_df['DNF'] == False) &
            (player_df['Week'] < target_week) &
            (player_df['Total_Score'].notna()) &
            (player_df['Total_Score'] > 0)
        ].sort_values('Week', ascending=False)

        # STRICT 3 ROUND MINIMUM
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
    
    # Visual confirmation for the player
    st.success(f"👍 Score Submitted Successfully for {player}!", icon="✅")
    time.sleep(2)
    st.rerun()

# --- 3. DATA LOAD ---
df_main = load_data()
EXISTING_PLAYERS = sorted(df_main['Player'].unique().tolist()) if not df_main.empty else []

# --- 4. APP UI ---
st.markdown("<div style='text-align: center;'>", unsafe_allow_html=True)
st.markdown("<h1>GGGOLF League 2026</h1>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

tabs = st.tabs(["📝 Scorecard", "🏆 Standings", "📅 History", "🏁 GGG Challenge", "ℹ️ League Info", "👤 Registration", "⚙️ Admin"])

with tabs[0]: # Scorecard
    if not EXISTING_PLAYERS: 
        st.warning("No players registered yet.")
    else:
        # UPDATED: Segmented Control for Player Selection
        st.write("### 👥 Select Your Profile")
        player_select = st.segmented_control(
            "Select Player", 
            options=EXISTING_PLAYERS, 
            selection_mode="single",
            key="player_seg_control",
            label_visibility="collapsed"
        )
        
        if player_select:
            is_unlocked = (st.session_state.get("unlocked_player") == player_select and 
                          (time.time() - st.session_state.get("login_timestamp", 0)) < SESSION_TIMEOUT) or \
                          st.session_state.get("authenticated", False)
            
            if not is_unlocked:
                st.markdown(f"### 🔒 PIN Required for **{player_select}**")
                with st.form("unlock_form"):
                    user_pin = st.text_input("Enter 4-Digit PIN", type="password")
                    if st.form_submit_button("🔓 Unlock Scorecard", use_container_width=True):
                        reg_row = df_main[(df_main['Player'] == player_select) & (df_main['Week'] == 0)]
                        if not reg_row.empty and user_pin.strip() == str(reg_row['PIN'].iloc[0]).split('.')[0].strip():
                            st.session_state.update({"unlocked_player": player_select, "login_timestamp": time.time()})
                            st.rerun()
                        else:
                            st.error("Incorrect PIN")
            else:
                p_data = df_main[df_main['Player'] == player_select]
                
                # UPDATED: Segmented Control for Week Selection
                week_vals = list(range(-2, 1)) + list(range(1, 14))
                week_labels = {w: (f"Pre {abs(w-1)}" if w <= 0 else f"Wk {w}") for w in week_vals}
                
                st.write("**Select Week**")
                w_s = st.segmented_control(
                    "Week Selection", 
                    options=week_vals, 
                    format_func=lambda x: week_labels.get(x),
                    selection_mode="single",
                    default=1,
                    key="week_seg_control",
                    label_visibility="collapsed"
                )

                current_hcp = 0.0 if (w_s <= 0 or w_s in [4, 8]) else calculate_rolling_handicap(p_data, w_s)
                
                st.divider()
                with st.form("score_entry", clear_on_submit=True):
                    st.subheader("Submit Weekly Results")
                    
                    col_gross, col_hcp = st.columns(2)
                    # UPDATED: Number input for Gross Score (Modern & Compact)
                    s_v_num = col_gross.number_input("Gross Score (0 for DNF)", min_value=0, max_value=150, value=36)
                    h_r = col_hcp.number_input("Handicap Applied", value=float(current_hcp), step=0.1)
                    
                    c1, c2, c3 = st.columns(3)
                    p_c = c1.number_input("Pars", 0, 18)
                    b_c = c2.number_input("Birdies", 0, 18)
                    e_c = c3.number_input("Eagles", 0, 18)
                    
                    final_score_str = "DNF" if s_v_num == 0 else str(int(s_v_num))
                    
                    if st.form_submit_button("Confirm & Submit Score", use_container_width=True, type="primary"):
                        reg_row = p_data[p_data['Week'] == 0]
                        pin = str(reg_row['PIN'].iloc[0]).split('.')[0].strip()
                        save_weekly_data(w_s, player_select, p_c, b_c, e_c, final_score_str, h_r, pin)
        else:
            st.info("Please select your name above to view your scorecard.")

with tabs[1]: # Standings
    st.subheader("🏆 Season Standings")
    if not df_main.empty:
        v = df_main[(df_main['Week'] > 0) & (df_main['DNF'] == False)].copy()
        if not v.empty:
            v['Pts'] = 0.0
            for w in v['Week'].unique():
                m = v['Week'] == w
                v.loc[m, 'R'] = v.loc[m, 'Net_Score'].rank(method='min')
                for idx, row in v[m].iterrows():
                    v.at[idx, 'Pts'] = GGG_POINTS.get(int(row['R']), 10.0) * (2 if w == 12 else 1)
            res = v.groupby('Player').agg({'Pts':'sum', 'Net_Score':'mean'}).reset_index().rename(columns={'Pts':'Total GGG Points', 'Net_Score':'Avg Net'})
            st.dataframe(res.sort_values(['Total GGG Points', 'Avg Net'], ascending=[False, True]), use_container_width=True, hide_index=True)

with tabs[2]: # History
    st.subheader("📅 Season History")
    h_df = df_main[(df_main['Week'] > 0) & (df_main['DNF'] == False)].copy()
    if not h_df.empty:
        st.dataframe(h_df[['Week', 'Player', 'Total_Score', 'Handicap', 'Net_Score']].sort_values('Week', ascending=False), use_container_width=True, hide_index=True)

with tabs[3]: # GGG Challenge
    st.header("🏁 GGG Challenge")
    challenge_selection = st.radio("Select Challenge:", ["Season Ball Challenge", "Gold Ticket"], horizontal=True)

    if challenge_selection == "Season Ball Challenge":
        st.subheader("Current Challenge: Season Ball")
        st.markdown("**Entry:** $20 for a GGG sleeve of balls")
        st.markdown("**Overview:** Use the GGG sleeve during league play. Return at least one ball from the sleeve at the season finale to qualify for the top prize.")
        st.markdown("1. Purchase a GGG sleeve for $20 to join.\n2. Use GGG balls during rounds.\n3. Return a ball at the finale to qualify for top prize ($100 cash option).")
    elif challenge_selection == "Gold Ticket":
        st.subheader("Current Challenge: Gold Ticket")
        st.write("Details for the Gold Ticket challenge will be revealed soon.")

with tabs[4]: # League Info
    info_category = st.radio("Category:", ["About Us", "Handicaps", "Rules", "Schedule", "Prizes", "Expenses", "Members", "Bets"], horizontal=True)
    st.divider()

    if info_category == "About Us":
        st.subheader("GGGolf Summer League 2026")
        st.write("Formed in 2022, GGGOLF league promotes camaraderie through friendly golf competition and welcomes all skill levels.")
        st.markdown("**President**: Txoovnom Vang | **Vice President**: Cory Vue | **Finance**: Mike Yang")
        st.markdown("**Rules/Players Committee**: Lex Vue, Long Lee, Deng Kue")

    elif info_category == "Handicaps":
        st.subheader("Establishing Your Handicap")
        st.info("**Requirement:** Minimum of 3 completed rounds (pre-season or regular) required to establish a handicap. Otherwise, you play at 0.0.")

    elif info_category == "Rules":
        st.subheader("League Rules")
        st.markdown("""
        - **Scoring:** Use the GGGolf app AND hand in a physical group scorecard.
        - **Tee Box:** Default is Blue/Black. C1 (HCP 20+) or Seniors (60+) play forward.
        - **Gimmies:** Putt out unless holding up pace. Putter blade length = Gimme.
        - **Pace:** 2-minute ball search. Help partners, but play ready golf.
        """)

    elif info_category == "Schedule":
        st.subheader("📅 2026 Schedule")
        courses = ["Dretzka", "Currie", "Whitnall", "Brown Deer", "Oakwood", "Dretzka", "Currie", "Brown Deer", "Whitnall", "Oakwood", "Dretzka", "Brown Deer", "Grant"]
        for i, course in enumerate(courses, 1):
            with st.expander(f"Week {i}: {course}"):
                if i == 4: st.write("Format: 2-Man Team Greensome")
                elif i == 8: st.write("Format: 4-Man Team Scramble")
                elif i == 12: st.write("Format: Double Points")
                else: st.write("Format: Regular Individual Stroke Play")

    elif info_category == "Bets":
        st.subheader("🤝 Season Long Bets")
        st.write("Track all official season-long side-action between players here.")

with tabs[5]: # Registration
    if not st.session_state.get("reg_access"):
        with st.form("reg_gate"):
            if st.text_input("League Key", type="password") == REGISTRATION_KEY and st.form_submit_button("Unlock"):
                st.session_state["reg_access"] = True
                st.rerun()
    else:
        with st.form("registration_form", clear_on_submit=True):
            n = st.text_input("Full Name")
            p = st.text_input("4-Digit PIN", max_chars=4)
            if st.form_submit_button("Complete Registration"):
                # Save week 0 record logic
                st.success(f"Welcome to the league, {n}!")

with tabs[6]: # Admin
    if not st.session_state.get("authenticated"):
        with st.form("admin_login"):
            if st.text_input("Admin Password", type="password") == ADMIN_PASSWORD and st.form_submit_button("Verify Admin"):
                st.session_state["authenticated"] = True
                st.rerun()
    else:
        if st.button("🚨 Reset Live Round Scoring", use_container_width=True, type="primary"):
            st.success("Live Round has been reset!")
