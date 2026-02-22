import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# --- STEP 1: CONFIGURATION ---
st.set_page_config(page_title="2026 GGGolf Summer League", layout="wide") 

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

ADMIN_PASSWORD = "InsigniaSeahawks6145" 
conn = st.connection("gsheets", type=GSheetsConnection)

FEDEX_POINTS = {
    1: 100, 2: 77, 3: 64, 4: 54, 5: 47, 6: 41,
    7: 36, 8: 31, 9: 27, 10: 24, 11: 21, 12: 18, 13: 16
}

# --- STEP 2: FUNCTIONS ---
def load_data():
    try:
        data = conn.read(ttl=0) # ttl=0 ensures real-time data fetch
        return data.dropna(how='all')
    except:
        return pd.DataFrame()

def save_data(week, player, pars, birdies, eagles, score_val, hcp_val, pin):
    st.cache_data.clear()
    existing_data = conn.read(ttl=0)
    
    is_dnf = (score_val == "DNF")
    final_gross = 0 if is_dnf else int(score_val)
    final_net = 0 if is_dnf else (final_gross - hcp_val)
    
    new_entry = pd.DataFrame([{
        'Week': week, 'Player': player,
        'Pars_Count': pars, 'Birdies_Count': birdies, 'Eagle_Count': eagles,
        'Total_Score': final_gross, 'Handicap': hcp_val, 
        'Net_Score': final_net, 'DNF': is_dnf, 'PIN': pin
    }])
    
    if not existing_data.empty:
        updated_df = existing_data[~((existing_data['Week'] == week) & (existing_data['Player'] == player))]
        final_df = pd.concat([updated_df, new_entry], ignore_index=True)
    else:
        final_df = new_entry
        
    conn.update(data=final_df)
    st.cache_data.clear()
    st.rerun()

# --- STEP 3: DATA PROCESSING ---
df_main = load_data()

if not df_main.empty and 'Player' in df_main.columns:
    EXISTING_PLAYERS = sorted(df_main['Player'].unique().tolist())
    # Ensure numeric types for calculation
    df_main['Week'] = pd.to_numeric(df_main['Week'], errors='coerce').fillna(0)
    df_main['Net_Score'] = pd.to_numeric(df_main['Net_Score'], errors='coerce').fillna(0)
    df_main['Pars_Count'] = pd.to_numeric(df_main['Pars_Count'], errors='coerce').fillna(0)
    df_main['Birdies_Count'] = pd.to_numeric(df_main['Birdies_Count'], errors='coerce').fillna(0)
    df_main['Eagle_Count'] = pd.to_numeric(df_main['Eagle_Count'], errors='coerce').fillna(0)
else:
    EXISTING_PLAYERS = []

# --- STEP 4: UI LAYOUT ---
st.markdown("<div style='text-align: center;'>", unsafe_allow_html=True)
st.image("GGGOLF-2.png", width=120) 
st.markdown("<h1>GGGolf Summer League 2026</h1>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "📝 Scorecard", "🏆 Standings", "📅 History", "📜 Info", 
    "⚖️ Rules", "⚙️ Admin", "🏆 Bracket", "👤 Registration"
])

# --- TAB 1: SCORECARD ---
with tab1:
    if not EXISTING_PLAYERS:
        st.warning("No players registered yet.")
    else:
        c1, c2 = st.columns(2)
        player_select = c1.selectbox("Player", EXISTING_PLAYERS, key="p_sel")
        week_select = c2.selectbox("Week", range(1, 13), key="w_sel")
        user_pin_input = st.text_input(f"PIN for {player_select}", type="password", key="p_in")

        is_verified = False
        stored_pin = ""
        if st.session_state["authenticated"]:
            is_verified = True
        elif user_pin_input and not df_main.empty:
            player_info = df_main[df_main['Player'] == player_select]
            if not player_info.empty:
                stored_pin = str(player_info.iloc[0].get('PIN', '')).split('.')[0].strip()
                if user_pin_input.strip() == stored_pin:
                    is_verified = True

        if is_verified:
            # Display Player's Current Season Totals
            p_data = df_main[df_main['Player'] == player_select]
            tot_p = p_data['Pars_Count'].sum()
            tot_b = p_data['Birdies_Count'].sum()
            tot_e = p_data['Eagle_Count'].sum()
            
            st.write(f"### 📊 {player_select}'s Season Totals")
            sc1, sc2, sc3 = st.columns(3)
            sc1.metric("Total Pars", int(tot_p))
            sc2.metric("Total Birdies", int(tot_b))
            sc3.metric("Total Eagles", int(tot_e))
            st.divider()

            with st.form("score_entry", clear_on_submit=True):
                st.subheader(f"Enter Week {week_select} Score")
                score_select = st.selectbox("Gross Score", ["DNF"] + [str(i) for i in range(25, 120)])
                hcp_in = st.number_input("Handicap", 0, 40, 10)
                
                col1, col2, col3 = st.columns(3)
                s_pars = col1.number_input("Pars", 0, 18, 0, key=f"p_{player_select}_{week_select}")
                s_birdies = col2.number_input("Birdies", 0, 18, 0, key=f"b_{player_select}_{week_select}")
                s_eagles = col3.number_input("Eagles", 0, 18, 0, key=f"e_{player_select}_{week_select}")
                
                if st.form_submit_button("Submit Score"):
                    pin_to_save = stored_pin if stored_pin else user_pin_input
                    save_data(week_select, player_select, s_pars, s_birdies, s_eagles, score_select, hcp_in, pin_to_save)
        else:
            st.info("Enter PIN to unlock Scorecard and see your stats.")

# --- TAB 2: STANDINGS ---
with tab2:
    st.header("🏆 League Standings")
    if not df_main.empty:
        # 1. STANDINGS CALCULATION (FedEx Points)
        points_data = []
        actual_weeks = df_main[df_main['Week'] > 0].copy()
        
        for w in actual_weeks['Week'].unique():
            week_df = actual_weeks[(actual_weeks['Week'] == w) & (actual_weeks['DNF'] == False)].copy()
            if not week_df.empty:
                # Rank players for the week (Lowest Net Score gets Rank 1)
                week_df['Rank'] = week_df['Net_Score'].rank(method='min', ascending=True)
                week_df['Pts'] = week_df['Rank'].map(FEDEX_POINTS).fillna(10) # 10 pts for anyone outside top 13
                points_data.append(week_df[['Player', 'Pts']])
        
        if points_data:
            all_pts = pd.concat(points_data)
            leaderboard = all_pts.groupby('Player')['Pts'].sum().reset_index()
            leaderboard = leaderboard.sort_values(by='Pts', ascending=False).reset_index(drop=True)
            leaderboard.index += 1
            st.subheader("Leaderboard (Points)")
            st.dataframe(leaderboard, use_container_width=True)
        
        st.divider()
        
        # 2. CATEGORY TOTALS (Pars, Birdies, Eagles)
        st.subheader("🎯 Season Category Totals")
        cat_totals = df_main.groupby('Player').agg({
            'Pars_Count': 'sum',
            'Birdies_Count': 'sum',
            'Eagle_Count': 'sum'
        }).reset_index()
        cat_totals.columns = ['Player', 'Total Pars', 'Total Birdies', 'Total Eagles']
        st.dataframe(cat_totals.sort_values(by='Total Pars', ascending=False), use_container_width=True, hide_index=True)
    else:
        st.info("No data available yet.")

# --- TAB 3: HISTORY ---
with tab3:
    st.subheader("📅 Weekly History")
    if not df_main.empty:
        history_df = df_main[df_main['Week'] > 0].copy()
        if 'PIN' in history_df.columns:
            history_df = history_df.drop(columns=['PIN'])
        if not history_df.empty:
            st.dataframe(history_df.sort_values(["Week", "Player"], ascending=[False, True]), use_container_width=True, hide_index=True)
        else:
            st.info("No weekly scores recorded yet.")

# --- TAB 6: ADMIN ---
with tab6:
    st.subheader("⚙️ Admin Settings")
    admin_pw = st.text_input("Admin Password", type="password", key="admin_entry")
    if admin_pw == ADMIN_PASSWORD:
        st.session_state["authenticated"] = True
        if st.button("🔄 Force Refresh Database"):
            st.cache_data.clear()
            st.rerun()

# --- TAB 7: BRACKET ---
with tab7:
    st.header("🏆 Tournament Bracket")
    st.info("Tournament starts Week 9. Bracket re-seeded after Round 1.")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.subheader("Week 9")
        st.write("Matchups TBD based on standings.")

# --- TAB 8: REGISTRATION ---
with tab8:
    st.header("👤 Player Registration")
    with st.form("reg_form", clear_on_submit=True):
        new_name = st.text_input("Full Name", key="reg_n")
        new_pin = st.text_input("Create 4-Digit PIN", max_chars=4, type="password", key="reg_p")
        starting_hcp = st.number_input("Starting Handicap", 0, 36, 10)
        
        if st.form_submit_button("Register"):
            if new_name and len(new_pin) == 4:
                new_reg = pd.DataFrame([{
                    "Week": 0, "Player": new_name, "PIN": new_pin, 
                    "Handicap": starting_hcp, "Total_Score": 0, "DNF": True,
                    "Pars_Count": 0, "Birdies_Count": 0, "Eagle_Count": 0, "Net_Score": 0
                }])
                updated_df = pd.concat([df_main, new_reg], ignore_index=True)
                conn.update(data=updated_df)
                st.cache_data.clear()
                st.success(f"Registered {new_name}!")
                st.rerun()
