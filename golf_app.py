###################################################DDDDDDDDDDDDDDDDDDDDDDDDDDEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV##################################################################
import streamlit as st
import pandas as pd
import time
import random
import altair as alt
from PIL import Image 

# --- 1. CONFIGURATION & SESSION STATE ---
st.set_page_config(page_title="QA ENVIRONMENT GGGolf ", layout="wide")

ADMIN_PASSWORD = "!@#Seahawks6145!@#"
REGISTRATION_KEY = "2026!@#"
SESSION_TIMEOUT = 2 * 60 * 60  # Updated: 2 hours in seconds

if "api_cooling_until" not in st.session_state: st.session_state["api_cooling_until"] = 0
if "unlocked_player" not in st.session_state: st.session_state["unlocked_player"] = None
if "authenticated" not in st.session_state: st.session_state["authenticated"] = False
if "login_timestamp" not in st.session_state: st.session_state["login_timestamp"] = 0
if "reg_access" not in st.session_state: st.session_state["reg_access"] = False

from st_supabase_connection import SupabaseConnection
conn = st.connection("supabase", type=SupabaseConnection)

MASTER_COLUMNS = [
    'Week', 'Player', 'PIN', 'Pars_Count', 'Birdies_Count', 
    'Eagle_Count', 'Total_Score', 'Handicap', 'Net_Score', 'DNF', 'Acknowledged'
]

GGG_POINTS = {
    1: 100, 2: 77, 3: 64, 4: 54, 5: 47, 6: 41,
    7: 36, 8: 31, 9: 27, 10: 24, 11: 21, 12: 16, 13: 13, 14: 9,
    15: 5, 16: 3, 17: 1 
}

# --- 2. CORE FUNCTIONS ---

def load_data():
    try:
        # Correct Supabase syntax to read all data from the table
        response = conn.table("league_scores_2026").select("*").execute()
        
        # Convert the Supabase response to a Pandas DataFrame
        data = pd.DataFrame(response.data)
        
        if data.empty or 'Player' not in data.columns: 
            return pd.DataFrame(columns=MASTER_COLUMNS)
        
        df = data.dropna(how='all')
        # Filter out specific players
        df = df[df['Player'].str.lower() != 'john']
        
        return df[df['Player'] != ""]
        
    except Exception as e:
        st.warning(f"Database error: {e}")
        return pd.DataFrame(columns=MASTER_COLUMNS)

def calculate_rolling_handicap(player_df, target_week):
    try:
        if target_week in [4, 8, 12]:
            return 0.0

        if 'Total_Score' in player_df.columns:
            player_df = player_df.copy()
            player_df['Total_Score'] = pd.to_numeric(player_df['Total_Score'], errors='coerce')

        excluded_weeks = [4, 8, 12]
        
        eligible_rounds = player_df[
            (~player_df['Week'].isin(excluded_weeks)) &
            (player_df['DNF'] == False) &
            (player_df['Week'] < target_week) &
            (player_df['Total_Score'].notna()) &
            (player_df['Total_Score'] > 0)
        ].sort_values('Week', ascending=False)

        if len(eligible_rounds) < 3:
            return 0.0

        last_scores = eligible_rounds.head(4)['Total_Score'].tolist()
        last_scores.sort() 
        hcp = round((sum(last_scores[:3]) / 3) - 36, 1)

        return float(hcp)

    except Exception:
        return 0.0

def save_weekly_data(week, player, pars, birdies, eagles, score_val, hcp_val, pin):
    try:
        is_dnf = (score_val == "DNF")
        final_gross = 0 if is_dnf else int(score_val)
        
        new_entry = {
            'Week': int(week),
            'Player': player,
            'Pars_Count': int(pars),
            'Birdies_Count': int(birdies),
            'Eagle_Count': int(eagles),
            'Total_Score': int(final_gross),
            'Handicap': float(hcp_val),
            'Net_Score': float(final_gross - hcp_val) if not is_dnf else 0.0,
            'DNF': is_dnf,
            'PIN': str(pin)
        }
        
        conn.table("league_scores_2026").upsert(new_entry).execute()
        st.cache_data.clear()
        
        st.success(f"👍 Score Submitted Successfully for {player}!", icon="✅")
        time.sleep(1) 
        st.rerun()
            
    except Exception as e:
        st.error(f"❌ An error occurred: {e}")

def render_live_scoring():
    st.subheader("⛳ Live Scoring")
    
    # --- 1. SECURITY CHECK ---
    # Ensure the user is logged in via your PIN system
    if not st.session_state.get("signed_in"):
        st.warning("🔒 Please sign in with your PIN to enter scores.")
        # We still show the scorecard below so they can see the board
    else:
        # Lock the scoring to the authenticated user
        logged_in_user = st.session_state.get("username")
        st.success(f"Logged in as: **{logged_in_user}**")

        # --- 2. INPUT SECTION (Locked to Logged-in User) ---
        with st.expander(f"📝 Enter Score for {logged_in_user}", expanded=True):
            if 'active_hole' not in st.session_state:
                st.session_state.active_hole = 1

            st.write(f"**Select Hole: {st.session_state.active_hole}**")
            
            # Hole Selection Grid
            f9_cols = st.columns(9)
            for i in range(1, 10):
                if f9_cols[i-1].button(f"{i}", key=f"f9_{i}", 
                                       type="primary" if st.session_state.active_hole == i else "secondary",
                                       use_container_width=True):
                    st.session_state.active_hole = i
                    st.rerun()

            b9_cols = st.columns(9)
            for i in range(10, 19):
                if b9_cols[i-10].button(f"{i}", key=f"b9_{i}", 
                                        type="primary" if st.session_state.active_hole == i else "secondary",
                                        use_container_width=True):
                    st.session_state.active_hole = i
                    st.rerun()

            with st.form("live_score_form", clear_on_submit=True):
                score = st.selectbox("Score", options=range(1, 11), index=3) # Defaults to 4
                
                if st.form_submit_button("Submit Score", type="primary", use_container_width=True):
                    try:
                        new_score = {
                            "week": 1, 
                            "player_name": logged_in_user, # Hardcoded to the user
                            "hole_number": st.session_state.active_hole,
                            "score": score,
                            "updated_at": "now()"
                        }
                        conn.table("live_scores").upsert(new_score, on_conflict="week,player_name,hole_number").execute()
                        st.success(f"Score of {score} saved for Hole {st.session_state.active_hole}!")
                        
                        # Auto-advance
                        if st.session_state.active_hole < 18:
                            st.session_state.active_hole += 1
                        
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Save Failed: {e}")

    # --- 3. PUBLIC VIEW SECTION ---
    # This remains outside the 'if signed_in' block so everyone can see it
    st.divider()
    st.subheader("📊 League Scorecard")
    
    if st.button("🔄 Refresh Scorecard"):
        st.rerun()
    
    try:
        response = conn.table("live_scores").select("*").eq("week", 1).execute()
        df = pd.DataFrame(response.data)
        
        if not df.empty:
            scorecard = df.pivot(index="player_name", columns="hole_number", values="score")
            for i in range(1, 19):
                if i not in scorecard.columns: scorecard[i] = None
            
            scorecard = scorecard.apply(pd.to_numeric, errors='coerce').fillna(0).astype(int)
            scorecard["Front 9"] = scorecard[range(1, 10)].sum(axis=1)
            scorecard["Back 9"] = scorecard[range(10, 19)].sum(axis=1)
            scorecard["Total"] = scorecard["Front 9"] + scorecard["Back 9"]
            
            cols_order = list(range(1, 10)) + ["Front 9"] + list(range(10, 19)) + ["Back 9", "Total"]
            display_df = scorecard[cols_order].replace(0, '-')
            
            st.dataframe(display_df, use_container_width=True)
        else:
            st.info("No scores recorded yet.")
    except Exception as e:
        st.warning("Scorecard is currently unavailable.")
        

# --- 3. DATA LOAD ---
df_main = load_data()
EXISTING_PLAYERS = sorted(df_main['Player'].unique().tolist()) if not df_main.empty else []

# --- 4. APP UI ---
st.markdown("<div style='text-align: center;'>", unsafe_allow_html=True)
st.image("GGGOLF-2.png", width=120) 
st.markdown("<h1>QA ENVIRONMENT GGGolf</h1>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

tabs = st.tabs(["📝 Scorecard", "🏆 Standings", "📅 History", "⛳ Live Scoring", "🏁 GGG Challenge", "ℹ️ League Info", "👤 Registration", "⚙️ Admin"])

with tabs[0]: # Scorecard
    if not EXISTING_PLAYERS: 
        st.warning("No players registered yet.")
    else:
        player_select = st.segmented_control(
            "Select Your Profile", 
                options=EXISTING_PLAYERS,
                selection_mode="single",
                key="player_segment_select"
            )
        
        is_unlocked = (st.session_state.get("unlocked_player") == player_select and 
                      (time.time() - st.session_state.get("login_timestamp", 0)) < SESSION_TIMEOUT) or \
                      st.session_state.get("authenticated", False)
        
        if not is_unlocked:
            st.markdown("### 🔒 Player Verification")
            st.info(f"Please enter your 4-digit PIN to unlock the scorecard for **{player_select}**.")

            with st.form("unlock_form"):
                user_pin = st.text_input("Enter PIN", type="password", key=f"pin_input_{player_select}")
                submit_unlock = st.form_submit_button("🔓 Unlock Scorecard", use_container_width=True, type="primary")
                
                if submit_unlock:
                    if user_pin:
                        p_info = df_main[df_main['Player'] == player_select]
                        reg_row = p_info[p_info['Week'] == 0]
                        
                        if not reg_row.empty:
                            stored_pin = str(reg_row['PIN'].iloc[0]).split('.')[0].strip()
                            if user_pin.strip() == stored_pin:
                                st.session_state.update({
                                    "unlocked_player": player_select, 
                                    "login_timestamp": time.time()
                                })
                                st.success("Identity Verified!")
                                time.sleep(0.5)
                                st.rerun()
                            else:
                                st.error("❌ Incorrect PIN.")
                        else:
                            st.error("⚠️ Player not found in registration records.")
                    else:
                        st.warning("Please enter your PIN.")
        
        else:
            p_data = df_main[df_main['Player'] == player_select]
                       
            st.markdown("### 📅 Select Week")

            week_categories = {
                "Pre-Season": [-2, -1, 0],
                "Phase 1": [1, 2, 3, 4],
                "Phase 2": [5, 6, 7, 8],
                "Phase 3": [9, 10, 11, 12],
                "Finals": [13, 14]
            }

            w_s = st.segmented_control(
                "Choose Week",
                options=[-2, -1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14],
                format_func=lambda x: f"P{abs(x-1)}" if x <= 0 else f"W{x}",
                selection_mode="single",
                default=1,
                key=f"week_tabs_{player_select}"
            )

            if w_s is None:
                w_s = 1

            if w_s <= 0:
                st.caption(f"📍 Currently Entering: **Pre-Season Round {abs(w_s-1)}**")
            elif w_s in [4, 8, 12]:
                st.caption(f"📍 Currently Entering: **Week {w_s} (Event Week)**")
            else:
                st.caption(f"📍 Currently Entering: **Week {w_s}**")

            if w_s <= 0:
                current_hcp = 0.0
                st.info("🛠️ Pre-Season: Logging rounds to establish your Week 1 handicap.")
            elif w_s in [4, 8, 12]:
                current_hcp = 0.0
                st.info("💡 GGG Event: No handicap applied for this round.")
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
                    x=alt.X('Week:O'),
                    y=alt.Y('Net_Score:Q', scale=alt.Scale(reverse=True, zero=False))
                ) + alt.Chart(played_rounds).mark_point(color='#2e7d32', size=100, filled=True).encode(x='Week:O', y='Net_Score:Q')
                st.altair_chart(chart.properties(height=250), use_container_width=True)

            st.divider()

            with st.form("score_entry", clear_on_submit=True):
                st.subheader("Submit Weekly Round")
                s_v = st.selectbox("Gross Score", ["DNF"] + [str(i) for i in range(25, 120)], key=f"gross_{player_select}_{w_s}")
                h_r = st.number_input("HCP to Apply", value=float(current_hcp), key=f"hcp_{player_select}_{w_s}")
                
                c1, c2, c3 = st.columns(3)
                p_c = c1.number_input("Pars", 0, 18, key=f"p_{player_select}_{w_s}")
                b_c = c2.number_input("Birdies", 0, 18, key=f"b_{player_select}_{w_s}")
                e_c = c3.number_input("Eagles", 0, 18, key=f"e_{player_select}_{w_s}")
                
                if st.form_submit_button("Confirm & Submit Score", use_container_width=True, type="primary"):
                    reg_row = p_data[p_data['Week'] == 0]
                    pin = str(reg_row['PIN'].iloc[0]).split('.')[0].strip()
                    save_weekly_data(w_s, player_select, p_c, b_c, e_c, s_v, h_r, pin)
                    st.success("Score Saved!")
                    time.sleep(1)
                    st.rerun()

with tabs[1]: # Standings
    st.subheader("🏆 Standings")
    if not df_main.empty:
        v = df_main[(df_main['Week'] > 0) & (df_main['DNF'] == False)].copy()
        if not v.empty:
            v['Pts'] = 0.0
            for w in v['Week'].unique():
                m = v['Week'] == w
                v.loc[m, 'R'] = v.loc[m, 'Net_Score'].rank(method='min')
                for idx, row in v[m].iterrows():
                    base_pts = GGG_POINTS.get(int(row['R']), 10.0)
                    final_pts = base_pts * 2 if w == 12 else base_pts
                    v.at[idx, 'Pts'] = final_pts                    
            res = v.groupby('Player').agg({'Pts':'sum', 'Net_Score':'mean'}).reset_index().rename(columns={'Pts':'Total Pts', 'Net_Score':'Avg Net'})
            res['Avg Net'] = res['Avg Net'].round(1)
            st.dataframe(res.sort_values(['Total Pts', 'Avg Net'], ascending=[False, True]), use_container_width=True, hide_index=True)


with tabs[2]: # History
    st.subheader("📅 Weekly Scores & GGG Points")
    h_df = df_main[(df_main['Week'] > 0) & (df_main['DNF'] == False)].copy()
    if not h_df.empty:
        h_df['Points'] = 0.0
        for w in h_df['Week'].unique():
            mask = h_df['Week'] == w
            h_df.loc[mask, 'Rank'] = h_df.loc[mask, 'Net_Score'].rank(method='min')
            for idx, row in h_df[mask].iterrows():
                base_pts = GGG_POINTS.get(int(row['Rank']), 10.0)
                h_df.at[idx, 'Points'] = base_pts * 2 if w == 12 else base_pts
                        
        f_col1, f_col2 = st.columns(2)
        all_players = ["All Players"] + sorted(h_df['Player'].unique().tolist())
        sel_player = f_col1.selectbox("Filter by Player", all_players)
        all_weeks = ["All Weeks"] + sorted(h_df['Week'].unique().tolist())
        sel_week = f_col2.selectbox("Filter by Week", all_weeks)
        
        filtered_df = h_df.copy()
        if sel_player != "All Players":
            filtered_df = filtered_df[filtered_df['Player'] == sel_player]
        if sel_week != "All Weeks":
            filtered_df = filtered_df[filtered_df['Week'] == sel_week]
            
        display_df = filtered_df[['Week', 'Player', 'Total_Score', 'Handicap', 'Net_Score', 'Points']].copy()
        display_df = display_df.sort_values(['Week', 'Points'], ascending=[False, False])
        
        st.dataframe(
            display_df, 
            use_container_width=True, 
            hide_index=True,
            column_config={
                "Points": st.column_config.NumberColumn("GGG Points", format="%d pts"),
                "Week": st.column_config.NumberColumn("Week", format="Wk %d")
            }
        )
    else:
        st.info("No completed rounds recorded yet.")

with tabs[3]:  # Live Scoring
    # You MUST call the function here to make the content appear
    render_live_scoring()

with tabs[4]:  # GGG Challenge
    st.header("🏁 GGG Challenge")
    st.write("Seasonal challenges and reward opportunities for GGGolf members.")
    st.divider()

    challenge_options = ["Season Ball Challenge", "Gold Card", "Most Pars", "Most Birdies", "Most Eagles"]
    challenge_selection = st.radio("Select Challenge:", challenge_options, horizontal=True)

    st.info("Challenges will be announced here during the season. Each challenge includes a short description, cost (if any), eligibility rules, and how to participate.")

    col_main, col_side = st.columns([3, 1])

    with col_main:
        if challenge_selection == "Season Ball Challenge":
            st.subheader("Current Challenge: Season Ball")
            st.markdown("**Entry:** $20 for a GGG sleeve of balls")
            st.markdown("**Overview:** Use the GGG sleeve during league play. Return at least one ball from the sleeve at the season finale to qualify for the top prize.")
            st.divider()
            st.markdown("**How it works**")
            st.markdown(
                "1. Purchase a GGG sleeve for $20 to join the challenge.\n"
                "2. Use the GGG balls during regular league and event play.\n"
                "3. At the start of each round your sleeve will be given to you.\n"
                "4. At the end of each round the sleeve must be returned with the remaining balls to one of the League Officials.\n"
                "5. At the start of the next round/week your sleeve will be redistributed from the previous week for you to continue the challenge.\n"
                "5. When you have lost all balls from the sleeve, you may REBUY (see timeline below).\n"
                "6. At the season finale, return at least one ball from your sleeve to qualify for prize tier of the returning sleeve.\n\n"
                "**Note:** On GGG events you must play your ball. In 2 man Greensomes, you must play your ball when its your shot on the alternate. This is the same for the 4-Man Scramble. Since you are able to play your own ball in these events."
            )
            st.divider()
            st.markdown("**Eligibility and Rebuy Options**")
            import pandas as _pd
            elig = _pd.DataFrame([
                {"Option": "Original Purchase", "Entry Deadline": "Before Week 1 April thru May 31", "Prize Eligibility": "1st pick EoS prize or $100"},
                {"Option": "REBUY 1", "Entry Deadline": "Before Week 3 - June 1 thru June 14", "Prize Eligibility": "2nd pick EoS prize or $50"},
                {"Option": "REBUY 2", "Entry Deadline": "Before Week 7 - June 15 thru July 12", "Prize Eligibility": "4th pick EoS prize or $20"},
                {"Option": "REBUY 3", "Entry Deadline": "Before Week 11 - July 13 thru Aug 9", "Prize Eligibility": "6th pick EoS prize"}
            ])
            st.table(elig)
            st.divider()
            with st.expander("Full Rules and Examples", expanded=False):
                st.markdown(
                    "**Key Rules**\n\n"
                    "- Purchasing the sleeve registers you for the challenge under the corresponding entry deadline.\n"
                    "- If you purchase a REBUY, you are only eligible for the prize tier associated with that REBUY (you forfeit eligibility for earlier tiers).\n"
                    "- Balls lost during play may be rebought using the REBUY options above; each REBUY has its own deadline.\n"
                    "- To claim a prize at the finale you must return at least one ball from the sleeve you purchased.\n\n"
                    "**Examples**\n\n"
                    "- If your initial buy is before Week 1 and return a ball after the finale at the picnic, you qualify for the top prize or $100 cash.\n"
                    "- If your initial buy is Week 2, you are not eligible for the top prize but can claim the REBUY 1 tier prize (2nd pick or $50).\n"
                    "- If you BUY at Week 1 and lose all your ball by Week 4, you decide to REBUY week 6, your prize tier will be REBUY 2\n"
                    "- If you BUY at Week 1 and lose all your ball by Week 8, you decide to REBUY week 10, your prize tier will be REBUY 3"
                )

        elif challenge_selection == "Gold Card":
            st.subheader("Current Challenge: Gold Card")
            st.markdown("**Entry:** Enter into the **Season Ball Challenge** before Week 1 to be eligible.")
            st.markdown("**Overview:** Use your Gold Card to play from the front tees. Finish the round in first place overall net score without handicap that week. If you do not come in first, you will donate $100 to the league or equvilent to 2 ducks for the picnic.\n\n"
                        "***NOTE:*** GOLD Card is **NOT** accepted at Currie Golf course or at any GGG events!")
            st.divider()
            st.markdown("**How it works**")
            st.markdown("1. Enter into the Ball Challenge.\n"
                        "2. Receive gold card.\n"
                        "3. Turn in gold card before teeing off.\n"
                        "4. Play from the front tee.\n"
                        "5. Win first or donate.")
            st.divider()
            with st.expander("Full Rules and Examples", expanded=False):
                st.markdown(
                    "**Key Rules**\n\n"
                    "- Play from the front tee.\n"
                    "- Multiple players can turn in their GOLD card on the same week.\n"
                    "- No handicap.\n"
                    "- Place First overall for the week.\n"
                    "- Any ties that occur, will continue on until one winner is decided in playoff rules. Win the hole or lose, ties keep moving onto the next hole until winner is decided.\n"
                    "- In the event of tie through 18 holes, Chip & Putt will decide.\n\n"
                    "**Examples**\n\n"
                    "- Dale plays from froward tee in this case the Gold at Dretzka. Dale come in first, Dale receives 100 points.\n"
                    "- Dale plays from froward tee in this case the Gold at Dretzka. Dale come in second, Dale pay ducks or $100 to the league as a donation fund for league expenses.\n"
                )

        elif challenge_selection in ["Most Pars", "Most Birdies", "Most Eagles"]:
            st.subheader(f"Current Challenge: {challenge_selection}")
            st.markdown(f"**Entry Fee:** $20")
            with st.expander("Rules, Fees, and Payout Structure", expanded=True):
                st.markdown(f"""
                **Rules for {challenge_selection}:**
                - This is a season-long cumulative total challenge.
                - Registration fee is **$20**.
                - **35%** ($7.00) of entry fees go directly to the GGGolf league fund for expenses.
                - **65%** ($13.00) of the entry fees form the payout pool.
                - Payouts TBD (based on final entries percentage will be calculated).
                """)

        st.markdown("### Registered Players")
        
        participants = []
        try:
            # SUPABASE READ
            response = conn.table("ChallengeRegistrations").select("*").execute()
            reg_df = pd.DataFrame(response.data) if response.data else pd.DataFrame(columns=["ChallengeName", "PlayerName"])
            
            if not reg_df.empty and 'ChallengeName' in reg_df.columns:
                participants = reg_df[reg_df['ChallengeName'] == challenge_selection]['PlayerName'].unique().tolist()
            
            if participants:
                for p in participants:
                    st.text(f"✅ {p}")
            else:
                st.write("No players registered yet.")
        except Exception as e:
            st.warning(f"Could not load registration list. Ensure 'ChallengeRegistrations' table exists. Error: {e}")

        if st.button(f"Join {challenge_selection}", key=f"join_{challenge_selection}"):
            player_name = st.session_state.get("unlocked_player")
            
            if not player_name:
                st.error("Please log in to register.")
            elif player_name in participants:
                st.info("You are already registered for this challenge.")
            else:
                new_reg = {
                    "PlayerName": player_name,
                    "ChallengeName": challenge_selection,
                    "RegistrationDate": pd.Timestamp.now().strftime("%Y-%m-%d")
                }
                
                try:
                    # SUPABASE INSERT
                    conn.table("ChallengeRegistrations").insert(new_reg).execute()
                    st.success(f"Successfully joined {challenge_selection}!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Registration failed: {e}")

    with col_side:
        st.subheader("Quick Actions")
        st.write("Admin controls will appear here when implemented.")
        st.button("Request Challenge Edit Access", disabled=True, key="req_edit_access")
        st.divider()
        st.markdown("**Notes for Players**")
        st.markdown(
            "- Keep your sleeve balls separate so returned balls can be verified.\n"
            "- Questions about eligibility should be directed to the Rules and Players Committee."
        )
        
with tabs[5]: # League Info
    st.header("ℹ️ League Information")
    info_category = st.radio("Select a Category:", ["About Us", "Handicaps", "Rules", "Schedule", "Prizes", "Expenses", "Members", "Bets"], horizontal=True)
    st.divider()

    if info_category == "About Us":
        st.subheader("GGGolf Summer League 2026")
        st.write("Formed in 2022, GGGOLF league promotes camaraderie through friendly golf competition and welcomes all skill levels. Members gain experience to prepare for community tournaments and events, while maintaining high standards of integrity in the game.")
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("League Officers")
            st.markdown("* **President**: Txoovnom Vang\n* **Vice President**: Cory Vue\n* **Finance**: Mike Yang")
            st.markdown("""
            **Executive Team:** The Officers hold primary responsibility for the league’s operational backbone. 
            Their focus is on **growth, financial oversight, and external promotion.** They ensure the league’s sustainability by managing the essential logistics that allow GGGolf to function as a professional-grade organization.
            """)
        with col2:
            st.subheader("Committees")
            st.markdown("* **Rules and Players Committee**: Lex Vue, Long Lee, Deng Kue\n")
            st.markdown("""
            **Player Advocacy:** This Committee serves as the formal link between the membership and leadership. They are tasked with **maintaining competitive integrity, hearing member grievances, and vetting player-driven initiatives.** Their role ensures that the evolution of the league is always informed by the needs of the players.
            """)
        
        st.divider()
        with st.expander("GGGolf Organizational Protocol", expanded=False):
            st.markdown("""
            To ensure the effective administration of GGGolf, we operate under a dual-branch governance model:
            
            1. **Administrative Authority:** All final decisions regarding league expansion, financial allocations, and external partnerships reside with the **League Officers**.
            2. **Consultative Feedback:** Players seeking to implement change or address concerns must follow the established chain of command by bringing matters to the **Players Committee**. The Committee evaluates these proposals before presenting them to the Officers for executive review.
            
            This professional hierarchy is established to protect the integrity of the league and ensure that the voice of the player is represented within a disciplined administrative framework.
            """)
        st.divider()
        st.subheader("Code of Conduct")
        st.markdown("""
        * Practice common golfing etiquette and rules.
        * Integrity: Respect yourself, fellow league members, and others outside the league on the golf course.
        * Arrive promptly and timely.
        * Communicate clearly about schedules and issues.
        * Comply with all policies and guidelines.
        * Follow the structural chain
        """)

    elif info_category == "Handicaps":
        st.subheader("Establishing Your Handicap")
        st.info("""
        **Pre-Season Requirement:**
        To have an accurate handicap for Week 1, players are encouraged to log 3 Pre-Season rounds. Play with one or more 2026 GGG member and play from the Tee Box you feel is fair per your skill level.
        You may play at any course on the 2026 GGG Schedule, once you've logged a pre-season round it will be locked in for calculation for Week 1.
        
        * **Option A:** Complete 3 rounds before May 31. Your Week 1 handicap will be the average of these three pre-season scores.
        * **Option B:** If you do not complete the 3 pre-season rounds, you will start Week 1 with a 0.0 handicap until you have reach 3 completed rounds for a hanidcap (Includes the pre-season round you have completed).
        """)

        st.divider()
        st.subheader("Handicap Calculation Transparency")
        st.write(
            "Use the tool below to inspect how a player's handicap is derived. "
            "This shows pre-season rounds, the last eligible rounds used, and the exact math (best 3 of last 4 to par 36)."
        )

        if 'df_main' not in globals() or df_main is None or df_main.empty:
            st.warning("No player data available to show handicap breakdown.")
        else:
            try:
                reg_players = df_main[df_main['Week'] == 0]['Player'].dropna().unique().tolist()
                all_players = sorted(df_main['Player'].dropna().unique().tolist())
                player_options = reg_players if reg_players else all_players
            except Exception:
                player_options = sorted(df_main['Player'].dropna().unique().tolist())

            if not player_options:
                st.info("No registered players found.")
            else:
                sel_player = st.selectbox("Select Player to Inspect", player_options, key="handicap_transparency_player")
                sel_week = st.selectbox("Target Week (handicap to apply for)", list(range(1, 15)), index=0, key="handicap_transparency_week")

                p_df = df_main[df_main['Player'] == sel_player].copy()
                if p_df.empty:
                    st.warning("No recorded rounds for this player.")
                else:
                    pre_season = p_df[(p_df['Week'] <= 0) & (p_df['DNF'] == False) & (p_df['Total_Score'] > 0)].sort_values('Week', ascending=False)
                    excluded_weeks = [0, 4, 8]
                    regular_rounds = p_df[
                        (p_df['Week'] > 0) &
                        (~p_df['Week'].isin(excluded_weeks)) &
                        (p_df['DNF'] == False) &
                        (p_df['Week'] < sel_week)
                    ].sort_values('Week', ascending=False)

                    with st.expander("View Rounds Used In Calculation", expanded=True):
                        st.markdown("**Pre-Season Rounds (Week <= 0)**")
                        if pre_season.empty:
                            st.write("No pre-season rounds recorded.")
                        else:
                            st.dataframe(pre_season[['Week', 'Total_Score', 'DNF']].reset_index(drop=True), use_container_width=True, hide_index=True)

                        st.markdown("**Eligible Regular Rounds (excluding Weeks 0, 4, 8)**")
                        if regular_rounds.empty:
                            st.write("No eligible regular rounds recorded prior to the selected target week.")
                        else:
                            st.dataframe(regular_rounds[['Week', 'Total_Score', 'DNF']].reset_index(drop=True), use_container_width=True, hide_index=True)

                    try:
                        all_eligible = pd.concat([pre_season, regular_rounds]).drop_duplicates().sort_values('Week', ascending=False)
                        
                        if len(all_eligible) < 3:
                            used_scores = []
                            avg_score = None
                            hcp_val = 0.0
                            method = f"Insufficient rounds ({len(all_eligible)}/3 completed). A minimum of 3 rounds is required to establish a handicap. Defaulting to 0.0."
                        else:
                            last_scores = all_eligible.head(4)['Total_Score'].tolist()
                            sorted_scores = sorted(last_scores)
                            used_scores = sorted_scores[:3]  
                            avg_score = sum(used_scores) / 3
                            hcp_val = round(avg_score - 36, 1)
                            method = f"Best 3 of last 4 eligible rounds ({len(last_scores)} available rounds evaluated)"

                        st.divider()
                        st.markdown("### Handicap Breakdown Result")
                        st.write(f"**Player:** {sel_player}")
                        st.write(f"**Target Week:** {sel_week}")
                        st.write(f"**Method:** {method}")
                        if avg_score is not None:
                            st.write(f"**Used Scores:** {used_scores}")
                            st.write(f"**Average Gross (used):** {avg_score:.2f}")
                            st.write(f"**Calculated Handicap:** **{hcp_val}** (computed as average gross − 36)")
                        else:
                            st.write("No scores available to compute an average. Handicap set to **0.0** by default.")

                        with st.expander("Detailed Rounds Table (marking used rounds)"):
                            combined = pd.concat([pre_season, regular_rounds]).drop_duplicates().sort_values('Week', ascending=False)
                            if combined.empty:
                                st.write("No rounds to display.")
                            else:
                                combined_display = combined[['Week', 'Total_Score', 'DNF']].reset_index(drop=True).copy()
                                def mark_used(row):
                                    try:
                                        return row['Total_Score'] in used_scores
                                    except Exception:
                                        return False
                                combined_display['UsedInCalc'] = combined_display.apply(mark_used, axis=1)
                                st.dataframe(combined_display, use_container_width=True, hide_index=True)

                        st.markdown(
                            "If you believe a round was incorrectly included or excluded, please contact the Rules and Players Committee. "
                            "Rounds from special event weeks (e.g., scrambles or team events) are excluded from handicap calculations by league policy."
                        )
                    except Exception as e:
                        st.error(f"Error computing handicap breakdown: {e}")

    elif info_category == "Rules":
        st.subheader("League Rules and Format")
        st.markdown("""
        **Handicaps:** Rolling average of the best 3 of the last 4 rounds to a par 36. If you have not played 4 rounds, your avg of the rounds you have completed will be used for handicap.\n\n

        **Scoring:** Use the GGGolf app AND hand in one of the group's (your playing partners) physical score card. ***Failure to do so can result in a DNF round and not receive GGG points.***
        * Individual Players are RESPONSIBLE to input and/or update their weekly rounds GROSS score into the GGG App.
        * The Net score will be automatically applied using the handicap.
        * GGG Points will be automatically applied.
        * Any mis-aligned score please consult your Rules/Players Committee.\n\n

        **Tee Box:** All players will play from tee box as stated below.\n  
        ***Unless you meet the criteria of C1 or C2 or have approval from the players committee to play from a forward tee box:***
        * Brown Deer: **Blue - 6306 yd**
        * Dretzka: **Blue - 6538 yd**
        * Oakwood: **Blue - 6737 yd**
        * Whitnall: **Blue - 6308 yd**
        * Currie: **Black - 6444 yd**
        
        ***C1: If your handicap average equals 20+ you will play from the tee box ahead of the default tee box.***
        * Brown Deer: **White - 5893 yd**
        * Dretzka: **White - 5970 yd**
        * Oakwood: **White - 6301 yd**
        * Whitnall: **White - 5909 yd**
        * Currie: **White - 6105 yd**

        ***C2: If you are of Senior Age (60+), you may play from the forward tee.**
        * Brown Deer: **Gold - 4996 yd**
        * Dretzka: **Gold - 4924 yd**
        * Oakwood: **Gold - 5562 yd**
        * Whitnall: **Gold - 5342 yd**
        * Currie: **Gold - 5246 yd**
        

        **Gimmies/Putting:**\n 
        Promote competition of fair play, Putt out\n
        ***Unless one of the below scenario***
        * Your group is holding up the playing field. All players in the group ahead of your's have tee off and are moving to the next hole, pickup - within putter blade length. Example: Putting for par, finish hole with Gimme Par.
        * Your group is holding up the playing field. All players in the group ahead of your's have tee off and are moving to the next hole, pickup with 2 stroke from 15-19 feet 5 full putter length. Example: Putting for par, finish hole with Gimme Bogey.
        * Your group is holding up the playing field. All players in the group ahead of your's have tee off and are moving to the next hole, pickup with 3 stroke from 30+ feet 10 full putter length. Example: Putting for par, finish hole with Gimme Double Bogey.\n
        **Pace of Play Etiquette:** Keep pace of play for your league members and others outside of the league.\n  
        * 2 Minutes ball search.
        * If the group behind you has reached the tee box while you are still searching for your ball, STOP searching - drop at point of entry or lateral drop and continue play.
        * Help your playing partners spot and search for their ball.
        * Search smartly: If one of the group's playing partner is helping another player search for their ball, You NEED to move on and play your ball. The entire group **DOES NOT** need to search for one players ball.
        * Play ready golf.
        * Move off the greens and record score at the next tee box.
        * Use common sense to keep play moving.
        * If your group is warned by the golf course ranger, it is your group's responsibility to catch up.\n\n

        **DNFs:** If you cannot finish, mark 'DNF'.
        """)
        
        st.info("**Note:** The League Committee reserves the right to amend, add, or remove rules during the season to optimize operations, resolve procedural issues, or adjust gameplay as necessary. All players are expected to uphold the integrity of the game. For any disputes, please contact the Players Committee.")

    elif info_category == "Schedule":
        st.subheader("📅 2026 Season Schedule")
        courses = ["Dretzka", "Currie", "Whitnall", "Brown Deer", "Oakwood", "Dretzka", "Currie", "Brown Deer", "Whitnall", "Oakwood", "Dretzka", "Brown Deer", "Grant"]
        league_start = pd.to_datetime("2026-05-31")
        
        schedule_data = []
        for i in range(1, 14):
            current_date = league_start + pd.Timedelta(weeks=i-1)
            course_name = courses[i-1] 
            if i == 4: note = "GGG Event- 2 Man Team Greensome (18 holes)"
            elif i == 8: note = "GGG Event- 4 Man Team Scramble (18 holes)"
            elif i == 12: note = "GGG Event- Double Points (18 holes)"
            else: note = "Regular Round"
            schedule_data.append({"Week": f"Week {i}", "Date": current_date.strftime('%B %d, %Y'), "Course": course_name, "Note": note})
        
        schedule_data.append({"Week": "FINALE", "Date": "August 28, 2026", "Course": "TBD", "Note": "GGG Event- GGGolf Finale & Friends & Family Picnic"})

        for entry in schedule_data:
            is_event = "GGG Event" in entry['Note']
            header = f"{'⭐ ' if is_event else ''}{entry['Week']}: {entry['Course']}"
            with st.expander(header):
                col1, col2 = st.columns([1, 2])
                with col1:
                    st.write(f"**Date:** {entry['Date']}")
                    st.write(f"**Format:** {entry['Note']}")
                with col2:
                    if "2 Man Team Greensome" in entry['Note']:
                        st.info("""
                        **2-Man Greensomes Rules:**
                        * Both players tee off and select the desire Drive to play from.
                        * The player's whose drive was not choosen, hits the second shot. Alternate through until the hole is complete.
                        * Team members receives the same GGG points for the week.
                        * **Handicap:** No handicap applied for this round.
                        * **Partners:** Entire field of players cut in half. Bottom tier will enter into a Draft Lottery.
                        * **Lottery:** Lowest ranked player will receive 6 balls in the lottery. Second lowest will receive 4 balls, Third lowest will receive 2 balls. The rest will receive 1 ball.
                        * **Draft:** All balls are randomly picked, which ever players name is picked, that player can pick any player from the top tier to play as their partner.
                        """)
                    elif "4 Man Team Scramble" in entry['Note']:
                        st.info("""
                        **4-Man Team Battle Scramble:**
                        * Any team with less then 4 players, the team can choose to play as the fourht player but MUST rotate alternate shot to play as the fourth player.
                        * All players tee off and selects the desired drive.
                        * All players continue play from best desired shot until hole is complete.
                        * Team members receives the same GGG points for the week.
                        * **Handicap:** No handicap applied for this round.
                        * **Partners:** Lowest points players will enter into lottery.
                        * **Lottery:** Lowest points player pick first for position to draft. Continue on until all capitans have a position.
                        * **Draft:** Capitans draft in their order any player until all players has been selected.
                        """)
                    elif "Double Points" in entry['Note']:
                        st.success("""
                        **Double Points Event:**
                        * Regular individual stroke play with your current GGG handicap.
                        * Front 9 points + Back 9 Point
                        * **Example 1:** You win the front But you end up last place in back. Your front GGG point is 100 points front and your back GGG points is 1 point. Total 101 points
                        * **Example 2:** You come in Third in the front and in the back you came in Second. Front GGG points for Third is 64 points and for Second points is 77 points. You get total 141
                        * **Example 3:** You win front and back. You get 100 for front and 100 for back, total 200 points
                        * **Example 4:** You are last front and back. You get 1 for front and 1 for back, total 2 points                        
                        """)
                    elif "Finale" in entry['Note']:
                        st.warning("Season finale and trophy presentation. Details to be announced.")
                    else:
                        st.write("Standard league play rules and rolling handicaps apply.")

    elif info_category == "Prizes":
        st.subheader("🏆 Prize Pool")
        st.info("The GGGOLF FINALE will determine the order of prize selection.\n\n"
        "**Note:** GGG Challenge winners override the FINALE prize pick order.")

        prizes = [
            {"img": "GGGopenBanner2.jpg", "desc": "GGG 2026 Open Banner."},
            {"img": "rockstarBag1.jpg", "desc": "Limited Edition OGIO Rockstar carry/stand golf Bag."},
            {"img": "taylormadeBag.jpg", "desc": "TaylorMade Select ST Stand Bag - Lightweight and durable."},
            {"img": "PackerJacket.jpg", "desc": "GB Packers 3 layer softshell jacket. Size: XL"},
            {"img": "takeya.jpg", "desc": "TAKEYA Insulated Stainless 18oz drink container."},
            {"img": "radgolfgps.jpg", "desc": "RADGOLF GPS Watch."},
            {"img": "70wedge.jpg", "desc": "FULL CHOICE 70 degree Wedge."},
            {"img": "ForezoBallMarkers.jpg", "desc": "Slope Master Ball Marker & Forezo Putter Grip."},
            {"img": "Sandals.jpg", "desc": "Sandals."}
        ]

        cols = st.columns(2)
        for i, prize in enumerate(prizes):
            with cols[i % 2]:
                with st.container(border=True):
                    image_to_display = prize["img"]
                    if prize["img"] == "GGGopenBanner2.jpg":
                        img = Image.open("GGGopenBanner2.jpg")
                        image_to_display = img.rotate(-90, expand=True)
                    elif prize["img"] == "radgolfgps.jpg":
                        img = Image.open("radgolfgps.jpg")
                        image_to_display = img.rotate(90, expand=True)
                    elif prize["img"] == "ForezoBallMarkers.jpg":
                        img = Image.open("ForezoBallMarkers.jpg")
                        image_to_display = img.rotate(-90, expand=True)

                    st.image(image_to_display, use_container_width=True)
                    st.caption(prize["desc"])
                   
    elif info_category == "Expenses":
        st.subheader("💵 League Expenses")
        st.write("Breakdown of league fees and administrative costs.")

        try:
            # SUPABASE READ
            response = conn.table("expenses").select("*").execute()
            expenses_df = pd.DataFrame(response.data) if response.data else pd.DataFrame(columns=["prize", "cost"])
            expenses_df = expenses_df.dropna(how='all')
        except Exception as e:
            st.error(f"Error loading expenses: {e}")
            expenses_df = pd.DataFrame(columns=["prize", "cost"])


        with st.expander("Add a Prize / Expense", expanded=True):
            with st.form("add_expense_form", clear_on_submit=True):
                prize_desc = st.text_input("Prize Description", placeholder="e.g., Season Trophy")
                prize_cost = st.number_input("Cost (USD)", min_value=0.0, step=1.0, format="%.2f")
                if st.form_submit_button("Add Expense", type="primary"):
                    if prize_desc:
                        # OPTIMIZED: Ensure consistent casing for keys
                        new_entry = {"prize": prize_desc.strip(), "cost": float(prize_cost)}
                        # INSERT using the correct lowercase table name
                    try:
                        conn.table("expenses").insert(new_entry).execute()
                        st.cache_data.clear()
                        st.success(f"Saved: {prize_desc}")
                        time.sleep(0.5) # Reduced sleep for better UX
                        st.rerun()
                    except Exception as e:
                            # This catches the APIError and prints the REAL message
                            st.error(f"⚠️ Database Error: {e}")
                    else:
                        st.warning("Please enter a description.")

        st.divider()

        if not expenses_df.empty:
            disp_df = expenses_df.copy()
            
            # 1. Standardize column names to handle Case Sensitivity
            # This makes sure we find the cost column regardless of if it's 'Cost' or 'cost'
            cols = {col.lower(): col for col in disp_df.columns}
            
            target_cost = cols.get('cost')
            target_prize = cols.get('prize')

            if target_cost and target_prize:
                # 2. Prepare the numeric data
                disp_df[target_cost] = pd.to_numeric(disp_df[target_cost], errors='coerce').fillna(0)
                
                # 3. Create a formatted display column
                disp_df["Amount"] = disp_df[target_cost].map(lambda x: f"${x:,.2f}")
                
                # 4. Show the table with the correct columns
                st.dataframe(
                    disp_df[[target_prize, "Amount"]], 
                    use_container_width=True, 
                    hide_index=True
                )
                
                total = disp_df[target_cost].sum()
                st.markdown(f"### 💰 Total League Costs: ${total:,.2f}")
            else:
                st.warning(f"Found data, but couldn't find 'Prize' or 'Cost' columns. Found: {list(disp_df.columns)}")
        else:
            st.info("No expenses found in the database yet.")

    elif info_category == "Members":
        st.subheader("👥 League Members")
        st.write("This list is automatically populated from registered players. New registrations will appear here after the sheet updates.\n\n"
                "GGGOLF 2026 registration fees is **$140**.\n\n"
                "Please pay registration fees by **Week 1** to Finance Officer: Mike Yang.\n\n"
                "Accepted form of payment: PayPal/Cash/Venmo/CashApp/Apple Pay/Zelle/EBTx2")

        if df_main is None or df_main.empty:
            st.info("No registered members yet.")
        else:
            members_df = df_main[df_main['Week'] == 0].copy()
            if members_df.empty:
                st.info("No registered members yet.")
            else:
                display_cols = ['Player']
                if 'Acknowledged' in members_df.columns:
                    members_df['Acknowledged'] = members_df['Acknowledged'].astype(bool)
                    display_cols.append('Acknowledged')
                members_df = members_df[display_cols].drop_duplicates().sort_values('Player').reset_index(drop=True)
                
                st.markdown(f"**Total Members:** {len(members_df)}")
                st.dataframe(members_df, use_container_width=True, hide_index=True)

    elif info_category == "Bets":
        st.subheader("🤝 Season Bets")
        
        try:
            # OPTIMIZED: Standard Supabase Read
            response = conn.table("bets").select("*").execute()
            bets_df = pd.DataFrame(response.data) if response.data else pd.DataFrame(columns=["id", "player_1", "player_2", "wager", "terms", "status"])
        except Exception as e:
            st.error(f"Error loading bets: {e}")
            bets_df = pd.DataFrame(columns=["id", "player_1", "player_2", "wager", "terms", "status"])

        with st.expander("➕ Log a New Bet"):
            with st.form("new_bet_form", clear_on_submit=True):
                col1, col2 = st.columns(2)
                p1 = col1.selectbox("Player 1", options=EXISTING_PLAYERS)
                p2 = col2.selectbox("Player 2", options=EXISTING_PLAYERS)
                wager = st.text_input("The Wager")
                terms = st.text_area("Terms")
                
                if st.form_submit_button("Post Official Bet", use_container_width=True, type="primary"):
                    if p1 != p2 and wager:
                        new_bet = {
                            "player_1": p1, 
                            "player_2": p2, 
                            "wager": wager, 
                            "terms": terms, 
                            "status": "⏳ Pending"
                        }
                        try:
                            conn.table("bets").insert(new_bet).execute()
                            st.cache_data.clear()
                            st.success("Bet saved to database!")
                            time.sleep(0.5)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Save Error: {e}")
                    else:
                        st.error("Check player selection and wager details.")

        st.divider()

        if not bets_df.empty:
            # Display table with readable column names
            disp_bets = bets_df.copy()
            disp_bets.columns = [c.replace("_", " ").title() if c != 'id' else c for c in disp_bets.columns]
            st.dataframe(disp_bets.drop(columns=["id"]), use_container_width=True, hide_index=True)
            
            with st.expander("🏅 Update a Bet Status"):
                bet_to_update = st.selectbox(
                    "Select Bet to Update", 
                    options=bets_df.to_dict('records'),
                    format_func=lambda x: f"{x['player_1']} vs {x['player_2']} ({x['wager']})"
                )
                
                new_status = st.radio("Outcome", ["⏳ Pending", "🏆 P1 Wins", "🏆 P2 Wins", "🤝 Draw"])
                
                if st.button("Update Status"):
                    try:
                        # OPTIMIZED: Update specifically by the ID (much safer)
                        conn.table("bets").update({"status": new_status}).eq("id", bet_to_update["id"]).execute()
                        st.cache_data.clear()
                        st.success("Status Updated!")
                        time.sleep(0.5)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Update Error: {e}")
        else:
            st.info("No active bets found in the database.")
                        
with tabs[6]: # Registration
    st.header("👤 Registration")
    
    if not st.session_state.get("reg_access"):
        st.info("Please enter the League Registration Key provided by the League Officers to begin.")
        with st.form("league_key_form"):
            user_key = st.text_input("League Key", type="password", key="reg_gate_key_input")
            submit_key = st.form_submit_button("🔓 Unlock Registration", use_container_width=True, type="primary")
            
            if submit_key:
                if user_key == REGISTRATION_KEY:
                    st.session_state["reg_access"] = True
                    st.success("Key Accepted! Please provide your details below.")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ Invalid League Key. Please contact an Officer.")

    else:
        st.info(
            "By registering for the GGGolf Summer League you confirm that you have read, "
            "understand, and agree to abide by the League Rules, Handicaps, and Policies. "
            "Registration indicates acceptance of these terms."
        )

        ack = st.checkbox("I have read and agree to the League Rules and Policies", key="reg_ack_checkbox")

        with st.form("registration_form", clear_on_submit=True):
            st.subheader("📝 New Player Details")
            
            n = st.text_input("Full Name", key="reg_name_input")
            p = st.text_input("Create 4-Digit PIN", max_chars=4, help="Used to unlock your scorecard", key="reg_pin_input")
            
            submit_reg = st.form_submit_button("Complete Registration", use_container_width=True, type="primary")
            
            if submit_reg:
                if not ack:
                    st.warning("You must acknowledge that you have read and agree to the League Rules and Policies before registering.")
                elif n and len(p) == 4:
                    try:
                        new_reg = {
                            "Week": 0, "Player": n, "PIN": str(p), "Handicap": 0.0, "DNF": True,
                            "Pars_Count": 0, "Birdies_Count": 0, "Eagle_Count": 0,
                            "Total_Score": 0, "Net_Score": 0.0, "Acknowledged": True
                        }
                        
                        # SUPABASE INSERT
                        conn.table("league_scores_2026").insert(new_reg).execute()

                        st.success(f"Welcome to the league, {n}!")
                        st.cache_data.clear()
                        time.sleep(1.5)
                        st.session_state["reg_access"] = False 
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"Registration Error: {e}")
                else:
                    st.warning("Please ensure name is filled and PIN is exactly 4 digits.")

with tabs[7]: # Admin
    st.header("⚙️ Admin Control Panel")
    
    if not st.session_state.get("authenticated"):
        st.info("Please enter the Administrative Password to access league management tools.")
        
        with st.form("admin_login_form"):
            admin_input = st.text_input("Admin Password", type="password", key="admin_password_field")
            submit_admin = st.form_submit_button("🔓 Verify Admin", use_container_width=True, type="primary")
            
            if submit_admin:
                if admin_input == ADMIN_PASSWORD:
                    st.session_state["authenticated"] = True
                    st.success("Access Granted!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ Incorrect Admin Password.")

    else:
        st.subheader("Leaderboard Management")
        st.warning("⚠️ Warning: Resetting the live board will delete all current scores. This action cannot be undone.")

        # Safety Lock for Reset
        confirm_reset = st.checkbox("I confirm that I want to delete all LIVE SCORES.")
        
        if confirm_reset:
            if st.button("🚨 DELETE ALL LIVE SCORES", use_container_width=True, type="primary"):
                try:
                    # Target correct table and force delete
                    conn.table("live_scores").delete().neq("id", 0).execute()
                    
                    st.cache_data.clear()
                    st.success("✅ Live Round has been reset!")
                    time.sleep(1.5)
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to reset table: {e}")
        else:
            st.button("🚨 DELETE ALL LIVE SCORES", use_container_width=True, disabled=True)

        st.divider()
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Refresh Data Cache", use_container_width=True):
                st.cache_data.clear()
                st.toast("App data synced with database.")
        
        with col2:
            if st.button("🔒 Lock Admin Panel", use_container_width=True):
                st.session_state["authenticated"] = False
                st.rerun()
