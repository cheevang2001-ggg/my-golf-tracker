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

# Adjusted Point Distribution: DNFs will be handled separately to ensure 0 points
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

def save_data(week, player, pars, birdies, eagles, score, hcp_val, is_dnf=False):
    st.cache_data.clear()
    existing_data = conn.read(ttl=0)
    
    # If DNF, we store 0 for score and net score, and a flag for DNF 
    net_score = 0 if is_dnf else (score - hcp_val)
    final_score = 0 if is_dnf else score

    new_entry = pd.DataFrame([{
        'Week': week, 'Player': player,
        'Pars_Count': pars if not is_dnf else 0, 
        'Birdies_Count': birdies if not is_dnf else 0, 
        'Eagle_Count': eagles if not is_dnf else 0,
        'Total_Score': final_score, 
        'Handicap': hcp_val, 
        'Net_Score': net_score,
        'DNF': is_dnf
    }])
    
    if not existing_data.empty:
        updated_df = existing_data[~((existing_data['Week'] == week) & (existing_data['Player'] == player))]
        final_df = pd.concat([updated_df, new_entry], ignore_index=True)
    else:
        final_df = new_entry
        
    cols_to_keep = ['Week', 'Player', 'Pars_Count', 'Birdies_Count', 'Eagle_Count', 'Total_Score', 'Handicap', 'Net_Score', 'DNF']
    final_df = final_df[[c for c in cols_to_keep if c in final_df.columns]]
    conn.update(data=final_df)
    st.cache_data.clear()

# --- STEP 2: DATA PROCESSING ---
current_handicaps = get_handicaps()
PLAYERS = sorted(list(current_handicaps.keys()))
df_main = load_data()

if not df_main.empty:
    df_main = df_main.fillna(0)
    # Rank only non-DNF players for points [cite: 36]
    df_main['animal_pts'] = 0.0
    for week in df_main['Week'].unique():
        week_mask = (df_main['Week'] == week) & (df_main['DNF'] == False)
        if week_mask.any():
            # Standard ranking: Lower Net Score is better [cite: 36]
            ranks = df_main.loc[week_mask, 'Net_Score'].rank(ascending=True, method='min')
            df_main.loc[week_mask, 'animal_pts'] = ranks.map(FEDEX_POINTS).fillna(0)

# --- UI ---
st.markdown("<h1 style='text-align: center;'>GGGolf - No Animals - Winter League</h1>", unsafe_allow_html=True)
st.divider()

tab1, tab2, tab3, tab4, tab5 = st.tabs(["📝 Live Scorecard", "🏆 No Animals Standing", "📅 Weekly History", "📜 League Info", "⚙️ Admin"])

# --- TAB 1: SCORECARD ---
with tab1:
    st.subheader("Round Tracker")
    col1, col2 = st.columns(2)
    player_select = col1.selectbox("Select Player", PLAYERS)
    week_select = col2.selectbox("Select Week", range(1, 13))
    selection_id = f"{player_select}_{week_select}"
    
    # DNF Toggle 
    is_dnf = st.checkbox("Mark as DNF (Did Not Finish)", help="Selecting this will award 0 points and a 0 Net Score for the week.")

    if 'counts' not in st.session_state or st.session_state.get('current_selection') != selection_id:
        st.session_state.counts = {'Par': 0, 'Birdie': 0, 'Eagle': 0}
        if not df_main.empty:
            hist = df_main[(df_main['Player'] == player_select) & (df_main['Week'] <= week_select)]
            st.session_state.counts = {'Par': int(hist['Pars_Count'].sum()), 'Birdie': int(hist['Birdies_Count'].sum()), 'Eagle': int(hist['Eagle_Count'].sum())}
            this_wk = df_main[(df_main['Player'] == player_select) & (df_main['Week'] == week_select)]
            st.session_state['temp_score'] = int(this_wk.iloc[0]['Total_Score']) if not this_wk.empty else 45
            st.session_state['temp_hcp'] = int(this_wk.iloc[0]['Handicap']) if not this_wk.empty else int(current_handicaps.get(player_select, 0))
        st.session_state.current_selection = selection_id
    
    if not is_dnf:
        r1 = st.columns(3)
        st.session_state.counts['Par'] = r1[0].number_input("Season Total Pars", min_value=0, value=st.session_state.counts['Par'])
        st.session_state.counts['Birdie'] = r1[1].number_input("Season Total Birdies", min_value=0, value=st.session_state.counts['Birdie'])
        st.session_state.counts['Eagle'] = r1[2].number_input("Season Total Eagles", min_value=0, value=st.session_state.counts['Eagle'])
        
        m1, m2, m3 = st.columns(3)
        score_in = m1.number_input("Gross Score", min_value=20, value=st.session_state.get('temp_score', 45))
        hcp_in = m2.number_input("Handicap", value=st.session_state.get('temp_hcp', 0))
        m3.metric("Net Score", score_in - hcp_in)
    else:
        st.warning(f"{player_select} will receive 0 points for Week {week_select}.")
        score_in = 0
        hcp_in = int(current_handicaps.get(player_select, 0))

    if st.button("Submit"):
        prev = df_main[(df_main['Player'] == player_select) & (df_main['Week'] < week_select)]
        save_data(
            week_select, player_select, 
            st.session_state.counts['Par'] - prev['Pars_Count'].sum(), 
            st.session_state.counts['Birdie'] - prev['Birdies_Count'].sum(), 
            st.session_state.counts['Eagle'] - prev['Eagle_Count'].sum(), 
            score_in, hcp_in, is_dnf=is_dnf
        )
        st.success("Score Updated!")
        st.rerun()

# --- TAB 2: NO ANIMALS STANDING ---
with tab2:
    if not df_main.empty:
        st.header("No Animals League Standing")
        # Filter out 0 Net Scores (DNFs) from average calculation [cite: 36]
        valid_scores = df_main[df_main['DNF'] == False]
        
        standings = df_main.groupby('Player').agg({'animal_pts': 'sum'}).rename(columns={'animal_pts': 'Animal Pts'}).reset_index()
        avg_nets = valid_scores.groupby('Player').agg({'Net_Score': 'mean'}).rename(columns={'Net_Score': 'Avg Net'}).reset_index()
        
        standings = standings.merge(avg_nets, on='Player', how='left').fillna({'Avg Net': 0})
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
        st.header("Pars, Birdies, Eagles")
        feats = df_main.groupby('Player').agg({'Pars_Count': 'sum', 'Birdies_Count': 'sum', 'Eagle_Count': 'sum'}).rename(columns={'Pars_Count': 'Par', 'Birdies_Count': 'Birdie', 'Eagle_Count': 'Eagle'}).reset_index()
        st.dataframe(feats.sort_values('Par', ascending=False), use_container_width=True, hide_index=True)
    else:
        st.info("No data found.")

# --- TAB 3: WEEKLY HISTORY ---
with tab3:
    st.header("📅 Weekly History")
    if not df_main.empty:
        f1, f2 = st.columns([1, 2])
        filter_player = f1.multiselect("Filter Player", options=PLAYERS)
        filter_week = f2.multiselect("Filter Week", options=sorted(df_main['Week'].unique(), reverse=True))
        
        history_df = df_main.copy()
        if filter_player: history_df = history_df[history_df['Player'].isin(filter_player)]
        if filter_week: history_df = history_df[history_df['Week'].isin(filter_week)]
        
        # Display "DNF" in the Total_Score column for clarity 
        history_df['Status'] = history_df.apply(lambda x: "DNF" if x['DNF'] else "Active", axis=1)
        
        cols_to_show = ['Week', 'Player', 'Status', 'Total_Score', 'Handicap', 'Net_Score', 'Pars_Count', 'Birdies_Count', 'Eagle_Count']
        st.dataframe(history_df[cols_to_show].sort_values(['Week', 'Player'], ascending=[False, True]), use_container_width=True, hide_index=True)

# --- TAB 4: LEAGUE INFO ---
with tab4:
    st.header("📜 League Information")
    st.divider()
    st.markdown("""
    **Drawing:** 5:45pm | **Tee Time:** 6:00pm [cite: 45, 46]
    * **Partners:** Randomized by picking playing cards. ***Unless players agree to play versus each other.*** [cite: 47]
    * **Makeups:** Set your own time with Pin High and complete the week before Trackman close the week by the following Friday at 12AM. [cite: 47]
    * **DNFs:** Players who miss a week and do not complete a makeup receive a **DNF**. DNFs result in **0 points** and a **0 Net Score** for that week. [cite: 21, 54]
    * **Bottom 2 each bay:** Each week the bottom two from each bay will buy a bucket the following week. [cite: 48]
    * **Missed Week:** When you miss a week, when you return you buy a bucket. [cite: 49]
    * **No Animal Bets:** Bet your Bets, Drink your bets. [cite: 50]
    * **No Animal bay etiquette:** After hitting, return bay to hitting area for next player. Failure to do so results in 1/4 drink. [cite: 51, 52]
    * **First Putt:** Player makes first putt in-hole = Everyone else drinks 1/4. [cite: 52]
    * **Chips:** Player chips in-hole = Everyone else drinks 1/2. [cite: 53]
    * **Mulligans:** Owe 1 a bucket right away. [cite: 53]
    """)

# --- TAB 5: ADMIN ---
with tab5:
    if st.button("🔄 Force Refresh Sync"):
        st.cache_data.clear()
        st.rerun()
