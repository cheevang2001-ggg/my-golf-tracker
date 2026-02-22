import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# --- STEP 1: CONFIGURATION ---
st.set_page_config(page_title="2026 GGGolf Summer League", layout="wide") 

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

ADMIN_PASSWORD = "InsigniaSeahawks6145" 
conn = st.connection("gsheets", type=GSheetsConnection)

# FedEx Points Scale for GGG_pts calculation
FEDEX_POINTS = {
    1: 100, 2: 77, 3: 64, 4: 54, 5: 47, 6: 41,
    7: 36, 8: 31, 9: 27, 10: 24, 11: 21, 12: 18, 13: 16
}

# --- STEP 2: FUNCTIONS ---
def load_data():
    try:
        # ttl=0 ensures the app pulls FRESH data on every interaction
        data = conn.read(ttl=0)
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
        # Overwrite if player already submitted for this week
        updated_df = existing_data[~((existing_data['Week'] == week) & (existing_data['Player'] == player))]
        final_df = pd.concat([updated_df, new_entry], ignore_index=True)
    else:
        final_df = new_entry
        
    conn.update(data=final_df)
    st.cache_data.clear()
    st.rerun()

# --- STEP 3: DATA PROCESSING & CALCULATIONS ---
df_main = load_data()

if not df_main.empty and 'Player' in df_main.columns:
    EXISTING_PLAYERS = sorted(df_main['Player'].unique().tolist())
    
    # 1. Ensure numeric types for math
    df_main['Week'] = pd.to_numeric(df_main['Week'], errors='coerce').fillna(0)
    df_main['Net_Score'] = pd.to_numeric(df_main['Net_Score'], errors='coerce').fillna(0)
    df_main['DNF'] = df_main.get('DNF', False).astype(bool)
    
    # 2. Calculate GGG_pts (Replacing animal_pts)
    df_main['GGG_pts'] = 0.0
    for w in df_main['Week'].unique():
        if w == 0: continue
        mask = (df_main['Week'] == w) & (df_main['DNF'] == False)
        if mask.any():
            ranks = df_main.loc[mask, 'Net_Score'].rank(ascending=True, method='min')
            df_main.loc[mask, 'GGG_pts'] = ranks.map(FEDEX_POINTS).fillna(10)
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
            # Personal Statistics Dashboard
            p_data = df_main[df_main['Player'] == player_select]
            st.write(f"### 📊 {player_select}'s Season Totals")
            sc1, sc2, sc3 = st.columns(3)
            sc1.metric("Total Pars", int(p_data['Pars_Count'].sum()))
            sc2.metric("Total Birdies", int(p_data['Birdies_Count'].sum()))
            sc3.metric("Total Eagles", int(p_data['Eagle_Count'].sum()))
            st.divider()

            with st.form("score_entry", clear_on_submit=True):
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
            st.info("Enter PIN to unlock Scorecard.")

# --- TAB 2: STANDINGS ---
with tab2:
    st.header("🏆 League Standings")
    if not df_main.empty:
        leaderboard = df_main.groupby('Player')['GGG_pts'].sum().reset_index()
        leaderboard = leaderboard.sort_values(by='GGG_pts', ascending=False).reset_index(drop=True)
        leaderboard.index += 1
        st.subheader("Leaderboard (GGG Points)")
        st.dataframe(leaderboard, use_container_width=True)
    else:
        st.info("No data available yet.")

# --- TAB 3: HISTORY ---
with tab3:
    st.subheader("📅 Weekly History")
    if not df_main.empty:
        # Filters
        f1, f2 = st.columns(2)
        p_filter = f1.selectbox("Filter by Player", ["All"] + EXISTING_PLAYERS)
        w_filter = f2.selectbox("Filter by Week", ["All"] + list(range(1, 13)))
        
        history_df = df_main[df_main['Week'] > 0].copy()
        
        if p_filter != "All":
            history_df = history_df[history_df['Player'] == p_filter]
        if w_filter != "All":
            history_df = history_df[history_df['Week'] == int(w_filter)]

        # REARRANGE COLUMNS: Move Pars/Birdies/Eagles and DNF to the end
        # Hide PIN and ensure animal_pts is gone
        cols_at_end = ['Pars_Count', 'Birdies_Count', 'Eagle_Count', 'DNF']
        cols_at_start = [c for c in history_df.columns if c not in cols_at_end and c not in ['PIN', 'animal_pts']]
        
        history_df = history_df[cols_at_start + cols_at_end]

        st.dataframe(history_df.sort_values(["Week", "Player"], ascending=[False, True]), use_container_width=True, hide_index=True)
    else:
        st.info("No weekly scores recorded yet.")

# --- TAB 6: ADMIN ---
with tab6:
    st.subheader("⚙️ Admin Settings")
    admin_pw = st.text_input("Admin Password", type="password", key="adm_key")
    if admin_pw == ADMIN_PASSWORD:
        st.session_state["authenticated"] = True
        if st.button("🔄 Force Refresh Database"):
            st.cache_data.clear()
            st.rerun()

# --- TAB 7: BRACKET ---
with tab7:
    st.header("🏆 Tournament Bracket")
    st.info("Starts Week 9.")

# --- TAB 8: REGISTRATION ---
with tab8:
    st.header("👤 Player Registration")
    with st.form("reg_form", clear_on_submit=True):
        new_name = st.text_input("Full Name", key="rn")
        new_pin = st.text_input("Create 4-Digit PIN", max_chars=4, type="password", key="rp")
        starting_hcp = st.number_input("Starting Handicap", 0, 36, 10)
        
        if st.form_submit_button("Register Player"):
            if new_name and len(new_pin) == 4:
                new_reg = pd.DataFrame([{
                    "Week": 0, "Player": new_name, "PIN": new_pin, 
                    "Handicap": starting_hcp, "Total_Score": 0, "DNF": True,
                    "Pars_Count": 0, "Birdies_Count": 0, "Eagle_Count": 0, "Net_Score": 0, "GGG_pts": 0
                }])
                updated_df = pd.concat([df_main, new_reg], ignore_index=True)
                conn.update(data=updated_df)
                st.cache_data.clear()
                st.success(f"Registered {new_name}!")
                st.rerun()
