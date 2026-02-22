import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import time

# --- STEP 1: CONFIGURATION ---
st.set_page_config(page_title="2026 GGGolf Summer League", layout="wide") 

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "unlocked_player" not in st.session_state:
    st.session_state["unlocked_player"] = None
if "login_timestamp" not in st.session_state:
    st.session_state["login_timestamp"] = 0
if "session_id" not in st.session_state:
    st.session_state["session_id"] = 0 

ADMIN_PASSWORD = "InsigniaSeahawks6145" 
SESSION_TIMEOUT = 4 * 60 * 60 
conn = st.connection("gsheets", type=GSheetsConnection)

FEDEX_POINTS = {
    1: 100, 2: 77, 3: 64, 4: 54, 5: 47, 6: 41,
    7: 36, 8: 31, 9: 27, 10: 24, 11: 21, 12: 18, 13: 16
}

# --- STEP 2: FUNCTIONS ---
def load_data():
    try:
        data = conn.read(ttl=0)
        df = data.dropna(how='all')
        
        # Data Recovery: Maps old test column names to new standard names
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
        return pd.DataFrame()

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
    }])
    
    if not existing_data.empty:
        updated_df = existing_data[~((existing_data['Week'] == week) & (existing_data['Player'] == player))]
        final_df = pd.concat([updated_df, new_entry], ignore_index=True)
    else:
        final_df = new_entry
        
    conn.update(data=final_df)
    st.cache_data.clear()
    st.rerun()

# --- STEP 3: DATA PROCESSING (FIXED CALCULATION) ---
df_main = load_data()

if not df_main.empty and 'Player' in df_main.columns:
    EXISTING_PLAYERS = sorted(df_main['Player'].unique().tolist())
    
    # 1. Ensure numeric types to prevent math errors
    df_main['Week'] = pd.to_numeric(df_main['Week'], errors='coerce').fillna(0)
    df_main['Net_Score'] = pd.to_numeric(df_main['Net_Score'], errors='coerce').fillna(0)
    
    # 2. Initialize the column
    df_main['GGG_pts'] = 0.0
    
    # 3. Calculate points week-by-week
    for w in df_main['Week'].unique():
        if w == 0: continue  # Skip registration week
        
        # Identify non-DNF players for this specific week
        mask = (df_main['Week'] == w) & (df_main.get('DNF', False) == False)
        
        if mask.any():
            # Calculate ranks for just these specific rows
            week_subset = df_main.loc[mask].copy()
            week_subset['rank'] = week_subset['Net_Score'].rank(ascending=True, method='min')
            
            # Map ranks to points and assign directly using the row indices
            df_main.loc[mask, 'GGG_pts'] = week_subset['rank'].map(FEDEX_POINTS).fillna(10)
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

# --- TAB 1: SCORECARD (WITH HARD LOGOUT) ---
with tab1:
    if not EXISTING_PLAYERS:
        st.warning("No players registered yet.")
    else:
        player_select = st.selectbox("Select Player", EXISTING_PLAYERS, key="p_sel")
        
        current_time = time.time()
        is_unlocked = (st.session_state["unlocked_player"] == player_select and 
                       (current_time - st.session_state["login_timestamp"]) < SESSION_TIMEOUT)
        
        if st.session_state["authenticated"]: 
            is_unlocked = True

        if not is_unlocked:
            st.info(f"🔒 {player_select} is locked.")
            pin_key = f"pin_box_{player_select}_{st.session_state['session_id']}"
            user_pin_input = st.text_input(f"Enter PIN for {player_select}", type="password", key=pin_key)
            
            if user_pin_input:
                player_info = df_main[df_main['Player'] == player_select]
                if not player_info.empty:
                    stored_pin = str(player_info.iloc[0].get('PIN', '')).split('.')[0].strip()
                    if user_pin_input.strip() == stored_pin:
                        st.session_state["unlocked_player"] = player_select
                        st.session_state["login_timestamp"] = current_time
                        st.rerun()
                    else:
                        st.error("❌ Incorrect PIN.")
        else:
            col_h1, col_h2 = st.columns([5, 1])
            col_h1.success(f"✅ **{player_select} Unlocked**")
            if col_h2.button("Logout 🔓", use_container_width=True):
                st.session_state["unlocked_player"] = None
                st.session_state["login_timestamp"] = 0
                st.session_state["session_id"] += 1 
                st.rerun()

            week_select = st.selectbox("Select Week", range(1, 13), key="w_sel")
            p_data = df_main[df_main['Player'] == player_select]
            st.write(f"### 📊 Season Stats Summary")
            sc1, sc2, sc3 = st.columns(3)
            sc1.metric("Total Pars", int(p_data['Pars_Count'].sum()))
            sc2.metric("Total Birdies", int(p_data['Birdies_Count'].sum()))
            sc3.metric("Total Eagles", int(p_data['Eagle_Count'].sum()))
            st.divider()

            with st.form("score_entry", clear_on_submit=True):
                score_select = st.selectbox("Gross Score", ["DNF"] + [str(i) for i in range(25, 120)])
                hcp_in = st.number_input("Handicap", 0, 40, 10)
                c1, c2, c3 = st.columns(3)
                s_p = c1.number_input("Pars", 0, 18, 0)
                s_b = c2.number_input("Birdies", 0, 18, 0)
                s_e = c3.number_input("Eagles", 0, 18, 0)
                
                if st.form_submit_button("Submit Score"):
                    player_info = df_main[df_main['Player'] == player_select]
                    final_pin = str(player_info.iloc[0].get('PIN', '')).split('.')[0].strip()
                    save_data(week_select, player_select, s_p, s_b, s_e, score_select, hcp_in, final_pin)

# --- TAB 2: STANDINGS ---
with tab2:
    st.header("🏆 League Standings")
    if not df_main.empty:
        leaderboard = df_main.groupby('Player')['GGG_pts'].sum().reset_index()
        leaderboard = leaderboard.sort_values(by='GGG_pts', ascending=False).reset_index(drop=True)
        leaderboard.index += 1
        st.dataframe(leaderboard, use_container_width=True)

# --- TAB 3: HISTORY ---
with tab3:
    st.subheader("📅 Weekly History")
    if not df_main.empty:
        history_df = df_main[df_main['Week'] > 0].copy()
        
        # Display logic and column ordering
        display_cols = [c for c in history_df.columns if c not in ['PIN', 'session_id']]
        end_cols = ['Pars_Count', 'Birdies_Count', 'Eagle_Count', 'DNF']
        start_cols = [c for c in display_cols if c not in end_cols and c != 'GGG_pts']
        history_df = history_df[start_cols + ['GGG_pts'] + end_cols]
        
        st.dataframe(history_df.sort_values(["Week", "Player"], ascending=[False, True]), use_container_width=True, hide_index=True)

# --- TAB 6: ADMIN ---
with tab6:
    st.subheader("⚙️ Admin Settings")
    admin_pw = st.text_input("Admin Password", type="password", key="adm_key")
    if admin_pw == ADMIN_PASSWORD:
        st.session_state["authenticated"] = True
        if st.button("🔄 Force Refresh Database"):
            st.cache_data.clear()
            st.rerun()

# --- TAB 8: REGISTRATION ---
with tab8:
    st.header("👤 Player Registration")
    with st.form("reg_form", clear_on_submit=True):
        new_name = st.text_input("Full Name")
        new_pin = st.text_input("4-Digit PIN", max_chars=4, type="password")
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

