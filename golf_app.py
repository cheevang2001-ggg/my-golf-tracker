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

# FedEx Cup Style Point Distribution for 12 Players
FEDEX_POINTS = {
    1: 100, 2: 85, 3: 75, 4: 70, 5: 65, 6: 60,
    7: 55, 8: 50, 9: 45, 10: 40, 11: 35, 12: 30
}

POINT_VALUES = {
    "Par": 1.85, "Birdie": 2.0, "Eagle": 3.0,
    "Gimme Par": 1.30, "Gimme Birdie": 1.75, "Gimme Eagle": 2.5
}

conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=600)
def load_data():
    return conn.read()

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

# --- DATA PREP & FEDEX LOGIC ---
df_main = load_data()

if not df_main.empty:
    df_main = df_main.fillna(0)
    # Calculate Round Points (Performance Feats)
    df_main['round_pts'] = (
        (df_main['Pars_Count'] * POINT_VALUES["Par"]) + 
        (df_main['Birdies_Count'] * POINT_VALUES["Birdie"]) + 
        (df_main['Eagle_Count'] * POINT_VALUES["Eagle"]) +
        (df_main['G_Par_Count'] * POINT_VALUES["Gimme Par"]) + 
        (df_main['G_Birdie_Count'] * POINT_VALUES["Gimme Birdie"]) + 
        (df_main['G_Eagle_Count'] * POINT_VALUES["Gimme Eagle"])
    )
    
    # Calculate Weekly Rank Points (FedEx Style)
    # We rank players within each week based on their Round Points
    df_main['week_rank'] = df_main.groupby('Week')['round_pts'].rank(ascending=False, method='min')
    df_main['fedex_pts'] = df_main['week_rank'].map(FEDEX_POINTS).fillna(0)

# --- UI DISPLAY ---
st.markdown("<h1 style='text-align: center;'>GGGolf - No Animals - Winter League</h1>", unsafe_allow_html=True)
st.divider()

tab1, tab2, tab3, tab4, tab5 = st.tabs(["📝 Live Scorecard", "🏆 Leaderboard", "📅 Weekly Log", "📜 League Info", "⚙️ Admin"])

with tab1:
    # (Scorecard logic remains same as previous version)
    st.info("Input weekly stats here to update the FedEx Cup Standings.")
    # ... [Rest of Scorecard Code] ...

with tab2:
    st.header("🏁 Season Standings")
    
    if not df_main.empty:
        # Create FedEx Standings Table
        standings = df_main.groupby('Player').agg({
            'fedex_pts': 'sum', 
            'round_pts': 'sum',
            'Net_Score': 'mean'
        }).rename(columns={
            'fedex_pts': 'FedEx Season Points',
            'round_pts': 'Total Feat Points',
            'Net_Score': 'Avg Net'
        }).sort_values('FedEx Season Points', ascending=False)
        
        col_rank, col_stat = st.columns([2, 1])
        
        with col_rank:
            st.subheader("🏆 FedEx Cup Rank")
            st.dataframe(standings.style.highlight_max(axis=0, subset=['FedEx Season Points']), use_container_width=True)
        
        with col_stat:
            st.subheader("📈 Quick Stats")
            top_player = standings.index[0]
            st.metric("Current Leader", top_player)
            st.metric("Points Lead", int(standings.iloc[0,0] - standings.iloc[1,0]) if len(standings) > 1 else 0)

        st.divider()
        st.subheader("Weekly Points Breakdown")
        weekly_breakdown = df_main.pivot(index='Week', columns='Player', values='fedex_pts').fillna(0)
        st.bar_chart(weekly_breakdown)
    else:
        st.info("No scores recorded yet.")

with tab4:
    st.header("📜 League Information")
    # Add FedEx Cup details to the info tab
    with st.expander("How does the FedEx Cup Point System work?"):
        st.write("Each week, players are ranked based on their total feat points (Pars, Birdies, etc.). Points are then awarded as follows:")
        point_df = pd.DataFrame(list(FEDEX_POINTS.items()), columns=['Rank', 'Points'])
        st.table(point_df.set_index('Rank'))

# (Admin and Log tabs remain unchanged)