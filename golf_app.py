import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# --- STEP 1: CONFIGURATION & SETUP ---
st.set_page_config(page_title="GGGolf No Animals Winter League", layout="wide") 

DEFAULT_HANDICAPS = {
    "Cory": 3, "Lex": 7, "Mike": 9,
    "Carter": 5, "Dale": 4, "Long": 6, "Txv": 4,
    "Matt": 2, "NomThai": 4, "VaMeng": 0,
    "Xuka": 0, "Beef": 9
}

# Points are awarded to ranked active players; [cite_start]DNFs will be excluded to receive 0 [cite: 34]
FEDEX_POINTS = {
    1: 100, 2: 85, 3: 75, 4: 70, 5: 65, 6: 60,
    7: 55, 8: 50, 9: 45, 10: 40, 11: 35, 12: 30
}

conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=600)
def load_data():
    [cite_start]return conn.read() [cite: 2, 29]

def get_handicaps():
    df = load_data() 
    if not df.empty and 'Handicap' in df.columns:
        latest = df.sort_values('Week').groupby('Player')['Handicap'].last().to_dict()
        for player in DEFAULT_HANDICAPS:
            if player not in latest:
                latest[player] = DEFAULT_HANDICAPS[player]
        return latest
    return DEFAULT_HANDICAPS

def save_data(week, player, pars, birdies, eagles, score_val, hcp_val):
    [cite_start]st.cache_data.clear() [cite: 30]
    [cite_start]existing_data = conn.read(ttl=0) [cite: 3, 30]
    
    # Logic to handle DNF vs Numeric Score from dropdown
    is_dnf = (score_val == "DNF")
    [cite_start]final_gross = 0 if is_dnf else int(score_val) [cite: 30]
    [cite_start]final_net = 0 if is_dnf else (final_gross - hcp_val) [cite: 30]

    new_entry = pd.DataFrame([{
        'Week': week, 'Player': player,
        [cite_start]'Pars_Count': pars if not is_dnf else 0, [cite: 30]
        [cite_start]'Birdies_Count': birdies if not is_dnf else 0, [cite: 30]
        [cite_start]'Eagle_Count': eagles if not is_dnf else 0, [cite: 30]
        [cite_start]'Total_Score': final_gross, [cite: 31]
        'Handicap': hcp_val, 
        [cite_start]'Net_Score': final_net, [cite: 31]
        [cite_start]'DNF': is_dnf [cite: 31]
    }])
    
    if not existing_data.empty:
        updated_df = existing_data[~((existing_data['Week'] == week) & (existing_data['Player'] == player))]
        final_df = pd.concat([updated_df, new_entry], ignore_index=True)
    else:
        [cite_start]final_df = new_entry [cite: 4, 31]
        
    [cite_start]cols_to_keep = ['Week', 'Player', 'Pars_Count', 'Birdies_Count', 'Eagle_Count', 'Total_Score', 'Handicap', 'Net_Score', 'DNF'] [cite: 32]
    final_df = final_df[[c for c in cols_to_keep if c in final_df.columns]]
    conn.update(data=final_df)
    st.cache_data.clear()

# --- STEP 2: DATA PROCESSING ---
current_handicaps = get_handicaps()
PLAYERS = sorted(list(current_handicaps.keys()))
df_main = load_data()

if not df_main.empty:
    df_main = df_main.fillna(0)
    
    # [cite_start]Safety check for DNF column to prevent KeyErrors [cite: 32, 33]
    if 'DNF' not in df_main.columns:
        df_main['DNF'] = False
    else:
        [cite_start]df_main['DNF'] = df_main['DNF'].astype(bool) [cite: 33]

    df_main['animal_pts'] = 0.0
    for week in df_main['Week'].unique():
        # [cite_start]Points are only awarded to players who are NOT DNF [cite: 33]
        week_mask = (df_main['Week'] == week) & (df_main['DNF'] == False)
        if week_mask.any():
            ranks = df_main.loc[week_mask, 'Net_Score'].rank(ascending=True, method='min')
            [cite_start]df_main.loc[week_mask, 'animal_pts'] = ranks.map(FEDEX_POINTS).fillna(0) [cite: 34]

# --- UI ---
st.markdown("<h1 style='text-align: center;'>GGGolf - No Animals - Winter League</h1>", unsafe_allow_html=True)
st.divider()

tab1, tab2, tab3, tab4, tab5 = st.tabs(["📝 Live Scorecard", "🏆 No Animals Standing", "📅 Weekly History", "📜 League Info", "⚙️ Admin"])

# --- TAB 1: SCORECARD ---
with tab1:
    [cite_start]st.subheader("Round Tracker") [cite: 5]
    col1, col2 = st.columns(2)
    player_select = col1.selectbox("Select Player", PLAYERS)
    week_select = col2.selectbox("Select Week", range(1, 13))
    selection_id = f"{player_select}_{week_select}"

    if 'counts' not in st.session_state or st.session_state.get('current_selection') != selection_id:
        st.session_state.counts = {'Par': 0, 'Birdie': 0, 'Eagle': 0}
        if not df_main.empty:
            hist = df_main[(df_main['Player'] == player_select) & (df_main['Week'] <= week_select)]
            st.session_state.counts = {
                'Par': int(hist['Pars_Count'].sum()), 
                'Birdie': int(hist['Birdies_Count'].sum()), 
                'Eagle': int(hist['Eagle_Count'].sum())
            [cite_start]} [cite: 6, 35]
            [cite_start]this_wk = df_main[(df_main['Player'] == player_select) & (df_main['Week'] == week_select)] [cite: 6, 36]
            # Use saved score if available, otherwise default to 45
            [cite_start]st.session_state['temp_score'] = int(this_wk.iloc[0]['Total_Score']) if (not this_wk.empty and this_wk.iloc[0]['Total_Score'] != 0) else 45 [cite: 6, 36]
            [cite_start]st.session_state['temp_hcp'] = int(this_wk.iloc[0]['Handicap']) if not this_wk.empty else int(current_handicaps.get(player_select, 0)) [cite: 6, 36]
        st.session_state.current_selection = selection_id
    
    # [cite_start]Input season totals [cite: 7, 37]
    r1 = st.columns(3)
    st.session_state.counts['Par'] = r1[0].number_input("Season Total Pars", min_value=0, value=st.session_state.counts['Par'])
    st.session_state.counts['Birdie'] = r1[1].number_input("Season Total Birdies", min_value=0, value=st.session_state.counts['Birdie'])
    st.session_state.counts['Eagle'] = r1[2].number_input("Season Total Eagles", min_value=0, value=st.session_state.counts['Eagle'])
    
    st.divider()

    # Gross Score Dropdown (30-72 and DNF)
    m1, m2, m3 = st.columns(3)
    score_options = ["DNF"] + list(range(30, 73))
    
    try:
        current_val = st.session_state.get('temp_score', 45)
        # If score is 0, it was a DNF entry
        default_idx = 0 if current_val == 0 else score_options.index(current_val)
    except ValueError:
        default_idx = score_options.index(45)

    score_select = m1.selectbox("Gross Score", options=score_options, index=default_idx)
    hcp_in = m2.number_input("Handicap", value=st.session_state.get('temp_hcp', 0))
    
    if score_select == "DNF":
        m3.metric("Net Score", "0 (DNF)")
    else:
        m3.metric("Net Score", int(score_select) - hcp_in)

    if st.button("Submit Score"):
        prev = df_main[(df_main['Player'] == player_select) & (df_main['Week'] < week_select)]
        save_data(
            week_select, player_select, 
            st.session_state.counts['Par'] - prev['Pars_Count'].sum(), 
            st.session_state.counts['Birdie'] - prev['Birdies_Count'].sum(), 
            st.session_state.counts['Eagle'] - prev['Eagle_Count'].sum(), 
            score_select, hcp_in
        [cite_start]) [cite: 8, 39]
        st.success("Round Recorded!")
        st.rerun()

# --- TAB 2: NO ANIMALS STANDING ---
with tab2:
    if not df_main.empty:
        st.header("🏁 No Animals Standing")
        # [cite_start]Exclude DNFs for Average Net calculations [cite: 40]
        valid_scores = df_main[df_main['DNF'] == False]
        
        [cite_start]standings = df_main.groupby('Player').agg({'animal_pts': 'sum'}).rename(columns={'animal_pts': 'Animal Pts'}).reset_index() [cite: 9, 40]
        [cite_start]avg_nets = valid_scores.groupby('Player').agg({'Net_Score': 'mean'}).rename(columns={'Net_Score': 'Avg Net'}).reset_index() [cite: 9, 40]
        
        standings = standings.merge(avg_nets, on='Player', how='left').fillna({'Avg Net': 0})
        [cite_start]standings['Total Points'] = standings['Animal Pts'] [cite: 9, 40]
        [cite_start]standings = standings.round(1).sort_values(by=['Animal Pts', 'Avg Net'], ascending=[False, True]) [cite: 9, 40]
        
        st.dataframe(
            standings[['Player', 'Animal Pts', 'Total Points', 'Avg Net']],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Player": st.column_config.TextColumn("Player", width="medium"),
                "Animal Pts": st.column_config.NumberColumn("Pts", width="small"),
                "Total Points": st.column_config.NumberColumn("Total", width="small"),
                "Avg Net": st.column_config.NumberColumn("Net", width="small"),
            [cite_start]} [cite: 10]
        )

        [cite_start]st.divider() [cite: 11, 41]
        [cite_start]st.header("🦅 Pars, Birdies, Eagles") [cite: 11, 41]
        feats = df_main.groupby('Player').agg({
            'Pars_Count': 'sum', 'Birdies_Count': 'sum', 'Eagle_Count': 'sum'
        [cite_start]}).rename(columns={'Pars_Count': 'Par', 'Birdies_Count': 'Birdie', 'Eagle_Count': 'Eagle'}).reset_index() [cite: 11, 41]
        
        st.dataframe(
            feats.sort_values('Par', ascending=False),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Player": st.column_config.TextColumn("Player", width="medium"),
                "Par": st.column_config.NumberColumn("Par", width="small"),
                "Birdie": st.column_config.NumberColumn("Birdie", width="small"),
                "Eagle": st.column_config.NumberColumn("Eagle", width="small"),
            [cite_start]} [cite: 12, 13]
        )
    else:
        st.info("No data found.")

# --- TAB 3: WEEKLY HISTORY (WITH FILTERS) ---
with tab3:
    st.header("📅 Weekly History")
    if not df_main.empty:
        f1, f2 = st.columns([1, 2])
        [cite_start]filter_player = f1.multiselect("Filter Player", options=PLAYERS) [cite: 14]
        [cite_start]filter_week = f2.multiselect("Filter Week", options=sorted(df_main['Week'].unique(), reverse=True)) [cite: 14, 42]
        
        history_df = df_main.copy()
        [cite_start]if filter_player: history_df = history_df[history_df['Player'].isin(filter_player)] [cite: 15]
        [cite_start]if filter_week: history_df = history_df[history_df['Week'].isin(filter_week)] [cite: 15]
        
        # [cite_start]Add a clear Status column for the history log [cite: 42]
        [cite_start]history_df['Status'] = history_df['DNF'].map({True: "DNF", False: "Active"}) [cite: 42]
        
        [cite_start]display_cols = ['Week', 'Player', 'Status', 'Total_Score', 'Handicap', 'Net_Score', 'Pars_Count', 'Birdies_Count', 'Eagle_Count'] [cite: 43]
        st.dataframe(
            history_df[display_cols].sort_values(['Week', 'Player'], ascending=[False, True]),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Week": st.column_config.NumberColumn("Wk", width="small"),
                "Total_Score": st.column_config.NumberColumn("Gross", width="small"),
                "Handicap": st.column_config.NumberColumn("Hcp", width="small"),
                "Net_Score": st.column_config.NumberColumn("Net", width="small"),
            [cite_start]} [cite: 16, 17]
        )
    else:
        st.info("No history available yet.")

# --- TAB 4: LEAGUE INFO ---
with tab4:
    [cite_start]st.header("📜 League Information") [cite: 18]
    st.divider()
    st.markdown("""
    [cite_start]**Drawing:** 5:45pm | **Tee Time:** 6:00pm [cite: 19, 44]
    * **Partners:** Randomized by picking playing cards. [cite_start]***Unless players agree to play versus each other.*** [cite: 19, 20, 45]
    * **DNFs:** Select **'DNF'** from the Gross Score dropdown. [cite_start]DNFs result in **0 points** and a **0 Net Score**. [cite: 30, 31]
    * [cite_start]**Makeups:** Set your own time with Pin High and complete before Trackman close; the following Friday at 12AM. [cite: 20, 46]
    * [cite_start]**Bottom 2 each bay:** Each week the bottom two from each bay will buy a bucket at the start of the next week. [cite: 21, 47]
    * [cite_start]**Missed Week:** When you miss a week, once you return at the start of the round you buy a bucket. [cite: 22, 48]
    * [cite_start]**No Animal Bets:** Bet your Bets, Drink your bets. [cite: 23, 49]
    * **No Animal Bay Etiquette:** After hitting, return bay to hitting area for next player. [cite_start]Failure to do so results in 1/4 drink. [cite: 24, 25, 50]
    * [cite_start]**First Putt:** Player makes first putt in-hole = Everyone on that bay drinks 1/4. [cite: 25, 51]
    * [cite_start]**Chips:** Player chips in-hole = Everyone on that bay drinks 1/2. [cite: 26, 52]
    * [cite_start]**Mulligans:** Owe 1 a bucket right away. [cite: 26, 53]
    """)

# --- TAB 5: ADMIN ---
with tab5:
    if st.button("🔄 Force Refresh Sync"):
        st.cache_data.clear()
        st.rerun()
