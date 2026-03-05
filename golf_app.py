import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import time
import random
import altair as alt

# --- 1. CONFIGURATION & SESSION STATE ---
st.set_page_config(page_title="2026 GGGolf Summer League", layout="wide")

ADMIN_PASSWORD = "InsigniaSeahawks6145"
REGISTRATION_KEY = "goatpigcowfishduck2026"
SESSION_TIMEOUT = 2 * 60 * 60 

if "authenticated" not in st.session_state: st.session_state["authenticated"] = False
if "unlocked_player" not in st.session_state: st.session_state["unlocked_player"] = None
if "login_timestamp" not in st.session_state: st.session_state["login_timestamp"] = 0
if "reg_access" not in st.session_state: st.session_state["reg_access"] = False

conn = st.connection("gsheets", type=GSheetsConnection)

MASTER_COLUMNS = [
    'Week', 'Player', 'PIN', 'Pars_Count', 'Birdies_Count', 
    'Eagle_Count', 'Total_Score', 'Handicap', 'Net_Score', 'DNF'
]

GGG_POINTS = {
    1: 100, 2: 77, 3: 64, 4: 54, 5: 47, 6: 41,
    7: 36, 8: 31, 9: 27, 10: 24, 11: 21, 12: 16, 13: 13, 14: 9,
    15: 5, 16: 3, 17: 1 
}

# --- 2. CORE FUNCTIONS (OPTIMIZED) ---

@st.cache_data(ttl=60)
def load_data():
    try:
        data = conn.read(ttl=60)
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
    except Exception:
        return pd.DataFrame(columns=MASTER_COLUMNS)

@st.cache_data(ttl=5)
def load_live_data():
    hole_cols = [str(i) for i in range(1, 10)]
    try:
        df = conn.read(worksheet="LiveScores", ttl=5)
        if df is None or df.empty or 'Player' not in df.columns:
            return pd.DataFrame(columns=['Player'] + hole_cols)
        df.columns = [str(c).strip().split('.')[0] for c in df.columns]
        for col in hole_cols:
            if col not in df.columns: df[col] = 0
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
        return df[['Player'] + hole_cols]
    except Exception:
        return pd.DataFrame(columns=['Player'] + hole_cols)

def calculate_rolling_handicap(p_data, target_week):
    past = p_data[(p_data['Week'] > 0) & (p_data['Week'] < target_week) & (p_data['DNF'] == False)]
    if past.empty: return 0.0
    recent = past.sort_values('Week', ascending=False).head(4)
    if len(recent) < 3: return round(recent['Total_Score'].mean() - 36, 1)
    best_3 = recent.sort_values('Total_Score').head(3)
    return round(best_3['Total_Score'].mean() - 36, 1)

def update_live_score(player, hole, strokes):
    try:
        df_live = load_live_data()
        if player in df_live['Player'].values:
            df_live.loc[df_live['Player'] == player, str(hole)] = int(strokes)
            conn.update(worksheet="LiveScores", data=df_live)
            load_live_data.clear()
            st.toast(f"✅ Saved Hole {hole}")
    except Exception as e:
        st.error(f"Error: {e}")

def save_weekly_data(week, player, pars, birdies, eagles, score_val, hcp_val, pin):
    df_main = load_data()
    is_dnf = (score_val == "DNF")
    gross = 0 if is_dnf else int(score_val)
    new_row = pd.DataFrame([{
        'Week': week, 'Player': player, 'Pars_Count': pars, 'Birdies_Count': birdies, 
        'Eagle_Count': eagles, 'Total_Score': gross, 'Handicap': hcp_val, 
        'Net_Score': (gross - hcp_val) if not is_dnf else 0, 'DNF': is_dnf, 'PIN': pin
    }])
    updated = pd.concat([df_main[~((df_main['Week'] == week) & (df_main['Player'] == player))], new_row], ignore_index=True)
    conn.update(data=updated[MASTER_COLUMNS])
    load_data.clear()
    st.success("Score Submitted!")
    time.sleep(1)
    st.rerun()

# --- 3. UI LAYOUT ---
df_main = load_data()
EXISTING_PLAYERS = sorted(df_main['Player'].unique().tolist()) if not df_main.empty else []

tabs = st.tabs(["📇 Scorecard", "🏆 Standings", "ℹ️ League Info", "📅 History", "📡 Live Round", "👤 Registration", "⚙️ Admin"])

# --- TAB 0: SCORECARD ---
with tabs[0]:
    if not EXISTING_PLAYERS: st.warning("No players registered yet.")
    else:
        player_select = st.selectbox("Select Player", EXISTING_PLAYERS)
        is_unlocked = (st.session_state["unlocked_player"] == player_select and (time.time() - st.session_state["login_timestamp"]) < SESSION_TIMEOUT) or st.session_state["authenticated"]
        
        if not is_unlocked:
            user_pin = st.text_input("Enter PIN", type="password", key=f"pin_{player_select}")
            if user_pin:
                p_info = df_main[df_main['Player'] == player_select]
                reg_row = p_info[p_info['Week'] == 0]
                stored_pin = str(reg_row['PIN'].iloc[0]).split('.')[0].strip() if not reg_row.empty else ""
                if user_pin.strip() == stored_pin:
                    st.session_state.update({"unlocked_player": player_select, "login_timestamp": time.time()})
                    st.rerun()
                else: st.error("❌ Incorrect PIN.")
        else:
            p_data = df_main[df_main['Player'] == player_select]
            w_s = st.selectbox("Select Week", range(1, 15))
            
            if w_s in [4, 8]:
                current_hcp = 0.0
                st.info("💡 GGG Event: No handicap applied for this round.")
            elif w_s == 12:
                current_hcp = calculate_rolling_handicap(p_data, w_s)
                st.info("🔥 GGG Double Points Event: Rolling handicap is active!")
            else:
                current_hcp = calculate_rolling_handicap(p_data, w_s)
            
            h_disp = f"+{abs(current_hcp)}" if current_hcp < 0 else f"{current_hcp}"
            played_rounds = p_data[(p_data['Week'] > 0) & (p_data['DNF'] == False)].sort_values('Week')
            
            st.markdown(f"### 📊 {player_select}'s Season Dashboard")
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Current HCP", h_disp)
            m2.metric("Avg Net", f"{played_rounds['Net_Score'].mean():.1f}" if not played_rounds.empty else "N/A")
            m3.metric("Total Pars", int(played_rounds['Pars_Count'].sum()))
            m4.metric("Total Birdies", int(played_rounds['Birdies_Count'].sum()))
            m5.metric("Total Eagles", int(played_rounds['Eagle_Count'].sum()))

            if not played_rounds.empty:
                chart = alt.Chart(played_rounds).mark_line(color='#2e7d32', strokeWidth=3).encode(
                    x=alt.X('Week:O'), y=alt.Y('Net_Score:Q', scale=alt.Scale(reverse=True, zero=False))
                ) + alt.Chart(played_rounds).mark_point(color='#2e7d32', size=100, filled=True).encode(x='Week:O', y='Net_Score:Q')
                st.altair_chart(chart.properties(height=300), use_container_width=True)

            st.divider()
            with st.form("score_entry", clear_on_submit=True):
                s_v = st.selectbox("Gross Score", ["DNF"] + [str(i) for i in range(25, 120)], key=f"gross_{w_s}")
                h_r = st.number_input("HCP to Apply", value=float(current_hcp), key=f"hcp_{w_s}")
                c1, c2, c3 = st.columns(3)
                p_c = c1.number_input("Pars", 0, 18, key=f"pars_{w_s}")
                b_c = c2.number_input("Birdies", 0, 18, key=f"birdies_{w_s}")
                e_c = c3.number_input("Eagles", 0, 18, key=f"eagles_{w_s}")
                
                if st.form_submit_button("Submit Score"):
                    reg_row = p_data[p_data['Week'] == 0]
                    pin = str(reg_row['PIN'].iloc[0]).split('.')[0].strip()
                    save_weekly_data(w_s, player_select, p_c, b_c, e_c, s_v, h_r, pin)

# --- TAB 1: STANDINGS ---
with tabs[1]:
    st.subheader("🏆 Standings")
    if not df_main.empty:
        v = df_main[(df_main['Week'] > 0) & (df_main['DNF'] == False)].copy()
        if not v.empty:
            v['Pts'] = 0.0
            for w in v['Week'].unique():
                m = v['Week'] == w
                v.loc[m, 'R'] = v.loc[m, 'Net_Score'].rank(method='min')
                for idx, row in v[m].iterrows():
                    base = GGG_POINTS.get(int(row['R']), 10.0)
                    v.at[idx, 'Pts'] = base * 2 if w == 12 else base
            res = v.groupby('Player').agg({'Pts':'sum', 'Net_Score':'mean'}).reset_index()
            res = res.rename(columns={'Pts':'Total GGG Points', 'Net_Score':'Avg Net'})
            st.dataframe(res.sort_values(['Total GGG Points', 'Avg Net'], ascending=[False, True]), use_container_width=True, hide_index=True)

# --- TAB 2: LEAGUE INFO ---
with tabs[2]:
    info_cat = st.radio("Select Category", ["About Us", "Rules", "Schedule", "Prizes"], horizontal=True)
    if info_cat == "About Us":
        st.subheader("GGGolf Summer League 2026")
        st.write("Established in 2022, GGGolf is a governed competitive community dedicated to high-integrity play and camaraderie. We provide a rigorous structural framework that allows players of all skill levels to excel in a tournament-style environment while ensuring the league's long-term prestige.")
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🏛️ League Officers")
            st.markdown("* **President**: Txoovnom Vang\n* **Vice President**: Cory Vue\n* **Finance**: Mike Yang")
            st.markdown("**Executive Command:** The Officers constitute the league’s primary governing body. They are responsible for strategic enablement, financial stewardship, and operational oversight.")
        with col2:
            st.subheader("⚖️ Players Committee")
            st.markdown("* **Rules**: Lex Vue\n* **Representation**: Long Lee & Deng Kue")
            st.markdown("**Representative Advocacy:** The Committee serves as the formal intermediary between the general membership and the Executive Command. Their mandate is to maintain competitive standards and evaluate member feedback.")
        st.divider()
        with st.expander("GGGolf Organizational Protocol", expanded=False):
            st.markdown("1. **Administrative Authority:** Final decisions reside with the **League Officers**.\n2. **Consultative Feedback:** Concerns must follow the chain of command by bringing matters to the **Players Committee**.")

# --- TAB 3: HISTORY ---
with tabs[3]:
    st.subheader("📅 Weekly Scores & GGG Points")
    h_df = df_main[(df_main['Week'] > 0) & (df_main['DNF'] == False)].copy()
    if not h_df.empty:
        h_df['Points'] = 0.0
        for w in h_df['Week'].unique():
            mask = h_df['Week'] == w
            h_df.loc[mask, 'Rank'] = h_df.loc[mask, 'Net_Score'].rank(method='min')
            for idx, row in h_df[mask].iterrows():
                base = GGG_POINTS.get(int(row['Rank']), 10.0)
                h_df.at[idx, 'Points'] = base * 2 if w == 12 else base
        f1, f2 = st.columns(2)
        sel_p = f1.selectbox("Filter by Player", ["All Players"] + sorted(h_df['Player'].unique().tolist()))
        sel_w = f2.selectbox("Filter by Week", ["All Weeks"] + sorted(h_df['Week'].unique().tolist()))
        fil = h_df.copy()
        if sel_p != "All Players": fil = fil[fil['Player'] == sel_p]
        if sel_w != "All Weeks": fil = fil[fil['Week'] == sel_w]
        st.dataframe(fil[['Week', 'Player', 'Total_Score', 'Handicap', 'Net_Score', 'Points']].sort_values(['Week', 'Points'], ascending=[False, False]), use_container_width=True, hide_index=True)

# --- TAB 4: LIVE ROUND ---
with tabs[4]:
    st.subheader("📡 Live Round Scorecard")
    l_df = load_live_data() # Removed force_refresh=True
    if not EXISTING_PLAYERS: st.info("Register to start live scoring.")
    else:
        active_p = st.selectbox("I am scoring for:", EXISTING_PLAYERS, key="live_p")
        h_idx = st.selectbox("Hole", range(1, 10))
        cur_s = int(l_df.loc[l_df['Player'] == active_p, str(h_idx)].iloc[0]) if active_p in l_df['Player'].values else 0
        new_s = st.number_input("Strokes", 0, 15, value=cur_s)
        if st.button("Save Stroke"): update_live_score(active_p, h_idx, new_s)
        st.divider()
        st.subheader("📊 Live Board")
        st.dataframe(load_live_data(), use_container_width=True, hide_index=True)

# --- TAB 5: REGISTRATION ---
with tabs[5]:
    st.header("👤 Registration")
    if not st.session_state["reg_access"]:
        user_key = st.text_input("League Key", type="password")
        if user_key == REGISTRATION_KEY:
            st.session_state["reg_access"] = True
            st.rerun()
    else:
        with st.form("r"):
            n, p = st.text_input("Name"), st.text_input("PIN", max_chars=4)
            if st.form_submit_button("Register"):
                if n and len(p) == 4:
                    new_reg = pd.DataFrame([{'Week':0, 'Player':n, 'PIN':p, 'Handicap':0.0, 'DNF':True, 'Pars_Count':0, 'Birdies_Count':0, 'Eagle_Count':0, 'Total_Score':0, 'Net_Score':0}])
                    conn.update(data=pd.concat([df_main, new_reg], ignore_index=True)[MASTER_COLUMNS])
                    l_df = load_live_data()
                    if n not in l_df['Player'].values:
                        new_live = pd.DataFrame([{'Player': n, **{str(i): 0 for i in range(1, 10)}}])
                        conn.update(worksheet="LiveScores", data=pd.concat([l_df, new_live], ignore_index=True))
                    load_data.clear() # Specific clear
                    load_live_data.clear() # Specific clear
                    st.session_state["reg_access"] = False
                    st.success(f"✅ {n} registered!")
                    st.rerun()

# --- TAB 6: ADMIN ---
with tabs[6]:
    if st.text_input("Admin Password", type="password") == ADMIN_PASSWORD:
        st.session_state["authenticated"] = True
        if st.button("🚨 Reset Live Board"):
            conn.update(worksheet="LiveScores", data=pd.DataFrame(columns=['Player'] + [str(i) for i in range(1, 10)]))
            load_live_data.clear()
            st.rerun()
