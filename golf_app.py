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
    st.header("Live Scorecard")
    
    # 1. Initialize Session State for the temporary scorecard if it doesn't exist
    if 'scorecard' not in st.session_state:
        st.session_state.scorecard = {
            'Par': 0, 'Birdie': 0, 'Eagle': 0,
            'G_Par': 0, 'G_Birdie': 0, 'G_Eagle': 0
        }

    # --- SECTION 1: SELECTION ---
    col1, col2 = st.columns(2)
    player_select = col1.selectbox("Select Player", PLAYERS)
    week_select = col2.selectbox("Select Week", range(1, 13))
    
    default_hcp = int(current_handicaps.get(player_select, 0))
    st.divider()
    
    # --- SECTION 2: CONTINUOUS COUNTERS ---
    st.subheader("Hole-by-Hole Entry")
    st.caption("Click the + and - buttons as you play. Values are saved locally until you submit.")

    # Create two rows of buttons for live counting
    r1_col1, r1_col2, r1_col3 = st.columns(3)
    r2_col1, r2_col2, r2_col3 = st.columns(3)

    categories = [
        ("Par", r1_col1, 'Par'), ("Birdie", r1_col2, 'Birdie'), ("Eagle", r1_col3, 'Eagle'),
        ("Gimme Par", r2_col1, 'G_Par'), ("Gimme Birdie", r2_col2, 'G_Birdie'), ("Gimme Eagle", r2_col3, 'G_Eagle')
    ]

    for label, col, key in categories:
        with col:
            # This number input stays in memory because it is linked to session_state
            st.session_state.scorecard[key] = st.number_input(
                label, 
                min_value=0, 
                value=st.session_state.scorecard[key],
                key=f"input_{key}"
            )

    st.divider()

    # --- SECTION 3: ROUND TOTALS & SUBMISSION ---
    st.subheader("Finalize Round")
    m1, m2, m3 = st.columns(3)
    
    score_input = m1.number_input("Gross Score", min_value=20, value=45)
    hcp_input = m2.number_input(f"Handicap", value=default_hcp, key=f"hcp_final_{player_select}")
    
    # Live Math
    calculated_net = score_input - hcp_input
    m3.metric("Live Net Score", calculated_net)

    if st.button("🚀 Submit Final Round to Sheets"):
        # Save all categories from session state
        save_data(
            week_select, player_select, 
            st.session_state.scorecard['Par'], 
            st.session_state.scorecard['Birdie'], 
            st.session_state.scorecard['Eagle'],
            st.session_state.scorecard['G_Par'], 
            st.session_state.scorecard['G_Birdie'], 
            st.session_state.scorecard['G_Eagle'],
            score_input, hcp_input
        )
        
        # Reset the temporary scorecard for the next entry
        for key in st.session_state.scorecard:
            st.session_state.scorecard[key] = 0
            
        st.success(f"✅ Round Submitted! {player_select} finished with a net {calculated_net}.")
        st.rerun()

    if st.button("🗑️ Clear Local Scorecard"):
        for key in st.session_state.scorecard:
            st.session_state.scorecard[key] = 0
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
        
        # --- NEW TRENDING CHART ---
        st.divider()
        st.subheader("📈 Performance Trending")
        st.caption("Weekly Points by Player")
        
        # Prepare data for trending chart (Week vs Points per Player)
        trend_df = df.pivot_table(index='Week', columns='Player', values='Points', aggfunc='sum').fillna(0)
        st.line_chart(trend_df)
        
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