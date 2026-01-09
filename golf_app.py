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

# --- STEP 2: LOAD & PREPARE DATA ---
current_handicaps = get_handicaps()
PLAYERS = sorted(list(current_handicaps.keys()))
df_main = load_data()

# Calculate points globally
if not df_main.empty:
    df_main = df_main.fillna(0)
    df_main['calc_pts'] = (
        (df_main['Pars_Count'] * 1.85) + (df_main['Birdies_Count'] * 2.5) + (df_main['Eagle_Count'] * 3.0) +
        (df_main['G_Par_Count'] * 1.0) + (df_main['G_Birdie_Count'] * 1.75) + (df_main['G_Eagle_Count'] * 2.0)
    )

# --- LOGO & TITLE ---
# This ensures the logo is centered at the top
col_l1, col_l2, col_l3 = st.columns([1,1,1])
with col_l2:
    try:
        st.image("GGGOLF-2.png", width=200)
    except:
        st.write("⛳ (Logo File 'GGGOLF-2.png' Not Found)")

st.markdown("<h1 style='text-align: center;'>GGGolf 2026 Winter League</h1>", unsafe_allow_html=True)
st.divider()

tab1, tab2, tab3, tab4 = st.tabs(["📝 Live Scorecard", "🏆 Leaderboard", "📅 Weekly Log", "⚙️ Admin"])

# --- TAB 1: LIVE SCORECARD ---
with tab1:
    if 'scorecard' not in st.session_state:
        st.session_state.scorecard = {'Par: 1.85': 0, 'Birdie: 2.5': 0, 'Eagle: 3.0': 0, 'G_Par: 1.0': 0, 'G_Birdie: 1.75': 0, 'G_Eagle: 2.0': 0}
    if 'current_selection' not in st.session_state:
        st.session_state.current_selection = ""

    col1, col2 = st.columns(2)
    player_select = col1.selectbox("Select Player", PLAYERS)
    week_select = col2.selectbox("Select Week", range(1, 13))
    
    default_hcp = int(current_handicaps.get(player_select, 0))
    selection_id = f"{player_select}_{week_select}"
    
    if st.session_state.current_selection != selection_id:
        if not df_main.empty:
            match = df_main[(df_main['Player'] == player_select) & (df_main['Week'] == week_select)]
            if not match.empty:
                st.session_state.scorecard['Par'] = int(match.iloc[0].get('Pars_Count', 0))
                st.session_state.scorecard['Birdie'] = int(match.iloc[0].get('Birdies_Count', 0))
                st.session_state.scorecard['Eagle'] = int(match.iloc[0].get('Eagle_Count', 0))
                st.session_state.scorecard['G_Par'] = int(match.iloc[0].get('G_Par_Count', 0))
                st.session_state.scorecard['G_Birdie'] = int(match.iloc[0].get('G_Birdie_Count', 0))
                st.session_state.scorecard['G_Eagle'] = int(match.iloc[0].get('G_Eagle_Count', 0))
                st.session_state['temp_score'] = int(match.iloc[0].get('Total_Score', 45))
                st.session_state['temp_hcp'] = int(match.iloc[0].get('Handicap', default_hcp))
            else:
                for k in st.session_state.scorecard: st.session_state.scorecard[k] = 0
                st.session_state['temp_score'] = 45
                st.session_state['temp_hcp'] = default_hcp
        st.session_state.current_selection = selection_id

    st.divider()
    
    live_pts = (
        (st.session_state.scorecard['Par'] * 1.85) + (st.session_state.scorecard['Birdie'] * 2.5) + (st.session_state.scorecard['Eagle'] * 3.0) +
        (st.session_state.scorecard['G_Par'] * 1.0) + (st.session_state.scorecard['G_Birdie'] * 1.75) + (st.session_state.scorecard['G_Eagle'] * 2.0)
    )

    prev_pts = 0
    if not df_main.empty:
        prev_pts = df_main[(df_main['Player'] == player_select) & (df_main['Week'] < week_select)]['calc_pts'].sum()

    m_col1, m_col2 = st.columns(2)
    m_col1.metric("Selected Week Points", f"{live_pts:.2f}")
    m_col2.metric("Projected Season Total", f"{prev_pts + live_pts:.2f}", delta=f"Week {week_select}")

    r1, r2 = st.columns(3), st.columns(3)
    cats = [("Par", r1[0], 'Par'), ("Birdie", r1[1], 'Birdie'), ("Eagle", r1[2], 'Eagle'),
            ("Gimme Par", r2[0], 'G_Par'), ("Gimme Birdie", r2[1], 'G_Birdie'), ("Gimme Eagle", r2[2], 'G_Eagle')]

    for label, col, key in cats:
        st.session_state.scorecard[key] = col.number_input(label, min_value=0, value=st.session_state.scorecard[key], key=f"in_{key}_{selection_id}")

    st.divider()
    m1, m2, m3 = st.columns(3)
    score_in = m1.number_input("Gross Score", min_value=20, value=st.session_state.get('temp_score', 45), key=f"gross_{selection_id}")
    hcp_in = m2.number_input(f"Handicap", value=st.session_state.get('temp_hcp', default_hcp), key=f"hcp_{selection_id}")
    m3.metric("Net Score", score_in - hcp_in)

    if st.button("🚀 Update / Submit Final Round"):
        save_data(week_select, player_select, st.session_state.scorecard['Par'], st.session_state.scorecard['Birdie'], 
                  st.session_state.scorecard['Eagle'], st.session_state.scorecard['G_Par'], 
                  st.session_state.scorecard['G_Birdie'], st.session_state.scorecard['G_Eagle'], score_in, hcp_in)
        st.success(f"Scorecard updated for {player_select} - Week {week_select}")
        st.rerun()

# --- TAB 2: LEADERBOARD ---
with tab2:
    if not df_main.empty:
        leaderboard = df_main.groupby('Player').agg({'calc_pts': 'sum', 'Total_Score': 'mean', 'Net_Score': 'mean'}).rename(columns={'calc_pts': 'Points'}).reset_index()
        leaderboard = leaderboard.round(2).sort_values(by=['Points', 'Net_Score'], ascending=[False, True])

        # NEW: First Place Highlight Feature
        leader_name = leaderboard.iloc[0]['Player']
        leader_pts = leaderboard.iloc[0]['Points']
        st.success(f"🏆 Current League Leader: **{leader_name}** with **{leader_pts}** points!")

        st.dataframe(leaderboard, use_container_width=True, hide_index=True)
        
        st.divider()
        st.subheader("📉 Net Score Trending")
        trend_df = df_main.pivot_table(index='Week', columns='Player', values='Net_Score', aggfunc='mean')
        trend_df.index = [f"Week {int(i)}" for i in trend_df.index]
        st.line_chart(trend_df)
        
        st.subheader("Season Points Total")
        st.bar_chart(data=leaderboard, x="Player", y="Points")
    else:
        st.info("No data found.")

# --- TAB 3: LOG ---
with tab3:
    st.header("Full History")
    if not df_main.empty:
        cols = ['Week', 'Player', 'Total_Score', 'Handicap', 'Net_Score', 'Pars_Count', 'Birdies_Count', 'Eagle_Count']
        st.dataframe(df_main[cols].sort_values(['Week', 'Player'], ascending=[False, True]), hide_index=True)

# --- TAB 4: ADMIN ---
with tab4:
    if st.button("🔄 Sync with Google Sheets Now"):
        st.cache_data.clear()

        st.rerun()
