import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# --- STEP 1: CONFIGURATION & SETUP ---
st.set_page_config(page_title="GGGolf League", page_icon="⛳", layout="wide") 

DEFAULT_HANDICAPS = {
    "Cory": 3, "Lex": 5, "John": 27, "Mike": 8,
    "Carter": 5, "Dale": 3, "Long": 5, "Txv": 3,
    "Matt": 1, "NomThai": 3, "VaMeng": 0
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
    
    if not existing_data.empty and 'Week' in existing_data.columns:
        updated_df = existing_data[~((existing_data['Week'] == week) & (existing_data['Player'] == player))]
        final_df = pd.concat([updated_df, new_entry], ignore_index=True)
    else:
        final_df = new_entry
    
    conn.update(data=final_df)
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
    
    col1, col2 = st.columns(2)
    player_select = col1.selectbox("Select Player", PLAYERS)
    week_select = col2.selectbox("Select Week", range(1, 13))
    
    default_hcp = int(current_handicaps.get(player_select, 0))
    st.divider()
    
    # LIVE MATH INPUTS
    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        score_input = st.number_input("Gross Score", min_value=20, max_value=150, value=45)
    with c2:
        hcp_input = st.number_input(f"Handicap for {player_select}", value=default_hcp, key=f"hcp_box_{player_select}")
    with c3:
        calculated_net = score_input - hcp_input
        st.metric(label="Calculated Net Score", value=calculated_net)

    st.divider()

    with st.form("stat_entry", clear_on_submit=True):
        st.caption("Enter hole breakdown:")
        
        row1_1, row1_2, row1_3 = st.columns(3)
        p_in = row1_1.number_input("Par (1.85 pts)", min_value=0, value=0)
        b_in = row1_2.number_input("Birdie (2.5 pts)", min_value=0, value=0)
        e_in = row1_3.number_input("Eagle (3 pts)", min_value=0, value=0)
        
        row2_1, row2_2, row2_3 = st.columns(3)
        gp_in = row2_1.number_input("Gimme Par (1 pt)", min_value=0, value=0)
        gb_in = row2_2.number_input("Gimme Birdie (1.75 pts)", min_value=0, value=0)
        ge_in = row2_3.number_input("Gimme Eagle (2 pts)", min_value=0, value=0)
        
        submit_button = st.form_submit_button("Save to Google Sheets")
        
        if submit_button:
            save_data(week_select, player_select, p_in, b_in, e_in, gp_in, gb_in, ge_in, score_input, hcp_input)
            st.success(f"✅ Saved! {player_select}'s Net Score: {calculated_net}")
            st.rerun()

with tab2:
    st.header("Season Standings")
    df = load_data()
    
    if not df.empty:
        df = df.fillna(0)
        # Point Calculation Logic
        df['Points'] = (
            (df['Pars_Count'] * 1.85) + (df['Birdies_Count'] * 2.5) + (df['Eagle_Count'] * 3.0) +
            (df['G_Par_Count'] * 1.0) + (df['G_Birdie_Count'] * 1.75) + (df['G_Eagle_Count'] * 2.0)
        )

        leaderboard = df.groupby('Player').agg({
            'Points': 'sum',
            'Total_Score': 'mean', 
            'Net_Score': 'mean'   
        }).rename(columns={'Total_Score': 'Avg Gross', 'Net_Score': 'Avg Net'}).reset_index()
        
        leaderboard = leaderboard.round(2).sort_values(by=['Points', 'Avg Net'], ascending=[False, True])
        
        st.dataframe(leaderboard, use_container_width=True, hide_index=True)
        st.subheader("Season Points Total")
        st.bar_chart(data=leaderboard, x="Player", y="Points")
    else:
        st.info("No data found.")

with tab3:
    st.header("Full History")
    df = load_data()
    if not df.empty:
        display_df = df[['Week', 'Player', 'Total_Score', 'Handicap', 'Net_Score', 'Pars_Count', 'Birdies_Count', 'Eagle_Count']]
        st.dataframe(display_df.sort_values(by=['Week', 'Player'], ascending=[False, True]), use_container_width=True, hide_index=True)

with tab4:
    st.header("League Settings")
    if st.button("🔄 Sync with Google Sheets Now"):
        st.cache_data.clear()
        st.rerun()
    st.divider()
    st.write("Current Handicaps in Memory:")
    st.write(current_handicaps)