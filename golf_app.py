import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# --- STEP 1: CONFIGURATION & SETUP ---
st.set_page_config(page_title="GGGolf League", page_icon="⛳") 

DEFAULT_HANDICAPS = {
    "Cory": 3, "Lex": 5, "John": 27, "Mike": 8,
    "Carter": 5, "Dale": 3, "Long": 5, "Txv": 3,
     "Matt": 1, "NomThai": 3, "VaMeng": 0
}

conn = st.connection("gsheets", type=GSheetsConnection)

# 1. CACHE THIS: Only ask Google once every 10 minutes (ttl=600)
# This prevents the "Rate Limit" error.
@st.cache_data(ttl=600)
def load_data():
    return conn.read()

# 2. FIX: This now uses 'load_data()' instead of 'conn.read(ttl=0)'
# It reads from the memory, not the internet.
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
    # We clear the cache immediately so the next read is fresh
    st.cache_data.clear()
    
    # We force a fresh read ONLY when saving to ensure we don't overwrite data
    existing_data = conn.read(ttl=0) 
    
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
    
    # CRITICAL: This clears the memory so the Leaderboard updates immediately
    st.cache_data.clear()

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
    
    # --- SECTION 1: PLAYER SELECTION ---
    col1, col2 = st.columns(2)
    player_select = col1.selectbox("Select Player", PLAYERS)
    week_select = col2.selectbox("Select Week", range(1, 13))
    
    # Get the saved handicap for this player
    default_hcp = int(current_handicaps.get(player_select, 0))
    
    st.divider()
    
    # --- SECTION 2: LIVE MATH INPUTS (Outside the Form) ---
    # Because these are outside the form, changing them triggers an instant update.
    c1, c2, c3 = st.columns([1, 1, 1])
    
    with c1:
        score_input = st.number_input("Gross Score", min_value=20, max_value=150, value=45)
    
    with c2:
        hcp_input = st.number_input(
            f"Handicap for {player_select}", 
            value=default_hcp, 
            key=f"hcp_box_{player_select}" # Unique key ensures it updates when player changes
        )
        
    with c3:
        # LIVE CALCULATION
        calculated_net = score_input - hcp_input
        st.metric(label="Calculated Net Score", value=calculated_net)

    st.divider()

    # --- SECTION 3: STATS FORM ---
    with st.form("stat_entry", clear_on_submit=True):
        st.caption("Enter stats below and click save:")
        col_a, col_b = st.columns(2)
        pars_input = col_a.number_input("Total Pars", min_value=0, max_value=18, value=0)
        birdies_input = col_b.number_input("Total Birdies", min_value=0, max_value=18, value=0)
        
        submit_button = st.form_submit_button("Save to Google Sheets")
        
        if submit_button:
            save_data(week_select, player_select, pars_input, birdies_input, score_input, hcp_input)
            st.success(f"✅ Saved! {player_select}'s Net Score: {calculated_net}")
            st.rerun()

with tab2:
    st.header("Season Standings")
    df = load_data()
    
    if not df.empty:
        # 1. Do the math
        df['Points'] = (df['Birdies_Count'] * 2) + (df['Pars_Count'] * 1)

        # 2. Build the leaderboard table
        leaderboard = df.groupby('Player').agg({
            'Birdies_Count': 'sum',
            'Pars_Count': 'sum',
            'Points': 'sum',
            'Total_Score': 'mean', 
            'Net_Score': 'mean'   
        }).rename(columns={'Total_Score': 'Avg Gross', 'Net_Score': 'Avg Net'})
        
        # 3. FIX: Move 'Player' from the hidden index back into a visible column
        leaderboard = leaderboard.reset_index()
        
        # 4. Clean up the numbers
        leaderboard = leaderboard.round(1)
        
        # 5. Sort the players
        leaderboard = leaderboard.sort_values(by=['Points', 'Avg Net'], ascending=[False, True])
        
        # 6. Display the table
        st.dataframe(
            leaderboard, 
            use_container_width=True,
            hide_index=True # Now it hides the blank numbers, but keeps the 'Player' column
        )
        
        st.subheader("Birdies and Pars Points Total")
        st.bar_chart(data=leaderboard, x="Player", y="Points")
        
    else:
        st.info("No data found.")

with tab3:
    st.header("Full History")
    df = load_data()
    if not df.empty:
        # Reordering columns to put Net Score in view
        display_df = df[['Week', 'Player', 'Total_Score', 'Handicap', 'Net_Score', 'Birdies_Count', 'Pars_Count']]
        # ADD 'hide_index=True' HERE
        st.dataframe(
            display_df.sort_values(by=['Week', 'Player'], ascending=[False, True]), 
            use_container_width=True,
            hide_index=True
        )
with tab4:
    st.header("League Settings")
    st.write(current_handicaps)