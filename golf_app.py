import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# --- STEP 1: CONFIGURATION & SETUP ---
st.set_page_config(page_title="GGGolf No Animals Winter League", layout="wide") 

ADMIN_PASSWORD = "InsigniaSeahawks6145" 

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

def calculate_rolling_handicap(player_df, current_week):
    """
    Logic: Take the 4 most recent rounds PRIOR to the current week, 
    remove the worst (highest), and average the remaining 3 relative to Par 36.
    """
    # Get all rounds before the week we are currently scoring
    valid_rounds = player_df[(player_df['Total_Score'] > 0) & (player_df['Week'] < current_week)]
    valid_rounds = valid_rounds.sort_values('Week', ascending=False)
    
    if len(valid_rounds) < 4:
        return None 
    
    # Get the 4 most recent rounds
    last_4 = valid_rounds.head(4)['Total_Score'].tolist()
    # Remove the highest score (worst)
    last_4.remove(max(last_4))
    # Average the best 3
    avg_gross = sum(last_4) / 3
    # Handicap = Avg Gross - 36
    return int(round(max(0, avg_gross - 36)))

def get_handicaps(current_week):
    df = load_data() 
    calculated_hcps = {}
    
    for player, hcp in DEFAULT_HANDICAPS.items():
        if not df.empty:
            player_data = df[df['Player'] == player]
            rolling = calculate_rolling_handicap(player_data, current_week)
            calculated_hcps[player] = rolling if rolling is not None else hcp
        else:
            calculated_hcps[player] = hcp
                
    return calculated_hcps

def save_data(week, player, pars, birdies, eagles, score_val, hcp_val):
    st.cache_data.clear()
    existing_data = conn.read(ttl=0)
    
    is_dnf = (score_val == "DNF")
    final_gross = 0 if is_dnf else int(score_val)
    final_net = 0 if is_dnf else (final_gross - hcp_val)

    new_entry = pd.DataFrame([{
        'Week': week, 'Player': player,
        'Pars_Count': pars, 'Birdies_Count': birdies, 'Eagle_Count': eagles,
        'Total_Score': final_gross, 'Handicap': hcp_val, 
        'Net_Score': final_net, 'DNF': is_dnf
    }])
    
    if not existing_data.empty:
        updated_df = existing_data[~((existing_data['Week'] == week) & (existing_data['Player'] == player))]
        final_df = pd.concat([updated_df, new_entry], ignore_index=True)
    else:
        final_df = new_entry
        
    conn.update(data=final_df)
    st.cache_data.clear()

# --- DATA PROCESSING ---
df_main = load_data()
if not df_main.empty:
    df_main = df_main.fillna(0)
    df_main['DNF'] = df_main.get('DNF', False).astype(bool)
    df_main['animal_pts'] = 0.0
    for week in df_main['Week'].unique():
        mask = (df_main['Week'] == week) & (df_main['DNF'] == False)
        if mask.any():
            ranks = df_main.loc[mask, 'Net_Score'].rank(ascending=True, method='min')
            df_main.loc[mask, 'animal_pts'] = ranks.map(FEDEX_POINTS).fillna(0)

# --- UI ---
st.markdown("<div style='text-align: center;'>", unsafe_allow_html=True)
st.image("GGGOLF-2.png", width=120) 
st.markdown("<h1 style='margin-top: -10px;'>GGGolf - No Animals</h1><p style='margin-top: -20px; color: gray;'>Winter League Tracker</p>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

st.divider()

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

tab1, tab2, tab3, tab4, tab5 = st.tabs(["📝 Scorecard", "🏆 Standings", "📅 History", "📜 Info", "⚙️ Admin"])

# --- TAB 1: SCORECARD ---
with tab1:
    st.subheader("Round Tracker")
    col1, col2 = st.columns(2)
    player_select = col1.selectbox("Select Player", sorted(DEFAULT_HANDICAPS.keys()), key="p_sel")
    week_select = col2.selectbox("Select Week", range(1, 13), key="w_sel")
    
    # Calculate values for display
    current_hcps_map = get_handicaps(week_select)
    suggested_hcp = current_hcps_map.get(player_select)
    
    if not df_main.empty:
        hist_prior = df_main[(df_main['Player'] == player_select) & (df_main['Week'] < week_select)]
        s_pars = int(hist_prior['Pars_Count'].sum())
        s_birdies = int(hist_prior['Birdies_Count'].sum())
        s_eagles = int(hist_prior['Eagle_Count'].sum())
        
        this_wk = df_main[(df_main['Player'] == player_select) & (df_main['Week'] == week_select)]
        wk_p = int(this_wk.iloc[0]['Pars_Count']) if not this_wk.empty else 0
        wk_b = int(this_wk.iloc[0]['Birdies_Count']) if not this_wk.empty else 0
        wk_e = int(this_wk.iloc[0]['Eagle_Count']) if not this_wk.empty else 0
        wk_s = int(this_wk.iloc[0]['Total_Score']) if (not this_wk.empty and this_wk.iloc[0]['Total_Score'] != 0) else 45
        wk_h = int(this_wk.iloc[0]['Handicap']) if not this_wk.empty else suggested_hcp
    else:
        s_pars = s_birdies = s_eagles = wk_p = wk_b = wk_e = 0
        wk_s = 45
        wk_h = suggested_hcp

    r1 = st.columns(3)
    sel_pars = r1[0].selectbox(f"Pars (Total: {s_pars + wk_p})", options=range(10), index=wk_p, key="p_in")
    sel_birdies = r1[1].selectbox(f"Birdies (Total: {s_birdies + wk_b})", options=range(10), index=wk_b, key="b_in")
    sel_eagles = r1[2].selectbox(f"Eagles (Total: {s_eagles + wk_e})", options=range(10), index=wk_e, key="e_in")
    
    st.divider()

    m1, m2, m3 = st.columns(3)
    score_options = ["DNF"] + list(range(30, 73))
    score_select = m1.selectbox("Gross Score", options=score_options, index=(0 if wk_s==0 else score_options.index(wk_s)), key="gs_in")
    
    # HANDICAP DISPLAY
    hcp_in = m2.number_input(f"Handicap (Suggested: {suggested_hcp})", value=wk_h, key="h_in")
    
    if score_select == "DNF":
        m3.metric("Net Score", "DNF")
    else:
        m3.metric("Net Score", int(score_select) - hcp_in)

    if st.session_state["authenticated"]:
        if st.button("Submit Score", use_container_width=True, key="sub"):
            save_data(week_select, player_select, sel_pars, sel_birdies, sel_eagles, score_select, hcp_in)
            st.success("Round Recorded!")
            st.rerun()
    else:
        st.warning("Read-Only Mode. Login in Admin tab to edit.")
        st.button("Submit Score", use_container_width=True, disabled=True, key="sub_dis")

# (Tabs 2-5 follow the previous code exactly, ensuring formatting is maintained)
with tab2:
    if not df_main.empty:
        st.header("Standings")
        standings = df_main.groupby('Player').agg({'animal_pts': 'sum'}).rename(columns={'animal_pts': 'Animal Pts'}).reset_index()
        avg_nets = df_main[df_main['DNF']==False].groupby('Player').agg({'Net_Score': 'mean'}).rename(columns={'Net_Score': 'Avg Net'}).reset_index()
        standings = standings.merge(avg_nets, on='Player', how='left').fillna(0)
        st.dataframe(standings.sort_values(by=['Animal Pts', 'Avg Net'], ascending=[False, True]), use_container_width=True, hide_index=True)

with tab3:
    st.header("📅 Weekly History")
    if not df_main.empty:
        st.dataframe(df_main.sort_values(['Week', 'Player'], ascending=[False, True]), use_container_width=True, hide_index=True)

with tab4:
    st.header("📜 League Information")
    st.markdown("* **Handicaps:** Calculated after 4 rounds (Avg of best 3 of last 4 relative to Par 36).")

with tab5:
    st.subheader("Admin")
    pwd = st.text_input("Password", type="password", key="ap")
    if pwd == ADMIN_PASSWORD:
        st.session_state["authenticated"] = True
    if st.button("🔄 Sync", key="syn", disabled=not st.session_state["authenticated"]):
        st.cache_data.clear()
        st.rerun()
