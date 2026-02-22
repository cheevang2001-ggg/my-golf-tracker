import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import time

# --- STEP 1: CONFIGURATION ---
st.set_page_config(page_title="2026 GGGolf Summer League", layout="wide") 

# Initialize session states
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "unlocked_player" not in st.session_state:
    st.session_state["unlocked_player"] = None
if "login_timestamp" not in st.session_state:
    st.session_state["login_timestamp"] = 0
if "session_id" not in st.session_state:
    st.session_state["session_id"] = 0 

ADMIN_PASSWORD = "InsigniaSeahawks6145" 
SESSION_TIMEOUT = 4 * 60 * 60 # 4 Hours in seconds [cite: 1]
conn = st.connection("gsheets", type=GSheetsConnection)

# FedEx Point Logic
FEDEX_POINTS = {
    1: 100, 2: 77, 3: 64, 4: 54, 5: 47, 6: 41,
    7: 36, 8: 31, 9: 27, 10: 24, 11: 21, 12: 18, 13: 16
}

# --- STEP 2: FUNCTIONS ---
def load_data():
    try:
        data = conn.read(ttl=0)
        df = data.dropna(how='all')
        # Backwards compatibility for column names [cite: 2, 3]
        rename_map = {
            'Gross Score': 'Total_Score',
            'Pars': 'Pars_Count',
            'Birdies': 'Birdies_Count',
            'Eagles': 'Eagle_Count',
            'animal_pts': 'GGG_pts'
        }
        df = df.rename(columns=rename_map)
        return df
    except:
        return pd.DataFrame() [cite: 2]

def save_data(week, player, pars, birdies, eagles, score_val, hcp_val, pin):
    st.cache_data.clear()
    existing_data = load_data()
    
    is_dnf = (score_val == "DNF")
    final_gross = 0 if is_dnf else int(score_val)
    final_net = 0 if is_dnf else (final_gross - hcp_val)
    
    new_entry = pd.DataFrame([{
        'Week': week, 'Player': player,
        'Pars_Count': pars, 'Birdies_Count': birdies, 'Eagle_Count': eagles,
        'Total_Score': final_gross, 'Handicap': hcp_val, 
        'Net_Score': final_net, 'DNF': is_dnf, 'PIN': pin
    }]) [cite: 3]
    
    if not existing_data.empty:
        updated_df = existing_data[~((existing_data['Week'] == week) & (existing_data['Player'] == player))]
        final_df = pd.concat([updated_df, new_entry], ignore_index=True)
    else:
        final_df = new_entry
        
    conn.update(data=final_df)
    st.cache_data.clear()
    st.rerun() [cite: 10, 20]

# --- STEP 3: DATA PROCESSING ---
df_main = load_data()

if not df_main.empty and 'Player' in df_main.columns:
    EXISTING_PLAYERS = sorted(df_main['Player'].unique().tolist()) [cite: 4]
    df_main['Week'] = pd.to_numeric(df_main['Week'], errors='coerce').fillna(0)
    df_main['Net_Score'] = pd.to_numeric(df_main['Net_Score'], errors='coerce').fillna(0)
    df_main['DNF'] = df_main.get('DNF', False).astype(bool)
    
    # Initialize point column safely
    df_main['GGG_pts'] = 0.0
    
    # Calculate GGG_pts week-by-week using individual row assignment to prevent ValueErrors
    for w in df_main['Week'].unique():
        if w == 0: continue
        mask = (df_main['Week'] == w) & (df_main['DNF'] == False)
        
        if mask.any():
            week_indices = df_main.index[mask].tolist()
            week_scores = df_main.loc[mask, 'Net_Score']
            ranks = week_scores.rank(ascending=True, method='min')
            
            for idx in week_indices:
                r_val = ranks.at[idx]
                pts = FEDEX_POINTS.get(int(r_val), 10)
                df_main.at[idx, 'GGG_pts'] = float(pts)
else:
    EXISTING_PLAYERS = []

# --- STEP 4: UI LAYOUT ---
st.markdown("<div style='text-align: center;'>", unsafe_allow_html=True)
st.image("GGGOLF-2.png", width=120) 
st.markdown("<h1>GGGolf Summer League 2026</h1>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

tabs = st.tabs(["📝 Scorecard", "🏆 Standings", "📅 History", "📜 Info", "⚖️ Rules", "⚙️ Admin", "🏆 Bracket", "👤 Registration"])

# --- TAB 1: SCORECARD ---
with tabs[0]:
    if not EXISTING_PLAYERS:
        st.warning("No players registered.")
    else:
        player_select = st.selectbox("Player", EXISTING_PLAYERS, key="p_sel") [cite: 5]
        
        current_time = time.time()
        # Session check for 4-hour window
        is_unlocked = (st.session_state["unlocked_player"] == player_select and 
                       (current_time - st.session_state["login_timestamp"]) < SESSION_TIMEOUT)
        
        if st.session_state["authenticated"]: is_unlocked = True

        if not is_unlocked:
            st.info(f"🔒 {player_select} is locked.")
            # session_id in key ensures box clears on logout
            pin_key = f"pin_{player_select}_{st.session_state['session_id']}"
            user_pin_input = st.text_input(f"Enter PIN for {player_select}", type="password", key=pin_key)
            
            if user_pin_input:
                player_info = df_main[df_main['Player'] == player_select] [cite: 6]
                if not player_info.empty:
                    stored_pin = str(player_info.iloc[0].get('PIN', '')).split('.')[0].strip() [cite: 6]
                    if user_pin_input.strip() == stored_pin:
                        st.session_state["unlocked_player"] = player_select
                        st.session_state["login_timestamp"] = current_time
                        st.rerun() [cite: 10]
                    else:
                        st.error("❌ Incorrect PIN.")
        else:
            # Unlocked Header with Logout
            col_h1, col_h2 = st.columns([5, 1])
            col_h1.success(f"✅ **{player_select} Unlocked** (Expires in 4 hours)")
            if col_h2.button("Logout 🔓", use_container_width=True):
                st.session_state["unlocked_player"] = None
                st.session_state["login_timestamp"] = 0
                st.session_state["session_id"] += 1 
                st.rerun() [cite: 10]

            week_select = st.selectbox("Week", range(1, 13), key="w_sel") [cite: 5]
            
            with st.form("score_entry", clear_on_submit=True): [cite: 7]
                score_select = st.selectbox("Gross Score", ["DNF"] + [str(i) for i in range(25, 120)]) [cite: 7]
                hcp_in = st.number_input("Handicap", 0, 40, 10) [cite: 7]
                
                c1, c2, c3 = st.columns(3) [cite: 8]
                s_pars = c1.number_input("Pars", 0, 18, 0, key=f"p_{player_select}_{week_select}") [cite: 8]
                s_birdies = c2.number_input("Birdies", 0, 18, 0, key=f"b_{player_select}_{week_select}") [cite: 8]
                s_eagles = c3.number_input("Eagles", 0, 18, 0, key=f"e_{player_select}_{week_select}") [cite: 8, 9]
                
                if st.form_submit_button("Submit Score"):
                    player_info = df_main[df_main['Player'] == player_select]
                    final_pin = str(player_info.iloc[0].get('PIN', '')).split('.')[0].strip()
                    save_data(week_select, player_select, s_pars, s_birdies, s_eagles, score_select, hcp_in, final_pin) [cite: 9]

# --- TAB 2: STANDINGS ---
with tabs[1]:
    st.subheader("League Standings")
    if not df_main.empty:
        # Group by player and sum points
        leaderboard = df_main.groupby('Player')['GGG_pts'].sum().reset_index()
        # The ValueError occurred here; we ensure GGG_pts is unique and present
        leaderboard = leaderboard.sort_values(by='GGG_pts', ascending=False).reset_index(drop=True)
        leaderboard.index += 1
        st.dataframe(leaderboard, use_container_width=True)

# --- TAB 3: HISTORY ---
with tabs[2]:
    st.subheader("Season History")
    if not df_main.empty:
        f1, f2 = st.columns(2)
        p_filter = f1.selectbox("Filter Player", ["All"] + EXISTING_PLAYERS, key="h_p")
        w_filter = f2.selectbox("Filter Week", ["All"] + list(range(1, 13)), key="h_w")
        
        hist_df = df_main[df_main['Week'] > 0].copy() [cite: 11]
        if p_filter != "All": hist_df = hist_df[hist_df['Player'] == p_filter]
        if w_filter != "All": hist_df = hist_df[hist_df['Week'] == int(w_filter)]

        # Move Counts and DNF to the end
        end_cols = ['Pars_Count', 'Birdies_Count', 'Eagle_Count', 'DNF']
        cols_to_show = [c for c in hist_df.columns if c not in ['PIN', 'session_id']]
        start_cols = [c for c in cols_to_show if c not in end_cols and c != 'GGG_pts']
        
        hist_df = hist_df[start_cols + ['GGG_pts'] + end_cols]
        st.dataframe(hist_df.sort_values(["Week", "Player"], ascending=[False, True]), use_container_width=True, hide_index=True)

# --- TAB 6: ADMIN ---
with tabs[5]:
    st.subheader("⚙️ Admin Settings") [cite: 12]
    admin_pw = st.text_input("Admin Password", type="password", key="adm_key") [cite: 12]
    if admin_pw == ADMIN_PASSWORD:
        st.session_state["authenticated"] = True
        if st.button("Refresh Database"):
            st.cache_data.clear()
            st.rerun() [cite: 10, 12]

# --- TAB 8: REGISTRATION ---
with tabs[7]:
    st.header("👤 Player Registration") [cite: 18]
    with st.form("reg_form", clear_on_submit=True):
        new_name = st.text_input("Name") [cite: 18, 19]
        new_pin = st.text_input("4-Digit PIN", max_chars=4, type="password") [cite: 18, 19]
        starting_hcp = st.number_input("Handicap", 0, 36, 10) [cite: 18, 19]
        
        if st.form_submit_button("Register"):
            if new_name and len(new_pin) == 4:
                new_reg = pd.DataFrame([{
                    "Week": 0, "Player": new_name, "PIN": new_pin, 
                    "Handicap": starting_hcp, "Total_Score": 0, "DNF": True,
                    "Pars_Count": 0, "Birdies_Count": 0, "Eagle_Count": 0, "Net_Score": 0, "GGG_pts": 0
                }]) [cite: 19]
                conn.update(data=pd.concat([df_main, new_reg], ignore_index=True)) [cite: 20]
                st.cache_data.clear()
                st.success("Registered!")
                st.rerun() [cite: 10, 20]
