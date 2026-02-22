import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import time
import random
import altair as alt

# --- 1. CONFIGURATION & SESSION STATE ---
st.set_page_config(page_title="2026 GGGolf Summer League", layout="wide")

ADMIN_PASSWORD = "InsigniaSeahawks6145"
REGISTRATION_KEY = "GG2026"
SESSION_TIMEOUT = 4 * 60 * 60 

if "authenticated" not in st.session_state: st.session_state["authenticated"] = False
if "unlocked_player" not in st.session_state: st.session_state["unlocked_player"] = None
if "login_timestamp" not in st.session_state: st.session_state["login_timestamp"] = 0
if "reg_access" not in st.session_state: st.session_state["reg_access"] = False

conn = st.connection("gsheets", type=GSheetsConnection)

# Schema to prevent KeyErrors and Data Wipes
MASTER_COLUMNS = [
    'Week', 'Player', 'PIN', 'Pars_Count', 'Birdies_Count', 
    'Eagle_Count', 'Total_Score', 'Handicap', 'Net_Score', 'DNF'
]

FEDEX_POINTS = {
    1: 100, 2: 77, 3: 64, 4: 54, 5: 47, 6: 41,
    7: 36, 8: 31, 9: 27, 10: 24, 11: 21, 12: 18, 13: 16
}

# --- 2. CORE FUNCTIONS ---

def load_data():
    try:
        data = conn.read(ttl=2)
        if data is None or data.empty or 'Player' not in data.columns: 
            return pd.DataFrame(columns=MASTER_COLUMNS)
        
        df = data.dropna(how='all')
        for col in MASTER_COLUMNS:
            if col not in df.columns:
                df[col] = 0 if col != 'Player' else ""

        numeric_cols = ['Week', 'Total_Score', 'Net_Score', 'Pars_Count', 'Birdies_Count', 'Eagle_Count', 'Handicap']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        df['DNF'] = df['DNF'].astype(bool) if 'DNF' in df.columns else False
        return df[df['Player'] != ""]
    except:
        return pd.DataFrame(columns=MASTER_COLUMNS)

def load_live_data():
    hole_cols = [str(i) for i in range(1, 10)]
    try:
        df = conn.read(worksheet="LiveScores", ttl=2)
        if df is None or df.empty or 'Player' not in df.columns:
            return pd.DataFrame(columns=['Player'] + hole_cols)
        
        # Cleanup headers to prevent 1.1, 2.1 duplicates
        df.columns = [str(c).strip().split('.')[0] for c in df.columns]
        for col in hole_cols:
            if col not in df.columns: df[col] = 0
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
        return df[['Player'] + hole_cols]
    except:
        return pd.DataFrame(columns=['Player'] + hole_cols)

def update_live_score(player, hole, strokes):
    """Updates live score with exponential backoff for high traffic."""
    df_live = load_live_data()
    hole_col = str(hole)
    
    if player in df_live['Player'].values:
        df_live.loc[df_live['Player'] == player, hole_col] = int(strokes)
    else:
        new_row = {str(i): 0 for i in range(1, 10)}
        new_row['Player'] = player
        new_row[hole_col] = int(strokes)
        df_live = pd.concat([df_live, pd.DataFrame([new_row])], ignore_index=True)
    
    hole_cols = [str(i) for i in range(1, 10)]
    df_live = df_live[['Player'] + hole_cols]

    max_retries = 5
    for attempt in range(max_retries):
        try:
            conn.update(worksheet="LiveScores", data=df_live)
            st.cache_data.clear()
            st.toast(f"✅ Hole {hole} Updated!")
            return 
        except Exception:
            if attempt < max_retries - 1:
                time.sleep((2 ** attempt) + (random.random()))
            else:
                st.error("⛳ Connection busy. Please wait a moment and try again.")

def calculate_rolling_handicap(player_df, target_week):
    try:
        excluded_weeks = [0, 4, 8, 12]
        rounds = player_df[(~player_df['Week'].isin(excluded_weeks)) & (player_df['DNF'] == False) & (player_df['Week'] < target_week)].sort_values('Week', ascending=False)
        
        starting_hcp = 10.0
        reg_row = player_df[player_df['Week'] == 0]
        if not reg_row.empty:
            starting_hcp = float(reg_row['Handicap'].iloc[0])
            
        if len(rounds) == 0: return float(starting_hcp)
        
        last_4 = rounds.head(4)['Total_Score'].tolist()
        last_4.sort()
        hcp = round(sum(last_4[:3]) / 3 - 36, 1) if len(last_4) >= 4 else round(sum(last_4)/len(last_4)-36, 1)
        return float(hcp)
    except: return 10.0

def save_weekly_data(week, player, pars, birdies, eagles, score_val, hcp_val, pin):
    st.cache_data.clear()
    existing_data = load_data()
    
    if existing_data.empty and EXISTING_PLAYERS:
        st.error("❌ Data Sync Error. Please refresh before saving.")
        return

    is_dnf = (score_val == "DNF")
    final_gross = 0 if is_dnf else int(score_val)
    new_entry = pd.DataFrame([{
        'Week': week, 'Player': player, 'Pars_Count': pars, 'Birdies_Count': birdies, 
        'Eagle_Count': eagles, 'Total_Score': final_gross, 'Handicap': hcp_val, 
        'Net_Score': (final_gross - hcp_val) if not is_dnf else 0, 'DNF': is_dnf, 'PIN': pin
    }])
    
    updated_df = pd.concat([existing_data[~((existing_data['Week'] == week) & (existing_data['Player'] == player))], new_entry], ignore_index=True)
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            conn.update(data=updated_df[MASTER_COLUMNS])
            st.success("Score Posted!")
            st.cache_data.clear()
            time.sleep(1)
            st.rerun()
            return
        except:
            time.sleep(1 + random.random())

# --- 3. DATA PROCESSING ---
df_main = load_data()
EXISTING_PLAYERS = sorted(df_main['Player'].unique().tolist()) if not df_main.empty else []

# --- 4. APP UI ---
st.markdown("<div style='text-align: center;'>", unsafe_allow_html=True)
st.image("GGGOLF-2.png", width=120) 
st.markdown("<h1>GGGolf Summer League 2026</h1>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

tabs = st.tabs(["📝 Scorecard", "🏆 Standings", "🔴 Live Round", "📅 History", "ℹ️ League Info", "👤 Registration", "⚙️ Admin"])

with tabs[0]: # Scorecard
    if not EXISTING_PLAYERS: st.warning("No players registered yet.")
    else:
        player_select = st.selectbox("Select Player", EXISTING_PLAYERS)
        is_unlocked = (st.session_state["unlocked_player"] == player_select and (time.time() - st.session_state["login_timestamp"]) < SESSION_TIMEOUT) or st.session_state["authenticated"]
        
        if not is_unlocked:
            user_pin = st.text_input("Enter PIN", type="password", key=f"pin_{player_select}")
            if user_pin:
                p_info = df_main[df_main['Player'] == player_select]
                stored_pin = str(p_info[p_info['Week'] == 0]['PIN'].iloc[0]).split('.')[0].strip() if not p_info.empty else ""
                if user_pin.strip() == stored_pin:
                    st.session_state.update({"unlocked_player": player_select, "login_timestamp": time.time()})
                    st.rerun()
                else: st.error("❌ Incorrect PIN.")
        else:
            p_data = df_main[df_main['Player'] == player_select]
            st.divider()
            w_s = st.selectbox("Select Week", range(1, 15))
            current_hcp = calculate_rolling_handicap(p_data, w_s)
            h_disp = f"+{abs(current_hcp)}" if current_hcp < 0 else f"{current_hcp}"
            
            st.markdown(f"### 📊 {player_select}'s Stats for Week {w_s}")
            m1, m2 = st.columns(2)
            m1.metric("HCP for Week", h_disp)
            
            with st.form("score_entry"):
                s_v = st.selectbox("Gross Score", ["DNF"] + [str(i) for i in range(25, 120)], key=f"gross_{w_s}")
                h_r = st.number_input("HCP to Apply", -10.0, 40.0, value=float(current_hcp), key=f"h_{w_s}")
                c1, c2, c3 = st.columns(3)
                p_c = c1.number_input("Pars", 0, 18, key=f"p_{w_s}")
                b_c = c2.number_input("Birdies", 0, 18, key=f"b_{w_s}")
                e_c = c3.number_input("Eagles", 0, 18, key=f"e_{w_s}")
                if st.form_submit_button("Submit Score"):
                    pin = str(p_data[p_data['Week'] == 0]['PIN'].iloc[0]).split('.')[0].strip()
                    save_weekly_data(w_s, player_select, p_c, b_c, e_c, s_v, h_r, pin)

with tabs[1]: # Standings
    st.subheader("🏆 Season Standings")
    if not df_main.empty:
        v = df_main[(df_main['Week'] > 0) & (df_main['DNF'] == False)].copy()
        if not v.empty:
            v['Pts'] = 0.0
            for w in v['Week'].unique():
                m = v['Week'] == w
                v.loc[m, 'R'] = v.loc[m, 'Net_Score'].rank(method='min')
                for idx, row in v[m].iterrows(): v.at[idx, 'Pts'] = FEDEX_POINTS.get(int(row['R']), 10.0)
            res = v.groupby('Player').agg({'Pts':'sum', 'Net_Score':'mean'}).reset_index().rename(columns={'Pts':'Total Pts', 'Net_Score':'Avg Net'})
            res['Avg Net'] = res['Avg Net'].round(1)
            st.dataframe(res.sort_values(['Total Pts', 'Avg Net'], ascending=[False, True]), use_container_width=True, hide_index=True)

with tabs[2]: # Live Round
    st.subheader("🔴 Live Round Tracking")
    curr_p = st.session_state.get("unlocked_player")
    if curr_p:
        with st.expander(f"Update Score for {curr_p}", expanded=True):
            c1, c2, c3 = st.columns([2, 1, 1])
            h_u = c1.selectbox("Hole", range(1, 10), key="lh")
            s_u = c2.number_input("Strokes", 1, 15, 4, key="ls")
            if c3.button("Post", use_container_width=True):
                update_live_score(curr_p, h_u, s_u)
                st.rerun()
    l_df = load_live_data()
    if not l_df.empty:
        l_df['Total'] = l_df[[str(i) for i in range(1, 10)]].sum(axis=1)
        st.dataframe(l_df.sort_values("Total"), use_container_width=True, hide_index=True)

with tabs[3]: # History
    st.subheader("📅 History")
    h_df = df_main[df_main['Week'] > 0]
    if not h_df.empty:
        st.dataframe(h_df[['Week', 'Player', 'Total_Score', 'Net_Score', 'Handicap']].sort_values(['Week', 'Net_Score'], ascending=[False, True]), use_container_width=True, hide_index=True)

with tabs[5]: # Registration
    st.header("👤 Registration")
    if not st.session_state["reg_access"]:
        if st.text_input("League Key", type="password") == REGISTRATION_KEY:
            if st.button("Unlock"): st.session_state["reg_access"] = True; st.rerun()
    else:
        with st.form("r"):
            n, p, h = st.text_input("Name"), st.text_input("PIN", max_chars=4), st.number_input("HCP", -10.0, 40.0, 10.0)
            if st.form_submit_button("Register"):
                if n and len(p) == 4:
                    new_reg = pd.DataFrame([{"Week": 0, "Player": n, "PIN": p, "Handicap": h, "DNF": True, "Pars_Count": 0, "Birdies_Count": 0, "Eagle_Count": 0, "Total_Score": 0, "Net_Score": 0}])
                    updated_reg = pd.concat([df_main, new_reg], ignore_index=True)
                    conn.update(data=updated_reg[MASTER_COLUMNS])
                    st.cache_data.clear(); time.sleep(1); st.session_state["reg_access"] = False; st.rerun()

with tabs[6]: # Admin
    if st.text_input("Admin Password", type="password") == ADMIN_PASSWORD:
        st.session_state["authenticated"] = True
        if st.button("🚨 Reset Live Board"):
            conn.update(worksheet="LiveScores", data=pd.DataFrame(columns=['Player'] + [str(i) for i in range(1, 10)]))
            st.rerun()
