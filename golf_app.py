import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# --- STEP 1: CONFIGURATION & SETUP ---
st.set_page_config(page_title="GGGolf League", page_icon="⛳") 

DEFAULT_HANDICAPS = {
    "Cory": 5, "Lex": 8, "John": 10, "Topdawg": 12,
    "Carter": 7, "Dale": 15, "Long": 9, "Txv": 11
}

conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    return conn.read(ttl=0)

def get_handicaps():
    df = load_data()
    if not df.empty and 'Handicap' in df.columns:
        latest = df.sort_values('Week').groupby('Player')['Handicap'].last().to_dict()
        for player in DEFAULT_HANDICAPS:
            if player not in latest:
                latest[player] = DEFAULT_HANDICAPS[player]
        return latest
    return DEFAULT_HANDICAPS

def save_data(week, player, pars, birdies, score, hcp_val):
    existing_data = load_data()
    net_score = score - hcp_val
    
    new_entry = pd.DataFrame([{
        'Week': week, 'Player': player,
        'Pars_Count': pars, 'Birdies_Count': birdies,
        'Total_Score': score, 'Handicap': hcp_val,
        'Net_Score': net_score
    }])
    
    if not existing_data.empty and 'Week' in existing_data.columns:
        updated_df = existing_data[~((existing_data['Week'] == week) & (existing_data['Player'] == player))]
        final_df = pd.concat([updated_df, new_entry], ignore_index=True)
    else:
        final_df = new_entry
    
    conn.update(data=final_df)

# --- LOGO & TITLE ---
col1, col2, col3 = st.columns([1,1,1])
with col2:
    try:
        st.image("GGGOLF-2.png", width=150)
    except:
        st.write("⛳")

st.markdown("<h1 style='text-align: center;'>GGGolf 2026 Winter League</h1>", unsafe_allow_html=True)
st.divider()

# --- STEP 2: APP LAYOUT ---
tab1, tab2, tab3, tab4 = st.tabs(["📝 Enter Stats", "🏆 Leaderboard", "📅 Weekly Log", "⚙️ Admin"])

current_handicaps = get_handicaps()
PLAYERS = sorted(list(current_handicaps.keys()))

with tab1:
    st.header("Input Weekly Stats")
    
    # Selection outside form for instant reactivity
    col1, col2 = st.columns(2)
    player_select = col1.selectbox("Select Player", PLAYERS)
    week_select = col2.selectbox("Select Week", range(1, 13))
    
    default_hcp = int(current_handicaps.get(player_select, 0))
    
    with st.form("stat_entry", clear_on_submit=True):
        hcp_input = st.number_input(f"Handicap for {player_select}", value=default_hcp, key=f"hcp_{player_select}")
        
        st.divider()
        c1, c2, c3 = st.columns(3)
        pars_input = c1.number_input("Total Pars", min_value=0, max_value=18, value=0)
        birdies_input = c2.number_input("Total Birdies", min_value=0, max_value=18, value=0)
        score_input = c3.number_input("Gross Score", min_value=20, max_value=150, value=45)
        
        # --- NEW: VISIBLE NET SCORE PREVIEW ---
        calculated_net = score_input - hcp_input
        st.metric(label="Calculated Net Score", value=calculated_net)
        
        submit_button = st.form_submit_button("Save to Google Sheets")
        
        if submit_button:
            save_data(week_select, player_select, pars_input, birdies_input, score_input, hcp_input)
            st.success(f"✅ Saved! {player_select}'s Net Score: {calculated_net}")
            st.rerun()

with tab2:
    st.header("Season Standings")
    df = load_data()
    if not df.empty:
        df['Points'] = (df['Birdies_Count'] * 2) + (df['Pars_Count'] * 1)
        
        # Aggregate stats including the average Net Score
        leaderboard = df.groupby('Player').agg({
            'Birdies_Count': 'sum',
            'Pars_Count': 'sum',
            'Points': 'sum',
            'Total_Score': 'mean', # Gross Avg
            'Net_Score': 'mean'    # Net Avg
        }).rename(columns={'Total_Score': 'Avg Gross', 'Net_Score': 'Avg Net'})
        
        leaderboard = leaderboard.round(1)
        # Sort by Points (descending) and Net Score (ascending)
        leaderboard = leaderboard.sort_values(by=['Points', 'Avg Net'], ascending=[False, True])
        
        st.dataframe(leaderboard, use_container_width=True)
    else:
        st.info("No data found.")

with tab3:
    st.header("Full History")
    df = load_data()
    if not df.empty:
        # Reordering columns to put Net Score in view
        display_df = df[['Week', 'Player', 'Total_Score', 'Handicap', 'Net_Score', 'Birdies_Count', 'Pars_Count']]
        st.dataframe(display_df.sort_values(by=['Week', 'Player'], ascending=[False, True]), use_container_width=True)

with tab4:
    st.header("League Settings")
    st.write(current_handicaps)