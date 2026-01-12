import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# --- STEP 1: CONFIGURATION & SETUP ---
st.set_page_config(page_title="GGGolf No Animals Winter League", layout="wide") 

DEFAULT_HANDICAPS = {
    "Cory": 3, "Lex": 7, "Mike": 9,
    "Carter": 5, "Dale": 4, "Long": 6, "Txv": 4,
    "Matt": 2, "NomThai": 4, "VaMeng": 0,
    "Xuka": 0, "Beef": 9
}

FEDEX_POINTS = {
    1: 100, 2: 85, 3: 75, 4: 70, 5: 65, 6: 60,
    7: 55, 8: 50, 9: 45, 10: 40, 11: 35, 12: 30
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

def save_data(week, player, pars, birdies, eagles, score, hcp_val):
    st.cache_data.clear()
    existing_data = conn.read(ttl=0)
    new_entry = pd.DataFrame([{
        'Week': week, 'Player': player,
        'Pars_Count': pars, 'Birdies_Count': birdies, 'Eagle_Count': eagles,
        'Total_Score': score, 'Handicap': hcp_val, 'Net_Score': score - hcp_val
    }])
    if not existing_data.empty:
        updated_df = existing_data[~((existing_data['Week'] == week) & (existing_data['Player'] == player))]
        final_df = pd.concat([updated_df, new_entry], ignore_index=True)
    else:
        final_df = new_entry
    cols_to_keep = ['Week', 'Player', 'Pars_Count', 'Birdies_Count', 'Eagle_Count', 'Total_Score', 'Handicap', 'Net_Score']
    final_df = final_df[cols_to_keep]
    conn.update(data=final_df)
    st.cache_data.clear()

# --- STEP 2: DATA PROCESSING ---
current_handicaps = get_handicaps()
PLAYERS = sorted(list(current_handicaps.keys()))
df_main = load_data()

if not df_main.empty:
    df_main = df_main.fillna(0)
    df_main['week_rank'] = df_main.groupby('Week')['Net_Score'].rank(ascending=True, method='min')
    df_main['animal_pts'] = df_main['week_rank'].map(FEDEX_POINTS).fillna(0)

# --- UI ---
st.markdown("<h1 style='text-align: center;'>GGGolf - No Animals - Winter League</h1>", unsafe_allow_html=True)
st.divider()

tab1, tab2, tab3, tab4, tab5 = st.tabs(["📝 Live Scorecard", "🏆 No Animals Standing", "📅 Weekly History", "📜 League Info", "⚙️ Admin"])

# --- TAB 1: SCORECARD ---
with tab1:
    st.subheader("🔢 Track Your Round Counts")
    col1, col2 = st.columns(2)
    player_select = col1.selectbox("Select Player", PLAYERS)
    week_select = col2.selectbox("Select Week", range(1, 13))
    selection_id = f"{player_select}_{week_select}"
    
    if 'counts' not in st.session_state or st.session_state.get('current_selection') != selection_id:
        st.session_state.counts = {'Par': 0, 'Birdie': 0, 'Eagle': 0}
        if not df_main.empty:
            hist = df_main[(df_main['Player'] == player_select) & (df_main['Week'] <= week_select)]
            st.session_state.counts = {'Par': int(hist['Pars_Count'].sum()), 'Birdie': int(hist['Birdies_Count'].sum()), 'Eagle': int(hist['Eagle_Count'].sum())}
            this_wk = df_main[(df_main['Player'] == player_select) & (df_main['Week'] == week_select)]
            st.session_state['temp_score'] = int(this_wk.iloc[0]['Total_Score']) if not this_wk.empty else 45
            st.session_state['temp_hcp'] = int(this_wk.iloc[0]['Handicap']) if not this_wk.empty else int(current_handicaps.get(player_select, 0))
        st.session_state.current_selection = selection_id
    
    r1 = st.columns(3)
    st.session_state.counts['Par'] = r1[0].number_input("Season Total Pars", min_value=0, value=st.session_state.counts['Par'])
    st.session_state.counts['Birdie'] = r1[1].number_input("Season Total Birdies", min_value=0, value=st.session_state.counts['Birdie'])
    st.session_state.counts['Eagle'] = r1[2].number_input("Season Total Eagles", min_value=0, value=st.session_state.counts['Eagle'])
    
    m1, m2, m3 = st.columns(3)
    score_in = m1.number_input("Gross Score", min_value=20, value=st.session_state.get('temp_score', 45))
    hcp_in = m2.number_input("Handicap", value=st.session_state.get('temp_hcp', 0))
    m3.metric("Net Score", score_in - hcp_in)
    
    if st.button("🚀 Submit & Sync Data"):
        prev = df_main[(df_main['Player'] == player_select) & (df_main['Week'] < week_select)]
        save_data(week_select, player_select, st.session_state.counts['Par'] - prev['Pars_Count'].sum(), st.session_state.counts['Birdie'] - prev['Birdies_Count'].sum(), st.session_state.counts['Eagle'] - prev['Eagle_Count'].sum(), score_in, hcp_in)
        st.success("Score Updated!")
        st.rerun()

# --- TAB 2: NO ANIMALS STANDING ---
with tab2:
    if not df_main.empty:
        # SECTION 1: MAIN LEADERBOARD
        st.header("🏁 No Animals Standing")
        standings = df_main.groupby('Player').agg({
            'animal_pts': 'sum', 
            'Net_Score': 'mean'
        }).rename(columns={'animal_pts': 'Animal Pts', 'Net_Score': 'Avg Net'}).reset_index()
        
        standings['Total Points'] = standings['Animal Pts']
        standings = standings.round(1).sort_values(by=['Animal Pts', 'Avg Net'], ascending=[False, True])
        
        st.dataframe(
            standings[['Player', 'Animal Pts', 'Total Points', 'Avg Net']],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Player": st.column_config.TextColumn("Player", width="medium"),
                "Animal Pts": st.column_config.NumberColumn("Pts", width="small"),
                "Total Points": st.column_config.NumberColumn("Total", width="small"),
                "Avg Net": st.column_config.NumberColumn("Net", width="small"),
            }
        )

        st.divider()

        # SECTION 2: PARS, BIRDIES, EAGLES
        st.header("🦅 Pars, Birdies, Eagles")
        feats = df_main.groupby('Player').agg({
            'Pars_Count': 'sum', 
            'Birdies_Count': 'sum', 
            'Eagle_Count': 'sum'
        }).rename(columns={
            'Pars_Count': 'Par', 
            'Birdies_Count': 'Birdie', 
            'Eagle_Count': 'Eagle'
        }).reset_index()
        
        # Sort by Par count descending
        feats_display = feats.sort_values('Par', ascending=False)

        st.dataframe(
            feats_display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Player": st.column_config.TextColumn("Player", width="medium"),
                "Par": st.column_config.NumberColumn("Par", width="small"),
                "Birdie": st.column_config.NumberColumn("Birdie", width="small"),
                "Eagle": st.column_config.NumberColumn("Eagle", width="small"),
            }
        )
    else:
        st.info("No data found.")

# --- TAB 3: WEEKLY HISTORY ---
with tab3:
    st.header("📅 Weekly History")
    if not df_main.empty:
        history_df = df_main[['Week', 'Player', 'Pars_Count', 'Birdies_Count', 'Eagle_Count', 'Total_Score', 'Handicap', 'Net_Score']].sort_values(['Week', 'Player'], ascending=[False, True])
        st.dataframe(
            history_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Week": st.column_config.NumberColumn("Wk", width="small"),
                "Player": st.column_config.TextColumn("Player", width="medium"),
                "Pars_Count": st.column_config.NumberColumn("Pars", width="small"),
                "Birdies_Count": st.column_config.NumberColumn("Birds", width="small"),
                "Eagle_Count": st.column_config.NumberColumn("Egls", width="small"),
                "Total_Score": st.column_config.NumberColumn("Gross", width="small"),
                "Handicap": st.column_config.NumberColumn("Hcp", width="small"),
                "Net_Score": st.column_config.NumberColumn("Net", width="small"),
            }
        )
# --- TABS 4 & 5 (Admin & Info) remain the same ---
