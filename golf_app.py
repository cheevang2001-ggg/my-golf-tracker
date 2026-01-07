import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# --- CONFIGURATION ---
PLAYERS = ["Apex", "Lex Luger", "AI-Player", "Topdawg", "Mkearter_57", "Happy Ending", "LongL", "Txoovnom-Dictator-Chee-Vang"]

# --- STEP 1: CONNECT TO GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    return conn.read(ttl=0)

def save_data(week, player, pars, birdies, score):
    existing_data = load_data()
    
    new_entry = pd.DataFrame([{
        'Week': week,
        'Player': player,
        'Pars_Count': pars,
        'Birdies_Count': birdies,
        'Total_Score': score  # Added this
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
st.title("GGGolf 2026 Winter League Tracker")

tab1, tab2, tab3 = st.tabs(["📝 Enter Stats", "🏆 Leaderboard", "📅 Weekly Log"])

with tab1:
    st.header("Input Weekly Stats")
    with st.form("stat_entry"):
        col1, col2 = st.columns(2)
        player_select = col1.selectbox("Select Player", PLAYERS)
        week_select = col2.selectbox("Select Week", range(1, 13))
        
        st.divider()
        c1, c2, c3 = st.columns(3) # Added a third column
        pars_input = c1.number_input("Total Pars", min_value=0, max_value=18, value=0)
        birdies_input = c2.number_input("Total Birdies", min_value=0, max_value=18, value=0)
        score_input = c3.number_input("Total Score", min_value=20, max_value=150, value=45) # Integer input
        
        if st.form_submit_button("Save to Google Sheets"):
            save_data(week_select, player_select, pars_input, birdies_input, score_input)
            st.success(f"Stats saved for {player_select}!")

with tab2:
    st.header("Season Standings")
    df = load_data()
    if not df.empty:
        # Create a Summary table
        # We sum Birdies/Pars, but AVERAGE the Total Score
        leaderboard = df.groupby('Player').agg({
            'Birdies_Count': 'sum',
            'Pars_Count': 'sum',
            'Total_Score': 'mean' # Average score for the season
        }).rename(columns={'Total_Score': 'Avg_Score'})
        
        # Round the average to 1 decimal point
        leaderboard['Avg_Score'] = leaderboard['Avg_Score'].round(1)
        
        # Sort by Birdies
        leaderboard = leaderboard.sort_values(by='Birdies_Count', ascending=False)
        st.dataframe(leaderboard, use_container_width=True)
        
        # Visual: Who has the lowest average score?
        st.subheader("Lowest Average Scores")
        st.bar_chart(leaderboard['Avg_Score'])
    else:
        st.info("No data found in the spreadsheet.")

with tab3:
    st.header("Full History")
    df = load_data()
    if not df.empty:
        # Show the most recent weeks at the top
        st.dataframe(df.sort_values(by=['Week', 'Player'], ascending=[False, True]), use_container_width=True)