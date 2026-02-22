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
        rename_map = {
            'Gross Score': 'Total_Score',
            'Pars': 'Pars_Count',
            'Birdies': 'Birdies_Count',
            'Eagles': 'Eagle_Count'
        }
        df = df.rename(columns=rename_map)
        if 'animal_pts' in df.columns:
            df = df.drop(columns=['animal_pts'])
        return df
    except:
        return pd.DataFrame()

def calculate_rolling_handicap(player_df):
    # Filter for actual rounds (Week > 0 and not DNF)
    rounds = player_df[(player_df['Week'] > 0) & (player_df['DNF'] == False)].sort_values('Week', ascending=False)
    
    # If fewer than 4 rounds, use the average of what's available or the starting handicap
    if len(rounds) == 0:
        starting_hcp = player_df[player_df['Week'] == 0]['Handicap'].values
        return int(starting_hcp[0]) if len(starting_hcp) > 0 else 10
    
    last_4 = rounds.head(4)['Total_Score'].tolist()
    
    if len(last_4) >= 4:
        last_4.sort()
        best_3 = last_4[:3] # Drop the highest (last in sorted list)
        return round(sum(best_3) / 3 - 36, 1) # Relative to Par 36
    else:
        # If they haven't played 4 rounds yet, average what they have relative to par
        return round(sum(last_4) / len(last_4) - 36, 1)

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
        if 'GGG_pts' in existing_data.columns:
            existing_data = existing_data.drop(columns=['GGG_pts'])
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
    if 'GGG_pts' in df_main.columns:
        df_main = df_main.drop(columns=['GGG_pts'])
    
    EXISTING_PLAYERS = sorted(df_main['Player'].unique().tolist())
    df_main['Week'] = pd.to_numeric(df_main['Week'], errors='coerce').fillna(0)
    df_main['Net_Score'] = pd.to_numeric(df_main['Net_Score'], errors='coerce').fillna(0)
    df_main['DNF'] = df_main.get('DNF', False).astype(bool)
    
    df_main['GGG_pts'] = 0.0
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

# --- STEP 4: UI ---
st.markdown("<div style='text-align: center;'>", unsafe_allow_html=True)
st.image("GGGOLF-2.png", width=120) 
st.markdown("<h1>GGGolf Summer League 2026</h1>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

tabs = st.tabs(["📝 Scorecard", "🏆 Standings", "📅 History", "⚙️ Admin", "👤 Registration"])

with tabs[0]: # Scorecard
    if not EXISTING_PLAYERS:
        st.warning("No players registered.")
    else:
        player_select = st.selectbox("Select Player", EXISTING_PLAYERS, key="p_sel")
        current_time = time.time()
        
        is_unlocked = (st.session_state["unlocked_player"] == player_select and 
                       (current_time - st.session_state["login_timestamp"]) < SESSION_TIMEOUT)
        
        if st.session_state["authenticated"]: is_unlocked = True

        if not is_unlocked:
            st.info(f"🔒 {player_select} is locked.")
            pin_key = f"pin_{player_select}_{st.session_state['session_id']}"
            user_pin_input = st.text_input("Enter PIN to Unlock", type="password", key=pin_key)
            if user_pin_input:
                p_info = df_main[df_main['Player'] == player_select]
                if not p_info.empty:
                    stored_pin = str(p_info.iloc[0].get('PIN', '')).split('.')[0].strip()
                    if user_pin_input.strip() == stored_pin:
                        st.session_state["unlocked_player"] = player_select
                        st.session_state["login_timestamp"] = current_time
                        st.rerun()
                    else:
                        st.error("❌ Incorrect PIN.")
        else:
            c1, c2 = st.columns([5, 1])
            c1.success(f"✅ **{player_select} Unlocked**")
            if c2.button("Logout 🔓", key="logout_btn"):
                st.session_state["unlocked_player"] = None
                st.session_state["login_timestamp"] = 0
                st.session_state["session_id"] += 1
                st.rerun()

            p_data = df_main[df_main['Player'] == player_select]
            valid_rounds = p_data[(p_data['Week'] > 0) & (p_data['DNF'] == False)]
            
            st.markdown(f"### 📊 {player_select}'s Season Dashboard")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Total Pars", int(p_data['Pars_Count'].sum()))
            m2.metric("Total Birdies", int(p_data['Birdies_Count'].sum()))
            m3.metric("Total Eagles", int(p_data['Eagle_Count'].sum()))
            
            avg_net = round(valid_rounds['Net_Score'].mean(), 1) if not valid_rounds.empty else 0
            m4.metric("Avg Net Score", avg_net)
            
            # Calculate rolling handicap for the current week
            current_hcp = calculate_rolling_handicap(p_data)
            st.info(f"💡 Based on your last 4 rounds, your calculated Handicap for this week is: **{current_hcp}**")
            st.divider()

            week_select = st.selectbox("Select Week to Enter Score", range(1, 13))
            
            with st.form("score_entry", clear_on_submit=True):
                score_select = st.selectbox("Gross Score", ["DNF"] + [str(i) for i in range(25, 120)])
                # Handicap input pre-filled with the rolling calculation
                hcp_in = st.number_input("Handicap", 0.0, 40.0, float(current_hcp), step=0.1)
                col1, col2, col3 = st.columns(3)
                s_p = col1.number_input("Pars this Week", 0, 18, 0)
                s_b = col2.number_input("Birdies this Week", 0, 18, 0)
                s_e = col3.number_input("Eagles this Week", 0, 18, 0)
                if st.form_submit_button("Submit Score"):
                    p_info = df_main[df_main['Player'] == player_select]
                    final_pin = str(p_info.iloc[0].get('PIN', '')).split('.')[0].strip()
                    save_data(week_select, player_select, s_p, s_b, s_e, score_select, hcp_in, final_pin)

with tabs[1]: # Standings
    st.subheader("🏆 League Standings")
    if not df_main.empty:
        standings = df_main.groupby('Player')['GGG_pts'].sum().reset_index()
        standings = standings.sort_values(by='GGG_pts', ascending=False).reset_index(drop=True)
        standings.index += 1
        st.dataframe(standings, use_container_width=True)

with tabs[2]: # History
    st.subheader("📅 Weekly History")
    if not df_main.empty:
        f1, f2 = st.columns(2)
        p_f = f1.selectbox("Filter Player", ["All"] + EXISTING_PLAYERS, key="hist_p")
        w_f = f2.selectbox("Filter Week", ["All"] + list(range(1, 13)), key="hist_w")
        
        hist = df_main[df_main['Week'] > 0].copy()
        if p_f != "All": hist = hist[hist['Player'] == p_f]
        if w_f != "All": hist = hist[hist['Week'] == int(w_f)]
        
        end_cols = ['Pars_Count', 'Birdies_Count', 'Eagle_Count', 'DNF']
        current_cols = [c for c in hist.columns if c not in ['PIN', 'session_id', 'animal_pts']]
        mid_cols = [c for c in current_cols if c not in end_cols and c != 'GGG_pts']
        
        hist = hist[mid_cols + ['GGG_pts'] + end_cols]
        st.dataframe(hist.sort_values(["Week", "Player"], ascending=[False, True]), use_container_width=True, hide_index=True)

with tabs[3]: # Admin
    if st.text_input("Admin Password", type="password") == ADMIN_PASSWORD:
        st.session_state["authenticated"] = True
        if st.button("Refresh App"):
            st.cache_data.clear()
            st.rerun()

with tabs[4]: # Registration
    st.header("👤 Player Registration")
    with st.form("reg"):
        n_n = st.text_input("Name")
        n_p = st.text_input("4-Digit PIN", max_chars=4)
        n_h = st.number_input("Handicap", 0.0, 36.0, 10.0)
        if st.form_submit_button("Register"):
            if n_n and len(n_p) == 4:
                new_p = pd.DataFrame([{"Week": 0, "Player": n_n, "PIN": n_p, "Handicap": n_h, "DNF": True, "Pars_Count": 0, "Birdies_Count": 0, "Eagle_Count": 0}])
                conn.update(data=pd.concat([df_main, new_p], ignore_index=True))
                st.cache_data.clear()
                st.rerun()
