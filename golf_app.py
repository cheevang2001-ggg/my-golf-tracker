import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# --- STEP 1: CONFIGURATION & SETUP ---
st.set_page_config(page_title="GGGolf No Animals Winter League", layout="wide") 

# UPDATED ROSTER
DEFAULT_HANDICAPS = {
    "Cory": 3, "Lex": 7, "Mike": 9,
    "Carter": 5, "Dale": 4, "Long": 6, "Txv": 4,
    "Matt": 2, "NomThai": 4, "VaMeng": 0,
    "Xuka": 0, "Beef": 9
}

# Rank-based points (1st = 100, 2nd = 85, etc.)
FEDEX_POINTS = {
    1: 100, 2: 85, 3: 75, 4: 70, 5: 65, 6: 60,
    7: 55, 8: 50, 9: 45, 10: 40, 11: 35, 12: 30
}

# Static values for personal tracking (Feats)
POINT_VALUES = {
    "Par": 1.85, "Birdie": 2.0, "Eagle": 3.0,
    "Gimme Par": 1.30, "Gimme Birdie": 1.75, "Gimme Eagle": 2.5
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

# --- STEP 2: DATA PROCESSING ---
current_handicaps = get_handicaps()
PLAYERS = sorted(list(current_handicaps.keys()))
df_main = load_data()

if not df_main.empty:
    df_main = df_main.fillna(0)
    # Calculate Weekly Rank based on Net Score (Lower is better)
    # method='min' ensures ties get the same points (e.g., both 1st place get 100)
    df_main['week_rank'] = df_main.groupby('Week')['Net_Score'].rank(ascending=True, method='min')
    df_main['animal_pts'] = df_main['week_rank'].map(FEDEX_POINTS).fillna(0)

# --- UI LOGO & TITLE ---
col_l1, col_l2, col_l3 = st.columns([1,1,1])
with col_l2:
    try:
        st.image("GGGOLF-2.png", width=200)
    except:
        st.write("⛳ GGGOLF")

st.markdown("<h1 style='text-align: center;'>GGGolf - No Animals - Winter League</h1>", unsafe_allow_html=True)
st.divider()

tab1, tab2, tab3, tab4, tab5 = st.tabs(["📝 Live Scorecard", "🏆 No Animals Standing", "📅 Weekly Log", "📜 League Info", "⚙️ Admin"])

# --- TAB 1: SCORECARD ---
with tab1:
    st.subheader("📊 Points Legend")
    l_cols = st.columns(6)
    for i, (k, v) in enumerate(POINT_VALUES.items()):
        l_cols[i].caption(f"**{k}:** {v}")
    
    col1, col2 = st.columns(2)
    player_select = col1.selectbox("Select Player", PLAYERS)
    week_select = col2.selectbox("Select Week", range(1, 13))
    selection_id = f"{player_select}_{week_select}"
    default_hcp = int(current_handicaps.get(player_select, 0))

    if 'current_selection' not in st.session_state or st.session_state.current_selection != selection_id:
        st.session_state.scorecard = {k: 0 for k in POINT_VALUES.keys()}
        if not df_main.empty:
            history = df_main[(df_main['Player'] == player_select) & (df_main['Week'] <= week_select)]
            st.session_state.scorecard = {
                'Par': int(history['Pars_Count'].sum()), 'Birdie': int(history['Birdies_Count'].sum()),
                'Eagle': int(history['Eagle_Count'].sum()), 'Gimme Par': int(history['G_Par_Count'].sum()),
                'Gimme Birdie': int(history['G_Birdie_Count'].sum()), 'Gimme Eagle': int(history['G_Eagle_Count'].sum())
            }
            this_week = df_main[(df_main['Player'] == player_select) & (df_main['Week'] == week_select)]
            st.session_state['temp_score'] = int(this_week.iloc[0]['Total_Score']) if not this_week.empty else 45
            st.session_state['temp_hcp'] = int(this_week.iloc[0]['Handicap']) if not this_week.empty else default_hcp
        st.session_state.current_selection = selection_id

    r1, r2 = st.columns(3), st.columns(3)
    st.session_state.scorecard['Par'] = r1[0].number_input("Total Season Pars", min_value=0, value=st.session_state.scorecard['Par'])
    st.session_state.scorecard['Birdie'] = r1[1].number_input("Total Season Birdies", min_value=0, value=st.session_state.scorecard['Birdie'])
    st.session_state.scorecard['Eagle'] = r1[2].number_input("Total Season Eagles", min_value=0, value=st.session_state.scorecard['Eagle'])
    st.session_state.scorecard['Gimme Par'] = r2[0].number_input("Total Season G-Pars", min_value=0, value=st.session_state.scorecard['Gimme Par'])
    st.session_state.scorecard['Gimme Birdie'] = r2[1].number_input("Total Season G-Birdies", min_value=0, value=st.session_state.scorecard['Gimme Birdie'])
    st.session_state.scorecard['Gimme Eagle'] = r2[2].number_input("Total Season G-Eagles", min_value=0, value=st.session_state.scorecard['Gimme Eagle'])

    st.divider()
    m1, m2, m3 = st.columns(3)
    score_in = m1.number_input("Gross Score (This Week)", min_value=20, value=st.session_state.get('temp_score', 45))
    hcp_in = m2.number_input("Current Handicap", value=st.session_state.get('temp_hcp', default_hcp))
    m3.metric("Net Score", score_in - hcp_in)

    if st.button("🚀 Submit & Sync Data"):
        prev = df_main[(df_main['Player'] == player_select) & (df_main['Week'] < week_select)]
        save_data(week_select, player_select, 
                  st.session_state.scorecard['Par'] - prev['Pars_Count'].sum(),
                  st.session_state.scorecard['Birdie'] - prev['Birdies_Count'].sum(),
                  st.session_state.scorecard['Eagle'] - prev['Eagle_Count'].sum(),
                  st.session_state.scorecard['Gimme Par'] - prev['G_Par_Count'].sum(),
                  st.session_state.scorecard['Gimme Birdie'] - prev['G_Birdie_Count'].sum(),
                  st.session_state.scorecard['Gimme Eagle'] - prev['G_Eagle_Count'].sum(),
                  score_in, hcp_in)
        st.success("Score Updated!")
        st.rerun()

# --- TAB 2: NO ANIMALS STANDING ---
with tab2:
    if not df_main.empty:
        st.header("🏁 No Animals Standing")
        
        standings = df_main.groupby('Player').agg({
            'animal_pts': 'sum', 
            'Net_Score': 'mean'
        }).rename(columns={
            'animal_pts': 'Animal Points', 
            'Net_Score': 'Avg Net'
        }).reset_index()
        
        # Total Animal Points strictly accumulates the Weekly Animal Points
        standings['Total Animal Points'] = standings['Animal Points']
        
        # Sort by Points (Highest) then Avg Net (Lowest)
        standings = standings.round(2).sort_values(by=['Animal Points', 'Avg Net'], ascending=[False, True])
        
        st.dataframe(standings[['Player', 'Animal Points', 'Total Animal Points', 'Avg Net']], 
                     use_container_width=True, hide_index=True)
        
        st.divider()
        st.subheader("📉 Net Score Trending")
        trend_df = df_main.pivot_table(index='Week', columns='Player', values='Net_Score', aggfunc='mean')
        trend_df.index = [f"Week {int(i)}" for i in trend_df.index]
        st.line_chart(trend_df)
    else:
        st.info("No leaderboard data found.")

# --- TAB 3: WEEKLY LOG ---
with tab3:
    st.header("📅 Weekly History")
    if not df_main.empty:
        st.dataframe(df_main.sort_values(['Week', 'Player'], ascending=[False, True]), hide_index=True, use_container_width=True)

# --- TAB 4: LEAGUE INFO ---
with tab4:
    st.header("📜 League Information")
    info_choice = st.radio("Category", ["Rules & Format", "No Animal Rules"], horizontal=True)
    st.divider()
    if info_choice == "Rules & Format":
        st.markdown("""
        **Who are my playing partners each week?** Randomized by picking playing cards at **5:45pm**.
        
        **Late Policy:** Round starts at **6:00pm**. If arriving after 6PM, you are paused until the hole is finished. 
        If not arrived by Hole 4, you receive a DNF.
        
        **Makeups:** Must be scheduled with PHGC and completed by the following Friday at 12AM.
        """)
    else:
        st.subheader("🦁 Don't Be An Animal")
        st.info("'From John Wick: Exactly. Rules. Without them, we'd live with the animals.'")
        st.markdown("""
        **Penalty:** Drink Alcohol, 5 Diamond Pushups, or 15 Jumping Jacks.
        
        * **Hitting Zone:** Step off mat without returning ball.
        * **First Putt:** Player makes first putt in-hole = Everyone else drinks.
        * **Chips:** Player chips in-hole = Everyone else drinks 1/2.
        * **Mulligans:** Owe 1 round of beer.
        * **Rules:** Slam a beer to make or cancel a rule.
        """)

# --- TAB 5: ADMIN ---
with tab5:
    if st.button("🔄 Force Refresh Sync"):
        st.cache_data.clear()
        st.rerun()
