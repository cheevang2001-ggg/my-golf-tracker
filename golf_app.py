import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# --- STEP 1: CONFIGURATION & SETUP ---
st.set_page_config(page_title="GGGolf No Animals Winter League", layout="wide") [cite: 1]

DEFAULT_HANDICAPS = {
    "Cory": 3, "Lex": 7, "John": 20, "Mike": 9,
    "Carter": 5, "Dale": 4, "Long": 6, "Txv": 4,
    "Matt": 2, "NomThai": 4, "VaMeng": 0
} [cite: 1]

# UPDATED: Point Values per your latest requirements
POINT_VALUES = {
    "Par": 1.85, 
    "Birdie": 2.0,       # Updated [cite: 1]
    "Eagle": 3.0,
    "Gimme Par": 1.30,   # Updated [cite: 1]
    "Gimme Birdie": 1.75, 
    "Gimme Eagle": 2.5    # Updated [cite: 2]
} [cite: 1, 2]

conn = st.connection("gsheets", type=GSheetsConnection) [cite: 2]

@st.cache_data(ttl=600)
def load_data():
    return conn.read() [cite: 2]

def get_handicaps():
    df = load_data() [cite: 2]
    if not df.empty and 'Handicap' in df.columns:
        latest = df.sort_values('Week').groupby('Player')['Handicap'].last().to_dict() [cite: 2]
        for player in DEFAULT_HANDICAPS:
            if player not in latest:
                latest[player] = DEFAULT_HANDICAPS[player] [cite: 2]
        return latest [cite: 3]
    return DEFAULT_HANDICAPS [cite: 3]

def save_data(week, player, pars, birdies, eagles, g_pars, g_birdies, g_eagles, score, hcp_val):
    st.cache_data.clear() [cite: 3]
    existing_data = conn.read(ttl=0) [cite: 3]
    
    new_entry = pd.DataFrame([{
        'Week': week, 'Player': player,
        'Pars_Count': pars, 'Birdies_Count': birdies, 'Eagle_Count': eagles,
        'G_Par_Count': g_pars, 'G_Birdie_Count': g_birdies, 'G_Eagle_Count': g_eagles,
        'Total_Score': score, 'Handicap': hcp_val, 'Net_Score': score - hcp_val
    }]) [cite: 3]
    
    if not existing_data.empty:
        updated_df = existing_data[~((existing_data['Week'] == week) & (existing_data['Player'] == player))] [cite: 4]
        final_df = pd.concat([updated_df, new_entry], ignore_index=True) [cite: 4]
    else:
        final_df = new_entry [cite: 4]
    
    conn.update(data=final_df) [cite: 4]
    st.cache_data.clear() [cite: 4]

# --- STEP 2: DATA PREPARATION ---
current_handicaps = get_handicaps() [cite: 4]
PLAYERS = sorted(list(current_handicaps.keys())) [cite: 4]
df_main = load_data() [cite: 4]

# Global point calculation for leaderboard
if not df_main.empty:
    df_main = df_main.fillna(0) [cite: 4]
    df_main['calc_pts'] = (
        (df_main['Pars_Count'] * POINT_VALUES["Par"]) + 
        (df_main['Birdies_Count'] * POINT_VALUES["Birdie"]) + 
        (df_main['Eagle_Count'] * POINT_VALUES["Eagle"]) +
        (df_main['G_Par_Count'] * POINT_VALUES["Gimme Par"]) + 
        (df_main['G_Birdie_Count'] * POINT_VALUES["Gimme Birdie"]) + 
        (df_main['G_Eagle_Count'] * POINT_VALUES["Gimme Eagle"])
    ) [cite: 4, 5]

# --- LOGO & TITLE ---
col_l1, col_l2, col_l3 = st.columns([1,1,1]) [cite: 5]
with col_l2:
    try:
        st.image("GGGOLF-2.png", width=200) [cite: 5]
    except:
        st.write("⛳ (Logo File 'GGGOLF-2.png' Not Found)") [cite: 6]

st.markdown("<h1 style='text-align: center;'>GGGolf - No Animals - Winter League</h1>", unsafe_allow_html=True) [cite: 6]
st.divider() [cite: 6]

# DEFINING TABS
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📝 Live Scorecard", "🏆 Leaderboard", "📅 Weekly Log", "📜 League Info", "⚙️ Admin"]) [cite: 6]

# --- TAB 1: LIVE SCORECARD ---
with tab1:
    st.subheader("📊 Points Legend") [cite: 6]
    l_col1, l_col2, l_col3, l_col4, l_col5, l_col6 = st.columns(6) [cite: 6]
    l_col1.caption(f"**Par:** {POINT_VALUES['Par']}") [cite: 6]
    l_col2.caption(f"**Birdie:** {POINT_VALUES['Birdie']}") [cite: 6]
    l_col3.caption(f"**Eagle:** {POINT_VALUES['Eagle']}") [cite: 6]
    l_col4.caption(f"**G-Par:** {POINT_VALUES['Gimme Par']}") [cite: 6]
    l_col5.caption(f"**G-Birdie:** {POINT_VALUES['Gimme Birdie']}") [cite: 6]
    l_col6.caption(f"**G-Eagle:** {POINT_VALUES['Gimme Eagle']}") [cite: 6]
    st.divider() [cite: 7]

    if 'current_selection' not in st.session_state:
        st.session_state.current_selection = "" [cite: 7]

    col1, col2 = st.columns(2) [cite: 7]
    player_select = col1.selectbox("Select Player", PLAYERS) [cite: 7]
    week_select = col2.selectbox("Select Week", range(1, 13)) [cite: 7]
    
    selection_id = f"{player_select}_{week_select}" [cite: 7]
    default_hcp = int(current_handicaps.get(player_select, 0)) [cite: 7]

    # Cumulative Data Fetching Logic
    if st.session_state.current_selection != selection_id:
        st.session_state.scorecard = {'Par': 0, 'Birdie': 0, 'Eagle': 0, 'G_Par': 0, 'G_Birdie': 0, 'G_Eagle': 0} [cite: 7]
        st.session_state['temp_score'] = 45 [cite: 8]
        st.session_state['temp_hcp'] = default_hcp [cite: 8]

        if not df_main.empty:
            history = df_main[(df_main['Player'] == player_select) & (df_main['Week'] <= week_select)] [cite: 8]
            st.session_state.scorecard['Par'] = int(history['Pars_Count'].sum()) [cite: 8]
            st.session_state.scorecard['Birdie'] = int(history['Birdies_Count'].sum()) [cite: 8]
            st.session_state.scorecard['Eagle'] = int(history['Eagle_Count'].sum()) [cite: 8]
            st.session_state.scorecard['G_Par'] = int(history['G_Par_Count'].sum()) [cite: 9]
            st.session_state.scorecard['G_Birdie'] = int(history['G_Birdie_Count'].sum()) [cite: 9]
            st.session_state.scorecard['G_Eagle'] = int(history['G_Eagle_Count'].sum()) [cite: 9]
            
            this_week = df_main[(df_main['Player'] == player_select) & (df_main['Week'] == week_select)] [cite: 9]
            if not this_week.empty:
                st.session_state['temp_score'] = int(this_week.iloc[0]['Total_Score']) [cite: 9]
                st.session_state['temp_hcp'] = int(this_week.iloc[0]['Handicap']) [cite: 10]
        st.session_state.current_selection = selection_id [cite: 10]

    # Reactive Calculation Display
    points_placeholder = st.empty() [cite: 10]
    r1, r2 = st.columns(3), st.columns(3) [cite: 10]
    cats = [("Total Pars", r1[0], 'Par'), ("Total Birdies", r1[1], 'Birdie'), ("Total Eagles", r1[2], 'Eagle'),
            ("Total Gimme Pars", r2[0], 'G_Par'), ("Total Gimme Birdies", r2[1], 'G_Birdie'), ("Total Gimme Eagles", r2[2], 'G_Eagle')] [cite: 10, 11]

    for label, col, key in cats:
        st.session_state.scorecard[key] = col.number_input(label, min_value=0, value=st.session_state.scorecard[key], key=f"val_{key}_{selection_id}") [cite: 11]

    live_cumulative_pts = (
        (st.session_state.scorecard['Par'] * POINT_VALUES["Par"]) + 
        (st.session_state.scorecard['Birdie'] * POINT_VALUES["Birdie"]) + 
        (st.session_state.scorecard['Eagle'] * POINT_VALUES["Eagle"]) +
        (st.session_state.scorecard['G_Par'] * POINT_VALUES["Gimme Par"]) + 
        (st.session_state.scorecard['G_Birdie'] * POINT_VALUES["Gimme Birdie"]) + 
        (st.session_state.scorecard['G_Eagle'] * POINT_VALUES["Gimme Eagle"])
    ) [cite: 11, 12]

    with points_placeholder:
        m1, m2 = st.columns(2) [cite: 12]
        m1.metric("Cumulative Season Points", f"{live_cumulative_pts:.2f}") [cite: 12]
        m2.metric("Week Detail", f"Week {week_select}") [cite: 13]

    st.divider() [cite: 13]
    m1, m2, m3 = st.columns(3) [cite: 13]
    score_in = m1.number_input("Gross Score", min_value=20, value=st.session_state.get('temp_score', 45), key=f"score_{selection_id}") [cite: 13]
    hcp_in = m2.number_input(f"Handicap", value=st.session_state.get('temp_hcp', default_hcp), key=f"hcp_{selection_id}") [cite: 13]
    m3.metric("Net Score", score_in - hcp_in) [cite: 13]

    if st.button("Submit Score"): [cite: 13]
        prev_history = df_main[(df_main['Player'] == player_select) & (df_main['Week'] < week_select)] [cite: 13]
        tw_pars = st.session_state.scorecard['Par'] - prev_history['Pars_Count'].sum() [cite: 13]
        tw_birdies = st.session_state.scorecard['Birdie'] - prev_history['Birdies_Count'].sum() [cite: 13]
        tw_eagles = st.session_state.scorecard['Eagle'] - prev_history['Eagle_Count'].sum() [cite: 14]
        tw_gp = st.session_state.scorecard['G_Par'] - prev_history['G_Par_Count'].sum() [cite: 14]
        tw_gb = st.session_state.scorecard['G_Birdie'] - prev_history['G_Birdie_Count'].sum() [cite: 14]
        tw_ge = st.session_state.scorecard['G_Eagle'] - prev_history['G_Eagle_Count'].sum() [cite: 14]

        save_data(week_select, player_select, tw_pars, tw_birdies, tw_eagles, tw_gp, tw_gb, tw_ge, score_in, hcp_in) [cite: 14]
        st.success(f"Updated! Season Total: {live_cumulative_pts:.2f}") [cite: 14, 15]
        st.rerun() [cite: 15]

# --- TAB 2: LEADERBOARD ---
with tab2:
    if not df_main.empty:
        leaderboard = df_main.groupby('Player').agg({'calc_pts': 'sum', 'Total_Score': 'mean', 'Net_Score': 'mean'}).rename(columns={'calc_pts': 'Points', 'Total_Score': 'Avg Gross', 'Net_Score': 'Avg Net'}).reset_index() [cite: 15]
        leaderboard = leaderboard.round(2).sort_values(by=['Points', 'Avg Net'], ascending=[False, True]) [cite: 15]
        winner = leaderboard.iloc[0] [cite: 15]
        st.success(f"🏆 **Leader:** {winner['Player']} with **{winner['Points']} Points**") [cite: 15]
        st.dataframe(leaderboard, use_container_width=True, hide_index=True) [cite: 15]
        st.divider() [cite: 16]
        st.subheader("📉 Net Score Trending") [cite: 16]
        trend_df = df_main.pivot_table(index='Week', columns='Player', values='Net_Score', aggfunc='mean') [cite: 16]
        trend_df.index = [f"Week {int(i)}" for i in trend_df.index] [cite: 16]
        st.line_chart(trend_df) [cite: 16]
    else:
        st.info("No data found.") [cite: 16]

# --- TAB 3: LOG ---
with tab3:
    st.header("Weekly History") [cite: 16]
    if not df_main.empty:
        cols = ['Week', 'Player', 'Total_Score', 'Handicap', 'Net_Score', 'Pars_Count', 'Birdies_Count', 'Eagle_Count'] [cite: 16, 17]
        st.dataframe(df_main[cols].sort_values(['Week', 'Player'], ascending=[False, True]), hide_index=True, use_container_width=True) [cite: 17]

# --- TAB 4: LEAGUE INFO ---
with tab4:
    st.header("📜 League Information")
    info_subtab = st.radio("Select Category", ["Rules & Regulations", "FAQs"], horizontal=True)
    st.divider()
    
    if info_subtab == "Rules & Regulations":
        st.subheader("📍 Rules and Regulations")
        st.markdown("""
        1. **Attendance**: Players must check in by [Insert Time].
        2. **Scoring**: All scorecards must be submitted via the app by the end of each round.
        3. **Gimmes**: Gimmes are allowed within [Insert Distance].
        4. **Prizes**: Season-end prizes awarded based on total points.
        """)
        # Place additional rules here
    else:
        st.subheader("❓ Frequently Asked Questions")
        with st.expander("How are points calculated?"):
            st.write("Points are based on Pars, Birdies, Eagles, and Gimme versions of each, weighted per the legend on Tab 1.")
        with st.expander("How do I update my handicap?"):
            st.write("Handicaps are updated automatically based on your weekly Net Score performance.")
        # Place additional FAQs here

# --- TAB 5: ADMIN ---
with tab5:
    if st.button("🔄 Force Refresh Database"): [cite: 17]
        st.cache_data.clear() [cite: 17]
        st.rerun() [cite: 17]
