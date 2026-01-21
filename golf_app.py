import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# --- STEP 1: CONFIGURATION & SETUP ---
# Imports and page config must come first to avoid NameErrors 
st.set_page_config(page_title="GGGolf No Animals Winter League", layout="wide") 

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

ADMIN_PASSWORD = "InsigniaSeahawks6145" 

# Updated with new player: Lefty (Handicap 5)
DEFAULT_HANDICAPS = {
    "Cory": 3, "Lex": 7, "Mike": 9,
    "Carter": 5, "Dale": 4, "Long": 6, "Txv": 4,
    "Matt": 2, "NomThai": 4, "VaMeng": 0,
    "Xuka": 0, "Beef": 9,
    "Lefty": 5
}

FEDEX_POINTS = {
    1: 100, 2: 77, 3: 64, 4: 54, 5: 47, 6: 41,
    7: 36, 8: 31, 9: 27, 10: 24, 11: 21, 12: 18
}

conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=600)
def load_data():
    return conn.read() [cite: 2]

def calculate_rolling_handicap(player_df, current_week):
    valid_rounds = player_df[(player_df['Total_Score'] > 0) & (player_df['Week'] < current_week)]
    valid_rounds = valid_rounds.sort_values('Week', ascending=False)
    if len(valid_rounds) < 4:
        return None 
    last_4 = valid_rounds.head(4)['Total_Score'].tolist()
    last_4.remove(max(last_4))
    avg_gross = sum(last_4) / 3
    return int(round(max(0, avg_gross - 36)))

def get_handicaps(current_week):
    df = load_data() 
    calculated_hcps = {}
    for player, hcp in DEFAULT_HANDICAPS.items():
        if not df.empty: [cite: 3]
            player_data = df[df['Player'] == player]
            rolling = calculate_rolling_handicap(player_data, current_week)
            calculated_hcps[player] = rolling if rolling is not None else hcp
        else:
            calculated_hcps[player] = hcp
    return calculated_hcps

def save_data(week, player, pars, birdies, eagles, score_val, hcp_val):
    st.cache_data.clear()
    existing_data = conn.read(ttl=0)
    
    is_dnf = (score_val == "DNF") [cite: 4]
    final_gross = 0 if is_dnf else int(score_val)
    final_net = 0 if is_dnf else (final_gross - hcp_val)
    new_entry = pd.DataFrame([{
        'Week': week, 'Player': player,
        'Pars_Count': pars, 'Birdies_Count': birdies, 'Eagle_Count': eagles,
        'Total_Score': final_gross, 'Handicap': hcp_val, 
        'Net_Score': final_net, 'DNF': is_dnf
    }])
    if not existing_data.empty:
        updated_df = existing_data[~((existing_data['Week'] == week) & (existing_data['Player'] == player))] [cite: 5]
        final_df = pd.concat([updated_df, new_entry], ignore_index=True)
    else:
        final_df = new_entry
    conn.update(data=final_df)
    st.cache_data.clear()

# --- DATA PROCESSING ---
df_main = load_data()
if not df_main.empty:
    df_main = df_main.fillna(0)
    df_main['DNF'] = df_main.get('DNF', False).astype(bool)
    df_main['animal_pts'] = 0.0
    for week in df_main['Week'].unique():
        mask = (df_main['Week'] == week) & (df_main['DNF'] == False)
        if mask.any():
            ranks = df_main.loc[mask, 'Net_Score'].rank(ascending=True, method='min') [cite: 6]
            df_main.loc[mask, 'animal_pts'] = ranks.map(FEDEX_POINTS).fillna(0)

# --- UI ---
st.markdown("<div style='text-align: center;'>", unsafe_allow_html=True)
st.image("GGGOLF-2.png", width=120) 
st.markdown("<h1 style='margin-top: -10px;'>GGGolf - No Animals</h1><p style='margin-top: -20px; color: gray;'>Winter League 2026</p>", unsafe_allow_html=True) [cite: 7]
st.markdown("</div>", unsafe_allow_html=True)

st.divider()

tab1, tab2, tab3, tab4, tab5 = st.tabs(["📝 Scorecard", "🏆 Standings", "📅 History", "📜 Info", "⚙️ Admin"])

# --- TAB 1: SCORECARD ---
with tab1:
    c1, c2 = st.columns(2)
    player_select = c1.selectbox("Select Player", sorted(DEFAULT_HANDICAPS.keys()), key="p_sel")
    week_select = c2.selectbox("Select Week", range(1, 13), key="w_sel")
    
    current_hcps_map = get_handicaps(week_select)
    suggested_hcp = current_hcps_map.get(player_select)
    
    if not df_main.empty: [cite: 8]
        hist_prior = df_main[(df_main['Player'] == player_select) & (df_main['Week'] < week_select)]
        season_pars_prior = int(hist_prior['Pars_Count'].sum())
        season_birdies_prior = int(hist_prior['Birdies_Count'].sum())
        season_eagles_prior = int(hist_prior['Eagle_Count'].sum())
        
        this_wk = df_main[(df_main['Player'] == player_select) & (df_main['Week'] == week_select)] [cite: 9]
        wk_p = int(this_wk.iloc[0]['Pars_Count']) if not this_wk.empty else 0
        wk_b = int(this_wk.iloc[0]['Birdies_Count']) if not this_wk.empty else 0
        wk_e = int(this_wk.iloc[0]['Eagle_Count']) if not this_wk.empty else 0
        wk_s = int(this_wk.iloc[0]['Total_Score']) if (not this_wk.empty and this_wk.iloc[0]['Total_Score'] != 0) else 45
        wk_h = int(this_wk.iloc[0]['Handicap']) if not this_wk.empty else suggested_hcp
    else: [cite: 10]
        season_pars_prior = season_birdies_prior = season_eagles_prior = 0
        wk_p = wk_b = wk_e = 0
        wk_s, wk_h = 45, suggested_hcp

    st.divider()

    r1 = st.columns(3)
    sel_pars = r1[0].selectbox("Pars (Week)", options=range(10), index=wk_p, key=f"p_in_{player_select}_{week_select}")
    sel_birdies = r1[1].selectbox("Birdies (Week)", options=range(10), index=wk_b, key=f"b_in_{player_select}_{week_select}")
    sel_eagles = r1[2].selectbox("Eagles (Week)", options=range(10), index=wk_e, key=f"e_in_{player_select}_{week_select}") [cite: 11]

    met1, met2, met3 = st.columns(3)
    met1.metric("Total Pars", season_pars_prior + sel_pars)
    met2.metric("Total Birdies", season_birdies_prior + sel_birdies)
    met3.metric("Total Eagles", season_eagles_prior + sel_eagles)
    
    st.divider()

    m1, m2, m3, m4 = st.columns([2, 2, 2, 2])
    score_options = ["DNF"] + list(range(30, 73))
    score_select = m1.selectbox("Gross Score", options=score_options, index=(0 if wk_s==0 else score_options.index(wk_s)), key=f"gs_in_{player_select}_{week_select}") [cite: 12]
    hcp_in = m2.number_input("Enter Handicap", value=wk_h, key=f"h_in_{player_select}_{week_select}")
    
    m3.metric("Suggested HCP", suggested_hcp)
    
    if score_select == "DNF":
        m4.metric("Net Score", "DNF")
    else:
        m4.metric("Net Score", int(score_select) - hcp_in)

    if st.session_state["authenticated"]:
        if st.button("Submit Score", use_container_width=True, key="sub_btn"):
            save_data(week_select, player_select, sel_pars, sel_birdies, sel_eagles, score_select, hcp_in)
            st.success(f"Scores updated for {player_select}!") [cite: 13]
            st.rerun()
    else:
        st.warning("Read-Only Mode. Login in Admin tab to edit.") [cite: 14]
        st.button("Submit Score", use_container_width=True, disabled=True, key="sub_dis")

# --- TAB 2: STANDINGS ---
with tab2:
    if not df_main.empty:
        st.markdown("<h2 style='text-align: center;'>League Standings</h2>", unsafe_allow_html=True)
        valid_scores = df_main[df_main['DNF'] == False]
        standings = df_main.groupby('Player').agg({'animal_pts': 'sum'}).rename(columns={'animal_pts': 'Animal Pts'}).reset_index()
        avg_nets = valid_scores.groupby('Player').agg({'Net_Score': 'mean'}).rename(columns={'Net_Score': 'Avg Net'}).reset_index() [cite: 15]
        standings = standings.merge(avg_nets, on='Player', how='left').fillna(0)
        final_standings = standings.round(1).sort_values(by=['Animal Pts', 'Avg Net'], ascending=[False, True])

        dynamic_height = (len(final_standings) + 1) * 35 + 3 [cite: 16]

        left_spacer, center_content, right_spacer = st.columns([1, 4, 1])
        with center_content:
            st.dataframe(
                final_standings, 
                use_container_width=True, 
                hide_index=True, [cite: 17]
                height=dynamic_height
            )
    else:
        st.info("No scores recorded yet.")

# --- TAB 3: WEEKLY HISTORY ---
with tab3:
    st.markdown("<h2 style='text-align: center;'>📅 Weekly History</h2>", unsafe_allow_html=True)
    if not df_main.empty:
        f1, f2 = st.columns([1, 2]) [cite: 18]
        filter_player = f1.multiselect("Filter Player", options=sorted(df_main['Player'].unique()), key="hist_p")
        filter_week = f2.multiselect("Filter Week", options=sorted(df_main['Week'].unique(), reverse=True), key="hist_w")
        
        history_df = df_main.copy()
        if filter_player:
            history_df = history_df[history_df['Player'].isin(filter_player)]
        if filter_week:
            history_df = history_df[history_df['Week'].isin(filter_week)] [cite: 19]
            
        history_df = history_df.sort_values(['Week', 'Player'], ascending=[False, True])
        history_df['Status'] = history_df['DNF'].map({True: "DNF", False: "Active"})
        
        display_cols = ['Week', 'Player', 'Status', 'Total_Score', 'Handicap', 'Net_Score', 'Pars_Count', 'Birdies_Count', 'Eagle_Count']
        final_history = history_df[display_cols]

        dynamic_height_hist = max(200, (len(final_history) + 1) * 35 + 3) [cite: 20]

        l_sp, center_hist, r_sp = st.columns([0.2, 9.6, 0.2]) [cite: 21]
        with center_hist:
            st.dataframe(
                final_history,
                use_container_width=True,
                hide_index=True,
                height=dynamic_height_hist
            )
    else: [cite: 22]
        st.info("No history found. Scores will appear here once submitted.") [cite: 23]

# --- TAB 4: LEAGUE INFO ---
with tab4:
    st.header("📜 League Information")
    st.divider()
    st.markdown("""
    **Drawing:** 5:45pm | **Tee Time:** 6:00pm
    * **Partners:** Randomized by picking playing cards. ***Unless players agree to play versus each other.*** * **Makeups:** Set your own time with Pin High and complete the round before it expires by Trackman; the following Friday at 12AM.
    * **Bottom 2 each bay:** Each week the bottom two from each bay will buy a bucket at the start of the next week. [cite: 24]
    * **Missed Week:** When you miss a week, once you return at the start of the round you buy a bucket.
    * **No Animal Bets:** Bet your Bets, Drink your bets.
    * **No Animal Bay Etiquette:** After hitting, return ball to hitting area for next player. Failure to do so results in 1/4 drink.
    * **First Putt:** Player makes first putt in-hole = Everyone on that bay drinks 1/4. Players from different bays can drink also if they choose [cite: 25]
    * **Chips:** Player chips in-hole = Everyone on that bay drinks drinks 1/2. Players from different bays can drink also if they choose [cite: 26]
    * **Mulligans:** Owe 1 a bucket right away. [cite: 27]
    """)

# --- TAB 5: ADMIN ---
with tab5:
    st.subheader("Admin Access")
    def check_password():
        if st.session_state["admin_pwd_input"] == ADMIN_PASSWORD:
            st.session_state["authenticated"] = True
            st.success("Admin Access Granted!")
        else:
            st.session_state["authenticated"] = False
            if st.session_state["admin_pwd_input"] != "": [cite: 28]
                st.error("Incorrect Password")

    st.text_input("Enter Admin Password", type="password", key="admin_pwd_input", on_change=check_password)

    if st.session_state["authenticated"]:
        st.write("✅ **You are currently logged in as Admin.**") [cite: 29]
        if st.button("🔄 Sync/Refresh Data", key="syn_admin"):
            st.cache_data.clear()
            st.rerun()
        if st.button("🚪 Logout"):
            st.session_state["authenticated"] = False
            st.rerun()
    else:
        st.info("Please enter the password and press Enter to enable editing on the Scorecard.") [cite: 30]
