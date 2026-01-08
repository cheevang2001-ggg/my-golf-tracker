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
    
    if not existing_data.empty:
        updated_df = existing_data[~((existing_data['Week'] == week) & (existing_data['Player'] == player))]
        final_df = pd.concat([updated_df, new_entry], ignore_index=True)
    else:
        final_df = new_entry
    
    conn.update(data=final_df)
    st.cache_data.clear()

# --- LOGO & TITLE ---
st.markdown("<h1 style='text-align: center;'>⛳ GGGolf 2026 Winter League</h1>", unsafe_allow_html=True)
st.divider()

tab1, tab2, tab3, tab4 = st.tabs(["📝 Live Scorecard", "🏆 Leaderboard", "📅 Weekly Log", "⚙️ Admin"])

current_handicaps = get_handicaps()
PLAYERS = sorted(list(current_handicaps.keys()))

# --- TAB 1: LIVE SCORECARD ---
with tab1:
    if 'scorecard' not in st.session_state:
        st.session_state.scorecard = {'Par': 0, 'Birdie': 0, 'Eagle': 0, 'G_Par': 0, 'G_Birdie': 0, 'G_Eagle': 0}

    col1, col2 = st.columns(2)
    player_select = col1.selectbox("Select Player", PLAYERS)
    week_select = col2.selectbox("Select Week", range(1, 13))
    
    st.divider()
    
    # LIVE POINTS PREVIEW
    current_pts = (
        (st.session_state.scorecard['Par'] * 1.85) + (st.session_state.scorecard['Birdie'] * 2.5) + (st.session_state.scorecard['Eagle'] * 3.0) +
        (st.session_state.scorecard['G_Par'] * 1.0) + (st.session_state.scorecard['G_Birdie'] * 1.75) + (st.session_state.scorecard['G_Eagle'] * 2.0)
    )
    st.metric("Live Points Earned", f"{current_pts:.2f}")

    # COUNTERS
    r1, r2 = st.columns(3), st.columns(3)
    cats = [("Par", r1[0], 'Par'), ("Birdie", r1[1], 'Birdie'), ("Eagle", r1[2], 'Eagle'),
            ("Gimme Par", r2[0], 'G_Par'), ("Gimme Birdie", r2[1], 'G_Birdie'), ("Gimme Eagle", r2[2], 'G_Eagle')]

    for label, col, key in cats:
        st.session_state.scorecard[key] = col.number_input(label, min_value=0, value=st.session_state.scorecard[key], key=f"in_{key}")

    st.divider()
    m1, m2, m3 = st.columns(3)
    score_in = m1.number_input("Gross Score", min_value=20, value=45)
    hcp_in = m2.number_input(f"Handicap", value=int(current_handicaps.get(player_select, 0)), key=f"h_{player_select}")
    m3.metric("Live Net Score", score_in - hcp_in)

    if st.button("🚀 Submit Final Round"):
        save_data(week_select, player_select, st.session_state.scorecard['Par'], st.session_state.scorecard['Birdie'], 
                  st.session_state.scorecard['Eagle'], st.session_state.scorecard['G_Par'], 
                  st.session_state.scorecard['G_Birdie'], st.session_state.scorecard['G_Eagle'], score_in, hcp_in)
        for k in st.session_state.scorecard: st.session_state.scorecard[k] = 0
        st.success("Round Saved!")
        st.rerun()

# --- TAB 2: LEADERBOARD & TRENDING ---
with tab2:
    st.header("Season Standings")
    df = load_data()
    if not df.empty:
        df = df.fillna(0)
        df['Points'] = ((df['Pars_Count'] * 1.85) + (df['Birdies_Count'] * 2.5) + (df['Eagle_Count'] * 3.0) +
                        (df['G_Par_Count'] * 1.0) + (df['G_Birdie_Count'] * 1.75) + (df['G_Eagle_Count'] * 2.0))

        leaderboard = df.groupby('Player').agg({'Points': 'sum', 'Total_Score': 'mean', 'Net_Score': 'mean'}).reset_index()
        leaderboard = leaderboard.round(2).sort_values(by=['Points', 'Net_Score'], ascending=[False, True])
        st.dataframe(leaderboard, use_container_width=True, hide_index=True)
        
        # --- MODIFIED TRENDING CHART (NET SCORE) ---
        st.divider()
        st.subheader("📉 Net Score Trending")
        st.caption("Lower is better. Track who is improving their game each week.")
        
        # Pivot by Net_Score instead of Points
        trend_df = df.pivot_table(index='Week', columns='Player', values='Net_Score', aggfunc='mean')
        st.line_chart(trend_df)
        
        st.subheader("Season Points Total")
        st.bar_chart(data=leaderboard, x="Player", y="Points")
    else:
        st.info("No data found.")

# --- TAB 3: LOG ---
with tab3:
    st.header("Full History")
    df = load_data()
    if not df.empty:
        cols = ['Week', 'Player', 'Total_Score', 'Handicap', 'Net_Score', 'Pars_Count', 'Birdies_Count', 'Eagle_Count']
        st.dataframe(df[cols].sort_values(['Week', 'Player'], ascending=[False, True]), hide_index=True)

# --- TAB 4: ADMIN ---
with tab4:
    if st.button("🔄 Sync with Google Sheets Now"):
        st.cache_data.clear()
        st.rerun()