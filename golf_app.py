import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# --- STEP 1: CONFIGURATION & SETUP ---
st.set_page_config(page_title="GGGolf No Animals Winter League", layout="wide") 

DEFAULT_HANDICAPS = {
    "Cory": 3, "Lex": 7, "John": 20, "Mike": 9,
    "Carter": 5, "Dale": 4, "Long": 6, "Txv": 4,
    "Matt": 2, "NomThai": 4, "VaMeng": 0
}

# UPDATED: Static Point Values (Gimme Par changed to 1.30)
POINT_VALUES = {
    "Par": 1.85, 
    "Birdie": 2.0, 
    "Eagle": 3.5,
    "Gimme Par": 1.30,  # Changed from 1.0 to 1.30
    "Gimme Birdie": 1.75, 
    "Gimme Eagle": 2.5
}

conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=600)
def load_data():
    return conn.read()

def get_handicaps():
    df = load_data() 
    if not df.empty and 'Handicap' in df.columns:
        latest = df.sort_values('Week').groupby('Player')['Handicap'].last().to_dict()
        for player in DEFAULT_HANDICAPS:
            if player not in latest:
                latest[player] = DEFAULT_HANDICAPS[player]
        return latest
    return DEFAULT_HANDICAPS

def save_data(week, player, pars, birdies, eagles, g_pars, g_birdies, g_eagles, score, hcp_val):
    st.cache_data.clear()
    existing_data = conn.read(ttl=0) 
    
    new_entry = pd.DataFrame([{
        'Week': week, 'Player': player,
        'Pars_Count': pars, 'Birdies_Count': birdies, 'Eagle_Count': eagles,
        'G_Par_Count': g_pars, 'G_Birdie_Count': g_birdies, 'G_Eagle_Count': g_eagles,
        'Total_Score': score, 'Handicap': hcp_val, 'Net_Score': score - hcp_val
    }])
    
    if not existing_data.empty:
        updated_df = existing_data[~((existing_data['Week'] == week) & (existing_data['Player'] == player))]
        final_df = pd.concat([updated_df, new_entry], ignore_index=True)
    else:
        final_df = new_entry
    
    conn.update(data=final_df)
    st.cache_data.clear()

# --- STEP 2: LOAD DATA ---
current_handicaps = get_handicaps()
PLAYERS = sorted(list(current_handicaps.keys()))
df_main = load_data()

# Pre-calculate global points with the new 1.30 value
if not df_main.empty:
    df_main = df_main.fillna(0)
    df_main['calc_pts'] = (
        (df_main['Pars_Count'] * POINT_VALUES["Par"]) + 
        (df_main['Birdies_Count'] * POINT_VALUES["Birdie"]) + 
        (df_main['Eagle_Count'] * POINT_VALUES["Eagle"]) +
        (df_main['G_Par_Count'] * POINT_VALUES["Gimme Par"]) + 
        (df_main['G_Birdie_Count'] * POINT_VALUES["Gimme Birdie"]) + 
        (df_main['G_Eagle_Count'] * POINT_VALUES["Gimme Eagle"])
    )

# --- LOGO & TITLE ---
col_l1, col_l2, col_l3 = st.columns([1,1,1])
with col_l2:
    try:
        st.image("GGGOLF-2.png", width=200)
    except:
        st.write("⛳ (Logo File 'GGGOLF-2.png' Not Found)")

st.markdown("<h1 style='text-align: center;'>GGGolf No Animals Winter League</h1>", unsafe_allow_html=True)
st.divider()

tab1, tab2, tab3, tab4 = st.tabs(["📝 Live Scorecard", "🏆 Leaderboard", "📅 Weekly Log", "⚙️ Admin"])

# --- TAB 1: LIVE SCORECARD ---
with tab1:
    # 1. UPDATED LEGEND (Static Display)
    st.subheader("📊 Points Legend")
    l_col1, l_col2, l_col3, l_col4, l_col5, l_col6 = st.columns(6)
    l_col1.caption(f"**Par:** {POINT_VALUES['Par']}")
    l_col2.caption(f"**Birdie:** {POINT_VALUES['Birdie']}")
    l_col3.caption(f"**Eagle:** {POINT_VALUES['Eagle']}")
    l_col4.caption(f"**G-Par:** {POINT_VALUES['Gimme Par']}") # Shows 1.3
    l_col5.caption(f"**G-Birdie:** {POINT_VALUES['Gimme Birdie']}")
    l_col6.caption(f"**G-Eagle:** {POINT_VALUES['Gimme Eagle']}")
    st.divider()

    if 'current_selection' not in st.session_state:
        st.session_state.current_selection = ""

    col1, col2 = st.columns(2)
    player_select = col1.selectbox("Select Player", PLAYERS)
    week_select = col2.selectbox("Select Week", range(1, 13))
    
    selection_id = f"{player_select}_{week_select}"
    default_hcp = int(current_handicaps.get(player_select, 0))

    # 2. Cumulative Data Fetching
    if st.session_state.current_selection != selection_id:
        st.session_state.scorecard = {'Par': 0, 'Birdie': 0, 'Eagle': 0, 'G_Par': 0, 'G_Birdie': 0, 'G_Eagle': 0}
        st.session_state['temp_score'] = 45
        st.session_state['temp_hcp'] = default_hcp

        if not df_main.empty:
            history = df_main[(df_main['Player'] == player_select) & (df_main['Week'] <= week_select)]
            st.session_state.scorecard['Par'] = int(history['Pars_Count'].sum())
            st.session_state.scorecard['Birdie'] = int(history['Birdies_Count'].sum())
            st.session_state.scorecard['Eagle'] = int(history['Eagle_Count'].sum())
            st.session_state.scorecard['G_Par'] = int(history['G_Par_Count'].sum())
            st.session_state.scorecard['G_Birdie'] = int(history['G_Birdie_Count'].sum())
            st.session_state.scorecard['G_Eagle'] = int(history['G_Eagle_Count'].sum())
            
            this_week = df_main[(df_main['Player'] == player_select) & (df_main['Week'] == week_select)]
            if not this_week.empty:
                st.session_state['temp_score'] = int(this_week.iloc[0]['Total_Score'])
                st.session_state['temp_hcp'] = int(this_week.iloc[0]['Handicap'])
        
        st.session_state.current_selection = selection_id

    # 3. Dynamic Calculation Area
    # We define the metrics here so they update AFTER inputs are read
    points_placeholder = st.empty()

    r1, r2 = st.columns(3), st.columns(3)
    cats = [("Total Pars", r1[0], 'Par'), ("Total Birdies", r1[1], 'Birdie'), ("Total Eagles", r1[2], 'Eagle'),
            ("Total Gimme Pars", r2[0], 'G_Par'), ("Total Gimme Birdies", r2[1], 'G_Birdie'), ("Total Gimme Eagles", r2[2], 'G_Eagle')]

    for label, col, key in cats:
        st.session_state.scorecard[key] = col.number_input(
            label, min_value=0, 
            value=st.session_state.scorecard[key], 
            key=f"val_{key}_{selection_id}"
        )

    # RE-CALCULATE LIVE
    live_cumulative_pts = (
        (st.session_state.scorecard['Par'] * POINT_VALUES["Par"]) + 
        (st.session_state.scorecard['Birdie'] * POINT_VALUES["Birdie"]) + 
        (st.session_state.scorecard['Eagle'] * POINT_VALUES["Eagle"]) +
        (st.session_state.scorecard['G_Par'] * POINT_VALUES["Gimme Par"]) + 
        (st.session_state.scorecard['G_Birdie'] * POINT_VALUES["Gimme Birdie"]) + 
        (st.session_state.scorecard['G_Eagle'] * POINT_VALUES["Gimme Eagle"])
    )

    with points_placeholder:
        m1, m2 = st.columns(2)
        m1.metric("Cumulative Season Points", f"{live_cumulative_pts:.2f}")
        m2.metric("Week Detail", f"Week {week_select}")

    st.divider()
    m1, m2, m3 = st.columns(3)
    score_in = m1.number_input("Gross Score", min_value=20, value=st.session_state.get('temp_score', 45), key=f"score_{selection_id}")
    hcp_in = m2.number_input(f"Handicap", value=st.session_state.get('temp_hcp', default_hcp), key=f"hcp_{selection_id}")
    m3.metric("Net Score", score_in - hcp_in)

    if st.button("Submit Score"):
        prev_history = df_main[(df_main['Player'] == player_select) & (df_main['Week'] < week_select)]
        
        tw_pars = st.session_state.scorecard['Par'] - prev_history['Pars_Count'].sum()
        tw_birdies = st.session_state.scorecard['Birdie'] - prev_history['Birdies_Count'].sum()
        tw_eagles = st.session_state.scorecard['Eagle'] - prev_history['Eagle_Count'].sum()
        tw_gp = st.session_state.scorecard['G_Par'] - prev_history['G_Par_Count'].sum()
        tw_gb = st.session_state.scorecard['G_Birdie'] - prev_history['G_Birdie_Count'].sum()
        tw_ge = st.session_state.scorecard['G_Eagle'] - prev_history['G_Eagle_Count'].sum()

        save_data(week_select, player_select, tw_pars, tw_birdies, tw_eagles, tw_gp, tw_gb, tw_ge, score_in, hcp_in)
        st.success(f"Updated! Season Total for {player_select}: {live_cumulative_pts:.2f}")
        st.rerun()

# --- TAB 2: LEADERBOARD ---
with tab2:
    if not df_main.empty:
        leaderboard = df_main.groupby('Player').agg({'calc_pts': 'sum', 'Total_Score': 'mean', 'Net_Score': 'mean'}).rename(columns={'calc_pts': 'Points', 'Total_Score': 'Avg Gross', 'Net_Score': 'Avg Net'}).reset_index()
        leaderboard = leaderboard.round(2).sort_values(by=['Points', 'Avg Net'], ascending=[False, True])

        winner = leaderboard.iloc[0]
        st.success(f"🏆 **Current Leader:** {winner['Player']} with **{winner['Points']} Points**")
        st.dataframe(leaderboard, use_container_width=True, hide_index=True)
        
        st.divider()
        st.subheader("📉 Net Score Trending")
        trend_df = df_main.pivot_table(index='Week', columns='Player', values='Net_Score', aggfunc='mean')
        trend_df.index = [f"Week {int(i)}" for i in trend_df.index]
        st.line_chart(trend_df)
    else:
        st.info("No data found.")

# --- TAB 3: HISTORY ---
with tab3:
    st.header("Weekly History")
    if not df_main.empty:
        cols = ['Week', 'Player', 'Total_Score', 'Handicap', 'Net_Score', 'Pars_Count', 'Birdies_Count', 'Eagle_Count']
        st.dataframe(df_main[cols].sort_values(['Week', 'Player'], ascending=[False, True]), hide_index=True, use_container_width=True)

# --- TAB 4: ADMIN ---
with tab4:
    if st.button("🔄 Force Refresh Database"):
        st.cache_data.clear()
        st.rerun()






