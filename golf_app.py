import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# --- CONFIGURATION ---
# Your specific player list
PLAYERS = ["Cory", "Lex", "John", "Topdawg", "Carter", "Dale", "Long", "Txv"]

# --- STEP 1: CONNECT TO GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    # Read the existing data from the Google Sheet
    # The 'spreadsheet' argument will be defined in your Streamlit secrets
    return conn.read(ttl=0) # ttl=0 ensures we always get the freshest data

def save_data(week, player, pars, birdies):
    existing_data = load_data()
    
    # Create the new row of data
    new_entry = pd.DataFrame([{
        'Week': week,
        'Player': player,
        'Pars_Count': pars,
        'Birdies_Count': birdies
    }])
    
    # FIX: Check if the sheet has any data yet. 
    # If 'Week' isn't in the columns, we just skip the "filtering" part.
    if not existing_data.empty and 'Week' in existing_data.columns:
        # Remove any existing entry for this player/week to allow updates
        updated_df = existing_data[~((existing_data['Week'] == week) & (existing_data['Player'] == player))]
        final_df = pd.concat([updated_df, new_entry], ignore_index=True)
    else:
        # If it's the first time, our final data is just the new entry
        final_df = new_entry
    
    # Update the Google Sheet
    conn.update(data=final_df)
    
    # Remove any existing entry for this player/week to allow updates
    updated_df = existing_data[~((existing_data['Week'] == week) & (existing_data['Player'] == player))]
    
    # Combine and update the sheet
    updated_df = pd.concat([updated_df, new_entry], ignore_index=True)
    conn.update(data=updated_df)

# --- STEP 2: APP LAYOUT ---
st.title("GGGolf Winter League Tracker")

tab1, tab2, tab3 = st.tabs(["📝 Enter Stats", "🏆 Leaderboard", "📅 Weekly Log"])

with tab1:
    st.header("Input Weekly Stats")
    with st.form("stat_entry"):
        col1, col2 = st.columns(2)
        player_select = col1.selectbox("Select Player", PLAYERS)
        week_select = col2.selectbox("Select Week", range(1, 13))
        
        st.divider()
        c1, c2 = st.columns(2)
        pars_input = c1.number_input("Total Pars", min_value=0, max_value=18, value=0)
        birdies_input = c2.number_input("Total Birdies", min_value=0, max_value=18, value=0)
        
        if st.form_submit_button("Save to Google Sheets"):
            save_data(week_select, player_select, pars_input, birdies_input)
            st.success(f"Stats saved for {player_select}!")

with tab2:
    st.header("Season Standings")
    df = load_data()
    if not df.empty:
        # Group and sum for the leaderboard
        leaderboard = df.groupby('Player')[['Pars_Count', 'Birdies_Count']].sum()
        leaderboard = leaderboard.sort_values(by='Birdies_Count', ascending=False)
        st.dataframe(leaderboard, use_container_width=True)
        st.bar_chart(leaderboard['Birdies_Count'])
    else:
        st.info("No data found in the spreadsheet.")

with tab3:
    st.header("Full History")
    df = load_data()
    if not df.empty:
        st.dataframe(df.sort_values(by=['Week', 'Player'], ascending=[False, True]))