import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# --- STEP 1: CONFIGURATION & SETUP ---
st.set_page_config(page_title="GGGolf League", page_icon="⛳") 

# Initial handicaps - The app will use these if the "Handicaps" sheet is empty
DEFAULT_HANDICAPS = {
    "Cory": 5, "Lex": 8, "John": 10, "Topdawg": 12,
    "Carter": 7, "Dale": 15, "Long": 9, "Txv": 11
}

conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    return conn.read(ttl=0)

# --- NEW: FUNCTIONS TO MANAGE HANDICAPS VIA GOOGLE SHEETS ---
def get_handicaps():
    df = load_data()
    if not df.empty and 'Handicap' in df.columns:
        # Get the most recent handicap assigned to each player
        latest = df.sort_values('Week').groupby('Player')['Handicap'].last().to_dict()
        # Merge with defaults for any player not yet in the sheet
        for player in DEFAULT_HANDICAPS:
            if player not in latest:
                latest[player] = DEFAULT_HANDICAPS[player]
        return latest
    return DEFAULT_HANDICAPS

def save_data(week, player, pars, birdies, score, hcp_override):
    existing_data = load_data()
    net_score = score - hcp_override
    
    new_entry = pd.DataFrame([{
        'Week': week, 'Player': player,
        'Pars_Count': pars, 'Birdies_Count': birdies,
        'Total_Score': score, 'Handicap': hcp_override,
        'Net_Score': net_score
    }])
    
    if not existing_data.empty and 'Week' in existing_data.columns:
        updated_df = existing_data[~((existing_data['Week'] == week) & (existing_data['Player'] == player))]
        final_df = pd.concat([updated_df, new_entry], ignore_index=True)
    else:
        final_df = new_entry
    
    conn.update(data=final_df)

# --- LOGO SECTION ---
col1, col2, col3 = st.columns([1,1,1])
with col2:
    try:
        st.image("GGGOLF-2.png", width=150)
    except:
        st.write("⛳")

st.markdown("<h1 style='text-align: center;'>GGGolf 2026 Winter League</h1>", unsafe_allow_html=True)

# --- STEP 2: APP LAYOUT ---
tab1, tab2, tab3, tab4 = st.tabs(["📝 Enter Stats", "🏆 Leaderboard", "📅 Weekly Log", "⚙️ Admin"])

current_handicaps = get_handicaps()
PLAYERS = sorted(list(current_handicaps.keys()))

with tab1:
    st.header("Input Weekly Stats")
    with st.form("stat_entry"):
        col1, col2 = st.columns(2)
        player_select = col1.selectbox("Select Player", PLAYERS)
        week_select = col2.selectbox("Select Week", range(1, 13))
        
        # Use the handicap from the system, but allow a manual override if needed
        hcp_val = st.number_input(f"Handicap for {player_select}", value=int(current_handicaps[player_select]))
        
        st.divider()
        c1, c2, c3 = st.columns(3)
        pars_input = c1.number_input("Total Pars", min_value=0, max_value=18, value=0)
        birdies_input = c2.number_input("Total Birdies", min_value=0, max_value=18, value=0)
        score_input = c3.number_input("Gross Score", min_value=20, max_value=150, value=45)
        
        if st.form_submit_button("Save to Google Sheets"):
            save_data(week_select, player_select, pars_input, birdies_input, hcp_val)
            st.success(f"Stats saved! Net Score: {score_input - hcp_val}")

with tab2:
    st.header("Season Standings")
    df = load_data()
    if not df.empty:
        # Calculation: Birdies = 2pts, Pars = 1pt
        df['Points'] = (df['Birdies_Count'] * 2) + (df['Pars_Count'] * 1)
        
        leaderboard = df.groupby('Player').agg({
            'Birdies_Count': 'sum',
            'Pars_Count': 'sum',
            'Points': 'sum',
            'Net_Score': 'mean' 
        }).rename(columns={'Net_Score': 'Avg_Net'})
        
        leaderboard['Avg_Net'] = leaderboard['Avg_Net'].round(1)
        leaderboard = leaderboard.sort_values(by='Points', ascending=False)
        
        st.dataframe(leaderboard, use_container_width=True)
        
        st.subheader("Performance Race")
        st.bar_chart(leaderboard['Points'])
    else:
        st.info("No data found.")

with tab3:
    st.header("Full History")
    df = load_data()
    if not df.empty:
        st.dataframe(df.sort_values(by=['Week', 'Player'], ascending=[False, True]), use_container_width=True)

with tab4:
    st.header("League Settings")
    st.write("Current Handicaps being used by the system:")
    st.json(current_handicaps)
    st.info("To change a handicap permanently for the next entry, simply adjust the 'Handicap' number in the 'Enter Stats' tab when saving a new week. The system will remember the most recent handicap used for each player.")