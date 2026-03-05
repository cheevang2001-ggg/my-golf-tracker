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
SESSION_TIMEOUT = 4 * 60 * 60 

if "authenticated" not in st.session_state: st.session_state["authenticated"] = False
if "unlocked_player" not in st.session_state: st.session_state["unlocked_player"] = None
if "login_timestamp" not in st.session_state: st.session_state["login_timestamp"] = 0
if "reg_access" not in st.session_state: st.session_state["reg_access"] = False

conn = st.connection("gsheets", type=GSheetsConnection)

MASTER_COLUMNS = [
    'Week', 'Player', 'PIN', 'Pars_Count', 'Birdies_Count', 
    'Eagle_Count', 'Total_Score', 'Handicap', 'Net_Score', 'DNF'
]

FEDEX_POINTS = {
    1: 100, 2: 77, 3: 64, 4: 54, 5: 47, 6: 41,
    7: 36, 8: 31, 9: 27, 10: 24, 11: 21, 12: 16, 13: 13, 14: 9,
    15: 5, 16: 3, 17: 1 
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

def load_live_data(force_refresh=True):
    hole_cols = [str(i) for i in range(1, 10)]
    try:
        ttl_val = 0 if force_refresh else 2
        df = conn.read(worksheet="LiveScores", ttl=ttl_val)
        if df is None or df.empty or 'Player' not in df.columns:
            return pd.DataFrame(columns=['Player'] + hole_cols)
        
        df.columns = [str(c).strip().split('.')[0] for c in df.columns]
        for col in hole_cols:
            if col not in df.columns: df[col] = 0
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
        return df[['Player'] + hole_cols]
    except:
        return pd.DataFrame(columns=['Player'] + hole_cols)

def update_live_score(player, hole, strokes):
    try:
        st.cache_data.clear()
        df_live = load_live_data(force_refresh=True)
        if player not in df_live['Player'].values:
            st.error(f"❌ Player '{player}' not found. Please re-register.")
            return
        hole_col = str(hole)
        df_live.loc[df_live['Player'] == player, hole_col] = int(strokes)
        conn.update(worksheet="LiveScores", data=df_live)
        st.cache_data.clear()
        st.toast(f"✅ Saved {player}: Hole {hole} = {strokes}")
        time.sleep(0.5) 
    except Exception as e:
        st.error(f"🚨 Update Failed: {e}")

def calculate_rolling_handicap(player_df, target_week):
    try:
        excluded_weeks = [0, 4, 8, 12]
        rounds = player_df[
            (~player_df['Week'].isin(excluded_weeks)) & 
            (player_df['DNF'] == False) & 
            (player_df['Week'] < target_week)
        ].sort_values('Week', ascending=False)
        
        if len(rounds) == 0: 
            return 0.0
            
        last_scores = rounds.head(4)['Total_Score'].tolist()
        
        if len(last_scores) >= 4:
            last_scores.sort()
            hcp = round(sum(last_scores[:3]) / 3 - 36, 1)
        else:
            hcp = round(sum(last_scores) / len(last_scores) - 36, 1)
        return float(hcp)
    except: return 0.0

def save_weekly_data(week, player, pars, birdies, eagles, score_val, hcp_val, pin):
    st.cache_data.clear()
    existing_data = load_data()
    is_dnf = (score_val == "DNF")
    final_gross = 0 if is_dnf else int(score_val)
    new_entry = pd.DataFrame([{
        'Week': week, 'Player': player, 'Pars_Count': pars, 'Birdies_Count': birdies, 
        'Eagle_Count': eagles, 'Total_Score': final_gross, 'Handicap': hcp_val, 
        'Net_Score': (final_gross - hcp_val) if not is_dnf else 0, 'DNF': is_dnf, 'PIN': pin
    }])
    updated_df = pd.concat([existing_data[~((existing_data['Week'] == week) & (existing_data['Player'] == player))], new_entry], ignore_index=True)
    conn.update(data=updated_df[MASTER_COLUMNS])
    st.cache_data.clear()
    st.rerun()

# --- 3. DATA LOAD ---
df_main = load_data()
EXISTING_PLAYERS = sorted(df_main['Player'].unique().tolist()) if not df_main.empty else []

# --- 4. APP UI ---
st.markdown("<div style='text-align: center;'>", unsafe_allow_html=True)
st.image("GGGOLF-2.png", width=120) 
st.markdown("<h1>GGGolf</h1>", unsafe_allow_html=True)
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
                reg_row = p_info[p_info['Week'] == 0]
                stored_pin = str(reg_row['PIN'].iloc[0]).split('.')[0].strip() if not reg_row.empty else ""
                if user_pin.strip() == stored_pin:
                    st.session_state.update({"unlocked_player": player_select, "login_timestamp": time.time()})
                    st.rerun()
                else: st.error("❌ Incorrect PIN.")
        else:
            p_data = df_main[df_main['Player'] == player_select]
            w_s = st.selectbox("Select Week", range(1, 15))
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
                    x=alt.X('Week:O'),
                    y=alt.Y('Net_Score:Q', scale=alt.Scale(reverse=True, zero=False))
                ) + alt.Chart(played_rounds).mark_point(color='#2e7d32', size=100, filled=True).encode(x='Week:O', y='Net_Score:Q')
                st.altair_chart(chart.properties(height=300), use_container_width=True)

            st.divider()
            with st.form("score_entry", clear_on_submit=True):
                s_v = st.selectbox("Gross Score", ["DNF"] + [str(i) for i in range(25, 120)], key=f"gross_{w_s}")
                h_r = st.number_input("HCP to Apply", -10.0, 40.0, value=float(current_hcp), key=f"hcp_input_{w_s}")
                c1, c2, c3 = st.columns(3)
                p_c = c1.number_input("Pars", 0, 18, key=f"pars_{w_s}")
                b_c = c2.number_input("Birdies", 0, 18, key=f"birdies_{w_s}")
                e_c = c3.number_input("Eagles", 0, 18, key=f"eagles_{w_s}")
                if st.form_submit_button("Submit Score"):
                    reg_row = p_data[p_data['Week'] == 0]
                    pin = str(reg_row['PIN'].iloc[0]).split('.')[0].strip()
                    save_weekly_data(w_s, player_select, p_c, b_c, e_c, s_v, h_r, pin)

with tabs[1]: # Standings
    st.subheader("🏆 Standings")
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
    if st.button("🔄 Refresh Table"):
        st.cache_data.clear()
        st.rerun()

    curr_p = st.session_state.get("unlocked_player")
    if curr_p:
        with st.expander(f"Update Score for {curr_p}", expanded=True):
            c1, c2, c3 = st.columns([2, 1, 1])
            h_u = c1.selectbox("Hole", range(1, 10))
            s_u = c2.number_input("Strokes", 1, 15, 4)
            if c3.button("Post", use_container_width=True):
                update_live_score(curr_p, h_u, s_u)
                st.rerun()
    
    l_df = load_live_data(force_refresh=True)
    if not l_df.empty:
        h_cols = [str(i) for i in range(1, 10)]
        l_df['Total'] = l_df[h_cols].sum(axis=1)
        st.dataframe(l_df.sort_values("Total"), use_container_width=True, hide_index=True)

with tabs[3]: # History
    st.subheader("📅 Weekly Scores")
    h_df = df_main[df_main['Week'] > 0].copy()
    if not h_df.empty:
        st.dataframe(h_df[['Week', 'Player', 'Total_Score', 'Net_Score', 'Handicap']].sort_values(['Week', 'Net_Score'], ascending=[False, True]), use_container_width=True, hide_index=True)

with tabs[4]: # League Info
    st.header("ℹ️ League Information")
    info_category = st.radio("Select a Category:", ["About Us", "Rules", "Schedule", "Prizes", "Expenses"], horizontal=True)
    st.divider()

    if info_category == "About Us":
        st.subheader("GGGolf Summer League 2026")
        st.write("Formed in 2022, GGGOLF league promotes camaraderie through friendly golf competition and welcomes all skill levels. Members gain experience to prepare for community tournaments and events, while maintaining high standards of integrity in the game.")
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("👥 League Officers")
            st.markdown("* **President**: Txoovnom Vang\n* **Vice President**: Cory Vue\n* **Finance**: Mike Yang")
        with col2:
            st.subheader("⚖️ Committees")
            st.markdown("* **Rules Committee**: Lex Vue\n* **Players Committee**: Long Lee and Deng Kue")
        st.divider()
        st.subheader("📜 Code of Conduct")
        st.markdown("""
        * Follow golf rules and be honest in scoring.
        * Arrive promptly for matches and events.
        * Communicate clearly about schedules and issues.
        * Cooperate for a successful league.
        * Comply with all policies and guidelines.
        """)

    elif info_category == "Rules":
        st.subheader("League Game Play Format")
        st.markdown("""
        **Handicaps:** Rolling average of the best 3 of the last 4 rounds to a par 36. If you have not played 4 rounds, your avg of the rounds you have completed will be used for handicap.\n
        
        **Tee Box:** All players will play from tee box as stated below.\n  
        ***Unless you meet the criteria of C1 or C2 or have approval from the players committee to play from a forward tee box:***
        * C1: If your handicap average equals 36+ you will play from the tee box ahead of the default tee box mentioned below.
        * C2: If your handicap average equals 50+ or more, you may play from tee box ahead of C1.\n
        Brown Deer: Blue - 6306 yd\n
        Dretzka: Blue - 6538 yd\n
        Oakwood: Blue - 6737 yd\n
        Whitnall: Blue - 6308 yd\n
        Currie: Black - 6444 yd\n
        **Gimmies/Putting:** Promote competition of fair play, Putt out\n
        ***Unless one of the below scenario***\n
        * Your group is holding up the playing field and the group in fornt of you are off their tee box, pickup - within putter blade length. Example: Putting for par, finish hole with Gimme Par.
        * Your group is holding up the playing field and the group in fornt of you are off their tee box, pickup with 2 stroke from 15-19 feet about 5 full putter length. Example: Putting for par, finish hole with Gimme Bogey.
        * Your group is holding up the playing field and the group in fornt of you are off their tee box, pickup with 3 stroke from 30+ feet about 10 full putter length. Example: Putting for par, finish hole with Gimme Double Bogey.\n
        **Pace of Play Etiquette:** Keep pace of play for your league members and others outside of the league.\n  
        * 2 Minutes ball search.\n
        * If the group behind you are on the tee box, STOP searching - drop and continue play.\n
        * Help your playing partners spot and search for their ball.\n
        * Search smartly: if a playing partner is helping search for the ball, you need to move on to play your ball. Do NOT have the entire group search for one players ball.\n
        * Play ready golf.
        * Move off the greens and record score at the next tee box.
        
        **DNFs:** If you cannot finish, mark 'DNF'.
        """)

    elif info_category == "Schedule":
        st.subheader("📅 2026 Season Schedule")
        courses = ["Dretzka", "Currie", "Whitnall", "Brown Deer", "Oakwood", "Dretzka", "Currie", "Brown Deer", "Whitnall", "Oakwood", "Dretzka", "Brown Deer", "TBD"]
        league_start = pd.to_datetime("2026-05-31")
        schedule_data = []
        for i in range(1, 14):
            current_date = league_start + pd.Timedelta(weeks=i-1)
            course_name = courses[i-1] 
            if i == 4: note = "GGG Event- 2 Man Scramble Team (18 holes)"
            elif i == 8: note = "GGG Event- 4 Man Team Battle (18 holes)"
            elif i == 12: note = "GGG Event- Double Points (18 holes)"
            else: note = "Regular Round"
            schedule_data.append({"Week": f"Week {i}", "Date": current_date.strftime('%B %d, %Y'), "Course": course_name, "Note": note})
        schedule_data.append({"Week": "FINALE", "Date": "August 28, 2026", "Course": "TBD", "Note": "GGG Event- GGGolf Finale & Friends & Family Picnic 🍔"})
        df_schedule = pd.DataFrame(schedule_data)
        st.dataframe(df_schedule.style.apply(lambda r: ['background-color: #d4edda']*len(r) if "GGG Event" in str(r["Note"]) else ['']*len(r), axis=1), use_container_width=True, hide_index=True, height=530)
        st.caption("Note: Major events are highlighted in green.")

    elif info_category == "Prizes":
        st.subheader("🏆 Prize Pool")
        st.write("Prizes are based on FedEx Point standings at the end of Week 13.")

    elif info_category == "Expenses":
        st.subheader("💵 League Expenses")
        st.write("Breakdown of league fees and administrative costs.")

with tabs[5]: # Registration
    st.header("👤 Registration")
    if not st.session_state["reg_access"]:
        if st.text_input("League Key", type="password") == REGISTRATION_KEY:
            if st.button("Unlock"): st.session_state["reg_access"] = True; st.rerun()
    else:
        with st.form("r"):
            n, p = st.text_input("Name"), st.text_input("PIN", max_chars=4)
            if st.form_submit_button("Register"):
                if n and len(p) == 4:
                    try:
                        new_reg = pd.DataFrame([{"Week": 0, "Player": n, "PIN": p, "Handicap": 0.0, "DNF": True, "Pars_Count": 0, "Birdies_Count": 0, "Eagle_Count": 0, "Total_Score": 0, "Net_Score": 0}])
                        conn.update(data=pd.concat([df_main, new_reg], ignore_index=True)[MASTER_COLUMNS])
                        l_df = load_live_data(force_refresh=True)
                        if n not in l_df['Player'].values:
                            new_live = pd.DataFrame([{'Player': n, **{str(i): 0 for i in range(1, 10)}}])
                            conn.update(worksheet="LiveScores", data=pd.concat([l_df, new_live], ignore_index=True))
                        st.cache_data.clear()
                        time.sleep(1)
                        st.session_state["reg_access"] = False
                        st.success("Registration Successful!")
                        st.rerun()
                    except Exception as e: st.error(f"Registration Error: {e}")

with tabs[6]: # Admin
    if st.text_input("Admin Password", type="password") == ADMIN_PASSWORD:
        st.session_state["authenticated"] = True
        if st.button("🚨 Reset Live Board"):
            conn.update(worksheet="LiveScores", data=pd.DataFrame(columns=['Player'] + [str(i) for i in range(1, 10)]))
            st.rerun()

