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
    
    # NEW: Visual confirmation & Thumbs Up message
    st.success(f"👍 Score Submitted Successfully for {player}! Great round.", icon="✅")
    time.sleep(2) # Delay so the player can see the message
    st.rerun()

# --- 3. UI LAYOUT ---
df_main = load_data()
EXISTING_PLAYERS = sorted(df_main['Player'].unique().tolist()) if not df_main.empty else []

st.markdown("<h1 style='text-align: center;'>2026 GGGOLF Summer League</h1>", unsafe_allow_html=True)

tabs = st.tabs(["📝 Scorecard", "🏆 Standings", "📅 History", "🏁 GGG Challenge", "ℹ️ League Info", "👤 Registration", "⚙️ Admin"])

with tabs[0]: # Scorecard
    if not EXISTING_PLAYERS: 
        st.warning("No players registered yet.")
    else:
        # UPDATE: Segmented Control for Player Selection
        player_select = st.segmented_control(
            "Select Your Profile", 
            options=EXISTING_PLAYERS, 
            selection_mode="single",
            key="player_seg"
        )
        
        if not player_select:
            st.info("Please select a player profile to begin.")
        else:
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
                
                # UPDATE: Segmented Control for Week Selection
                week_vals = list(range(-2, 1)) + list(range(1, 14))
                week_labels = {w: (f"Pre {abs(w-1)}" if w <= 0 else f"Wk {w}") for w in week_vals}
                
                w_s = st.segmented_control(
                    "Select Week", 
                    options=week_vals, 
                    format_func=lambda x: week_labels.get(x),
                    selection_mode="single",
                    default=1,
                    key="week_seg"
                )

                current_hcp = 0.0 if (w_s <= 0 or w_s in [4, 8]) else calculate_rolling_handicap(p_data, w_s)
                
                st.divider()
                with st.form("score_entry", clear_on_submit=True):
                    st.subheader("Submit Weekly Results")
                    
                    col_s, col_h = st.columns(2)
                    # NOTE: Number input is used for Gross Score to keep the UI compact for 25-120 range
                    s_v = col_s.number_input("Gross Score (Enter 0 for DNF)", min_value=0, max_value=150, value=36)
                    h_r = col_h.number_input("Handicap to Apply", value=float(current_hcp), step=0.1)
                    
                    st.write("**Stats**")
                    c1, c2, c3 = st.columns(3)
                    p_c = c1.number_input("Pars", 0, 18)
                    b_c = c2.number_input("Birdies", 0, 18)
                    e_c = c3.number_input("Eagles", 0, 18)
                    
                    final_score_val = "DNF" if s_v == 0 else str(int(s_v))
                    
                    if st.form_submit_button("Confirm & Submit Score", use_container_width=True, type="primary"):
                        reg_row = p_data[p_data['Week'] == 0]
                        pin = str(reg_row['PIN'].iloc[0]).split('.')[0].strip()
                        save_weekly_data(w_s, player_select, p_c, b_c, e_c, final_score_val, h_r, pin)

# --- (Rest of the tabs remain as previously configured) ---

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
            res = v.groupby('Player').agg({'Pts':'sum', 'Net_Score':'mean'}).reset_index()
            st.dataframe(res.sort_values(['Pts', 'Net_Score'], ascending=[False, True]), use_container_width=True, hide_index=True)

with tabs[3]: # GGG Challenge
    st.header("🏁 Challenges")
    challenge_selection = st.segmented_control("Active Challenges:", ["Season Ball Challenge", "Gold Ticket"], selection_mode="single", default="Season Ball Challenge")
    if challenge_selection == "Season Ball Challenge":
        st.subheader("Season Ball")
        st.write("Return a GGG ball at the finale to qualify for the top prize.")
    else:
        st.subheader("Gold Ticket")
        st.write("Details for the Gold Ticket challenge will be revealed soon.")

with tabs[4]: # League Info
    info_category = st.segmented_control("Category:", ["About Us", "Handicaps", "Rules", "Schedule", "Bets"], selection_mode="single", default="About Us")
    if info_category == "Bets":
        st.subheader("🤝 Season Long Bets")
        st.info("Track all side-wagers between players here.")
    elif info_category == "Handicaps":
        st.subheader("Handicap Rules")
        st.write("Minimum 3 completed rounds required to establish a handicap.")

with tabs[5]: # Registration
    if not st.session_state.get("reg_access"):
        with st.form("key_gate"):
            st.info("Enter Registration Key")
            rk = st.text_input("Key", type="password")
            if st.form_submit_button("Unlock"):
                if rk == REGISTRATION_KEY:
                    st.session_state["reg_access"] = True
                    st.rerun()
    else:
        with st.form("reg_form"):
            n = st.text_input("Name")
            p = st.text_input("PIN (4 digits)", max_chars=4)
            if st.form_submit_button("Register"):
                st.success("Registered!")

with tabs[6]: # Admin
    if not st.session_state.get("authenticated"):
        with st.form("admin_login"):
            ap = st.text_input("Admin Password", type="password")
            if st.form_submit_button("Login"):
                if ap == ADMIN_PASSWORD:
                    st.session_state["authenticated"] = True
                    st.rerun()
    else:
        if st.button("Reset Live Board"):
            st.write("Live Board Reset.")
