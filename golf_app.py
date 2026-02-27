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
    """Loads live tracking data with zero cache to ensure absolute accuracy."""
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
    """Updates the player's row in LiveScores using the proven conn.update method."""
    try:
        # 1. Clear cache and get the latest live data
        st.cache_data.clear()
        df_live = load_live_data(force_refresh=True)
        
        if player not in df_live['Player'].values:
            st.error(f"❌ Player '{player}' not found. Please re-register.")
            return

        # 2. Modify only the specific hole for this player in our local copy
        hole_col = str(hole)
        df_live.loc[df_live['Player'] == player, hole_col] = int(strokes)
        
        # 3. Use the same logic that works in Registration to save the whole table
        # This is more reliable than cell-level updates for st.connection
        conn.update(worksheet="LiveScores", data=df_live)
        
        st.cache_data.clear()
        st.toast(f"✅ Saved {player}: Hole {hole} = {strokes}")
        time.sleep(0.5) # Short buffer for Google API
        
    except Exception as e:
        st.error(f"🚨 Update Failed: {e}")

def calculate_rolling_handicap(player_df, target_week):
    try:
        excluded_weeks = [0, 4, 8, 12]
        rounds = player_df[(~player_df['Week'].isin(excluded_weeks)) & (player_df['DNF'] == False) & (player_df['Week'] < target_week)].sort_values('Week', ascending=False)
        starting_hcp = 10.0
        reg_row = player_df[player_df['Week'] == 0]
        if not reg_row.empty: starting_hcp = float(reg_row['Handicap'].iloc[0])
        if len(rounds) == 0: return float(starting_hcp)
        last_4 = rounds.head(4)['Total_Score'].tolist()
        last_4.sort()
        hcp = round(sum(last_4[:3]) / 3 - 36, 1) if len(last_4) >= 4 else round(sum(last_4)/len(last_4)-36, 1)
        return float(hcp)
    except: return 10.0

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
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Current HCP", h_disp)
            m2.metric("Avg Net", f"{played_rounds['Net_Score'].mean():.1f}" if not played_rounds.empty else "N/A")
            m3.metric("Total Birdies", int(played_rounds['Birdies_Count'].sum()))
            m4.metric("Total Pars", int(played_rounds['Pars_Count'].sum()))

            if not played_rounds.empty:
                chart = alt.Chart(played_rounds).mark_line(color='#2e7d32', strokeWidth=3).encode(
                    x=alt.X('Week:O'),
                    y=alt.Y('Net_Score:Q', scale=alt.Scale(reverse=True, zero=False))
                ) + alt.Chart(played_rounds).mark_point(color='#2e7d32', size=100, filled=True).encode(x='Week:O', y='Net_Score:Q')
                st.altair_chart(chart.properties(height=300), use_container_width=True)

            st.divider()
            with st.form("score_entry"):
                s_v = st.selectbox("Gross Score", ["DNF"] + [str(i) for i in range(25, 120)], key=f"gross_{w_s}")
                h_r = st.number_input("HCP to Apply", -10.0, 40.0, value=float(current_hcp))
                c1, c2, c3 = st.columns(3)
                p_c = c1.number_input("Pars", 0, 18)
                b_c = c2.number_input("Birdies", 0, 18)
                e_c = c3.number_input("Eagles", 0, 18)
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
    
    # Category Selection
    info_category = st.radio(
        "Select a Category:",
        ["General Info", "Rules", "Schedule", "Prizes", "Expenses"],
        horizontal=True
    )
    
    st.divider()

    if info_category == "General Info":
        st.subheader("GGGolf Summer League 2026")
        st.write("This league promotes camaraderie through friendly golf competition and welcomes all skill levels. Members gain experience to prepare for community tournaments and events, while maintaining high standards of integrity in the game.")
        st.divider() # Adds a clean visual line
        
        # League Officers and Committees
        st.subheader("**League Officers and Committees**")
        st.markdown("""
        **President**: Txoovnom Vang
        **Vice President**: Cory Vue
        **Finance**: Mike Yang
        **Rules Comittee**: Lex Vue
        **Players Committee:** Long Lee and Deng Kue
        """)
        
        # Code of Conduct
        st.divider() # Adds a clean visual linest
        st.subheader("**Code of Conduct**")
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
        * **Handicaps:** Rolling average of the best 3 of the last 4 rounds to a par 36.
        * **Gimmies:** Inside the leather (standard putter length).
        * **DNFs:** If you cannot finish, mark 'DNF'.
        """)

    elif info_category == "Schedule":
        st.subheader("📅 2026 Season Schedule")
        
        # 1. Define the course list (13 weeks total)
        courses = [
            "Dretzka", "Currie", "Whitnall", "Brown Deer", "Oakwood", 
            "Dretzka", "Currie", "Brown Deer", "Whitnall", "Oakwood", 
            "Dretzka", "Brown Deer", "TBD"
        ]

        # 2. Build the schedule table
        league_start = pd.to_datetime("2026-05-31")
        schedule_data = []
        
        for i in range(1, 14): # i goes from 1 to 13
            current_date = league_start + pd.Timedelta(weeks=i-1)
            
            # i-1 matches the week number to the 0-indexed course list
            course_name = courses[i-1] 

            # Start
            # Custom Notes for specific weeks
            if i == 4:
                note = "GGG Event- 2 Man Scramble Team (18 holes)"
            elif i == 8:
                note = "GGG Event- 4 Man Team Battle (18 holes)"
            elif i == 12:
                note = "GGG Event- Double Points (18 holes)"
            elif i in [4, 8, 12]: # Catch-all for other event formatting if needed
                note = "GGG Event"
            else:
                note = "Regular Round"
                
            schedule_data.append({
                "Week": f"Week {i}",
                "Date": current_date.strftime('%B %d, %Y'),
                "Course": course_name,
                "Note": note
            })


            # End
            # schedule_data.append({
                # "Week": f"Week {i}",
                # "Date": current_date.strftime('%B %d, %Y'),
                # "Course": course_name,
                # "Note": "Regular Round" if i not in [4, 8, 12] else "GGG Event"
            # })
        
        # 3. Add the Finale Row (Manually appended at the end)
        schedule_data.append({
            "Week": "FINALE",
            "Date": "August 28, 2026",
            "Course": "TBD",
            "Note": "GGGolf Finale & Friends & Family Picnic 🍔"
        })

        df_schedule = pd.DataFrame(schedule_data)

        # 3. Apply Highlighting Logic
        def highlight_events(row):
            # If the Note contains "GGG Event", color the whole row light green
            if "GGG Event" in str(row["Note"]):
                return ['background-color: #d4edda'] * len(row) # Hex code for light green
            return [''] * len(row)

        #styled_df = df_schedule.style.apply(highlight_events, axis=1)

        # Display as a styled dataframe (use_container_width makes it look like a table)
        #st.dataframe(styled_df, use_container_width=True, hide_index=True)

    # Apply styling and set a fixed height to prevent scrolling
        # 550 pixels is usually enough to show 14 rows without a scrollbar
        st.dataframe(
            df_schedule.style.apply(highlight_events, axis=1),
            use_container_width=True,
            hide_index=True,
            height=530 
        )
        
        st.caption("Note: Major events are highlighted in green.")


        
         # st.table(pd.DataFrame(schedule_data))
        
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
            n, p, h = st.text_input("Name"), st.text_input("PIN", max_chars=4), st.number_input("HCP", -10.0, 40.0, 10.0)
            if st.form_submit_button("Register"):
                if n and len(p) == 4:
                    try:
                        # 1. Update League Sheet
                        new_reg = pd.DataFrame([{"Week": 0, "Player": n, "PIN": p, "Handicap": h, "DNF": True, "Pars_Count": 0, "Birdies_Count": 0, "Eagle_Count": 0, "Total_Score": 0, "Net_Score": 0}])
                        conn.update(data=pd.concat([df_main, new_reg], ignore_index=True)[MASTER_COLUMNS])
                        
                        # 2. SEED LIVE SCORE: Create the row immediately
                        l_df = load_live_data(force_refresh=True)
                        if n not in l_df['Player'].values:
                            new_live = pd.DataFrame([{'Player': n, **{str(i): 0 for i in range(1, 10)}}])
                            conn.update(worksheet="LiveScores", data=pd.concat([l_df, new_live], ignore_index=True))
                        
                        st.cache_data.clear()
                        time.sleep(1)
                        st.session_state["reg_access"] = False
                        st.success("Registration Successful!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Registration Error: {e}")

with tabs[6]: # Admin
    if st.text_input("Admin Password", type="password") == ADMIN_PASSWORD:
        st.session_state["authenticated"] = True
        if st.button("🚨 Reset Live Board"):
            conn.update(worksheet="LiveScores", data=pd.DataFrame(columns=['Player'] + [str(i) for i in range(1, 10)]))
            st.rerun()

























