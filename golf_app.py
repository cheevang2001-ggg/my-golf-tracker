import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# --- CONFIGURATION ---
# UPDATE THESE NUMBERS WHENEVER HANDICAPS CHANGE
HANDICAPS = {
    "Cory": 5,
    "Lex": 8,
    "John": 10,
    "Topdawg": 12,
    "Carter": 7,
    "Dale": 15,
    "Long": 9,
    "Txv": 11
}

PLAYERS = list(HANDICAPS.keys())

# --- STEP 1: CONNECT TO GOOGLE SHEETS ---
st.set_page_config(page_title="GGG League", page_icon="⛳") 
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    return conn.read(ttl=0)

def save_data(week, player, pars, birdies, score):
    existing_data = load_data()
    
    # CALCULATE HANDICAP MATH
    hcp = HANDICAPS.get(player, 0)
    net_score = score - hcp
    
    new_entry = pd.DataFrame([{
        'Week': week,
        'Player': player,
        'Pars_Count': pars,
        'Birdies_Count': birdies,
        'Total_Score': score,
        'Handicap': hcp,      # Saved for record-keeping
        'Net_Score': net_score # The handicapped score
    }])
    
    if not existing_data.empty and 'Week' in existing_data.columns:
        updated_df = existing_data[~((existing_data['Week'] == week) & (existing_data['Player'] == player))]
        final_df = pd.concat([updated_df, new_entry], ignore_index=True)
    else:
        final_df = new_entry
    
    conn.update(data=final_df)

    # --- LOGO SECTION ---
# This opens the image file you uploaded to GitHub
col1, col2, col3 = st.columns([1,1,1]) # Creates 3 columns

with col2: # This puts the logo in the middle column
    st.image("GGGOLF-2.png", width=150) # You can adjust the width (in pixels) here


# --- STEP 2: APP LAYOUT ---
# (Logo code here as you had it before)
st.title("GGGolf 2026 Winter League Tracker")

tab1, tab2, tab3 = st.tabs(["📝 Enter Stats", "🏆 Leaderboard", "📅 Weekly Log"])

with tab1:
    st.header("Input Weekly Stats")
    with st.form("stat_entry"):
        col1, col2 = st.columns(2)
        player_select = col1.selectbox("Select Player", PLAYERS)
        week_select = col2.selectbox("Select Week", range(1, 13))
        
        # Display current handicap so you know it's working
        st.info(f"Current Handicap for {player_select}: {HANDICAPS[player_select]}")
        
        st.divider()
        c1, c2, c3 = st.columns(3)
        pars_input = c1.number_input("Total Pars", min_value=0, max_value=18, value=0)
        birdies_input = c2.number_input("Total Birdies", min_value=0, max_value=18, value=0)
        score_input = c3.number_input("Gross Score (Raw)", min_value=20, max_value=150, value=45)
        
        if st.form_submit_button("Save to Google Sheets"):
            save_data(week_select, player_select, pars_input, birdies_input, score_input)
            st.success(f"Stats saved! Net Score: {score_input - HANDICAPS[player_select]}")

with tab2:
    st.header("Season Standings")
    df = load_data()
    if not df.empty:
        # Leaderboard now focuses on NET score (Handicapped)
        leaderboard = df.groupby('Player').agg({
            'Birdies_Count': 'sum',
            'Pars_Count': 'sum',
            'Net_Score': 'mean' 
        }).rename(columns={'Net_Score': 'Avg_Net_Score'})
        
        leaderboard['Avg_Net_Score'] = leaderboard['Avg_Net_Score'].round(1)
        leaderboard = leaderboard.sort_values(by='Avg_Net_Score', ascending=True) # Lowest score wins!
        
        st.dataframe(leaderboard, use_container_width=True)
        
        st.subheader("Net Score Race (Lowest Wins)")
        st.bar_chart(leaderboard['Avg_Net_Score'])
    else:
        st.info("No data found.")

with tab3:
    st.header("Full History")
    df = load_data()
    if not df.empty:
        # Show all columns so you can see the Gross vs Net
        st.dataframe(df.sort_values(by=['Week', 'Player'], ascending=[False, True]), use_container_width=True)