import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import time
import random
import altair as alt
from PIL import Image # Ensure this is at the top of your file

# --- 1. CONFIGURATION & SESSION STATE ---
st.set_page_config(page_title="2026 GGGolf Summer League", layout="wide")

ADMIN_PASSWORD = "!@#Seahawks6145!@#"
REGISTRATION_KEY = "2026!@#"
SESSION_TIMEOUT = 2 * 60 * 60  # Updated: 2 hours in seconds

if "api_cooling_until" not in st.session_state: st.session_state["api_cooling_until"] = 0
if "unlocked_player" not in st.session_state: st.session_state["unlocked_player"] = None
if "authenticated" not in st.session_state: st.session_state["authenticated"] = False
if "unlocked_player" not in st.session_state: st.session_state["unlocked_player"] = None
if "login_timestamp" not in st.session_state: st.session_state["login_timestamp"] = 0
if "reg_access" not in st.session_state: st.session_state["reg_access"] = False

conn = st.connection("gsheets", type=GSheetsConnection)

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
        # Increase TTL to 10 seconds to reduce API hits
        data = conn.read(ttl=10) 
        if data is None or data.empty or 'Player' not in data.columns: 
            return pd.DataFrame(columns=MASTER_COLUMNS)
        
        df = data.dropna(how='all')
        # Filter out specific players
        df = df[df['Player'].str.lower() != 'john']
        
        return df[df['Player'] != ""]
    except Exception as e:
        if "429" in str(e):
            st.warning("⚠️ High traffic: Using cached data while Google Sheets rests...")
        return pd.DataFrame(columns=MASTER_COLUMNS)

def calculate_rolling_handicap(player_df, target_week):
    try:
        # 1. Immediately return 0 for exception weeks (4, 8, and 12)
        if target_week in [4, 8, 12]:
            return 0.0

        if 'Total_Score' in player_df.columns:
            player_df = player_df.copy()
            player_df['Total_Score'] = pd.to_numeric(player_df['Total_Score'], errors='coerce')

        # 2. Define weeks that do not count toward handicap history
        excluded_weeks = [4, 8, 12]
        
        # 3. Gather all eligible rounds prior to the target_week
        # This automatically includes pre-season (Week <= 0) and valid regular season weeks
        eligible_rounds = player_df[
            (~player_df['Week'].isin(excluded_weeks)) &
            (player_df['DNF'] == False) &
            (player_df['Week'] < target_week) &
            (player_df['Total_Score'].notna()) &
            (player_df['Total_Score'] > 0)
        ].sort_values('Week', ascending=False)

        # 4. Require a minimum of 3 completed rounds (pre-season or regular)
        if len(eligible_rounds) < 3:
            return 0.0

        # 5. Get the most recent 4 eligible rounds
        last_scores = eligible_rounds.head(4)['Total_Score'].tolist()

        # 6. Calculate using the best 3 of the available rounds (lowest scores)
        last_scores.sort() # Sorts ascending, putting the 3 lowest scores at the front
        hcp = round((sum(last_scores[:3]) / 3) - 36, 1)

        return float(hcp)

    except Exception:
        return 0.0

def save_weekly_data(week, player, pars, birdies, eagles, score_val, hcp_val, pin):
    max_retries = 3
    retry_delay = 2 # Initial pause in seconds
    
    for attempt in range(max_retries):
        try:
            st.cache_data.clear()
            existing_data = load_data()
            is_dnf = (score_val == "DNF")
            final_gross = 0 if is_dnf else int(score_val)
            
            new_entry = pd.DataFrame([{
                'Week': week, 'Player': player, 'Pars_Count': pars, 'Birdies_Count': birdies, 
                'Eagle_Count': eagles, 'Total_Score': final_gross, 'Handicap': hcp_val, 
                'Net_Score': (final_gross - hcp_val) if not is_dnf else 0, 'DNF': is_dnf, 'PIN': pin
            }])
            
            # Remove any existing entry for this player/week to avoid duplicates, then append the new one
            updated_df = pd.concat([existing_data[~((existing_data['Week'] == week) & (existing_data['Player'] == player))], new_entry], ignore_index=True)
            
            conn.update(data=updated_df[MASTER_COLUMNS])
            st.cache_data.clear()
            
            st.success(f"👍 Score Submitted Successfully for {player}!", icon="✅")
            time.sleep(2) 
            st.rerun()
            return # Exit function on success
            
        except Exception as e:
            if "429" in str(e) or "Quota" in str(e):
                if attempt < max_retries - 1:
                    st.warning(f"⚠️ High traffic. Queueing your score... (Retrying in {retry_delay}s)")
                    time.sleep(retry_delay)
                    retry_delay *= 2 # Double the wait time for the next attempt
                else:
                    st.error("❌ The server is experiencing very high traffic. Please wait 60 seconds and submit your score again.")
                    break
            else:
                st.error(f"❌ An error occurred: {e}")
                break
# --- 3. DATA LOAD ---
df_main = load_data()
EXISTING_PLAYERS = sorted(df_main['Player'].unique().tolist()) if not df_main.empty else []

# --- 4. APP UI ---
st.markdown("<div style='text-align: center;'>", unsafe_allow_html=True)
st.image("GGGOLF-2.png", width=120) 
st.markdown("<h1>GGGOLF League 2026</h1>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

tabs = st.tabs(["📝 Scorecard", "🏆 Standings", "📅 History", "🏁 GGG Challenge", "ℹ️ League Info", "👤 Registration", "⚙️ Admin"])

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
        
        # Check if the session is still valid (2-hour timeout logic)
        # Ensure SESSION_TIMEOUT = 7200 is defined globally
        is_unlocked = (st.session_state.get("unlocked_player") == player_select and 
                      (time.time() - st.session_state.get("login_timestamp", 0)) < SESSION_TIMEOUT) or \
                      st.session_state.get("authenticated", False)
        
        if not is_unlocked:
            # --- LOCKED STATE: Only show PIN entry ---
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
            # --- UNLOCKED STATE: Show everything else ---
            p_data = df_main[df_main['Player'] == player_select]
                       

            # 1. Compact Week Selection
            st.markdown("### 📅 Select Week")

            # Creating categories to keep the UI clean
            week_categories = {
                "Pre-Season": [-2, -1, 0],
                "Phase 1": [1, 2, 3, 4],
                "Phase 2": [5, 6, 7, 8],
                "Phase 3": [9, 10, 11, 12],
                "Finals": [13, 14]
            }

            # Create three columns or a single container for the segmented control
            # Using segmented_control for a "Tab" feel
            w_s = st.segmented_control(
                "Choose Week",
                options=[-2, -1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14],
                format_func=lambda x: f"P{abs(x-1)}" if x <= 0 else f"W{x}",
                selection_mode="single",
                default=1, # Sets Week 1 as default
                key=f"week_tabs_{player_select}"
            )

            # If they haven't clicked one yet, default to Week 1
            if w_s is None:
                w_s = 1

            # Display a quick label so they know exactly what they picked
            if w_s <= 0:
                st.caption(f"📍 Currently Entering: **Pre-Season Round {abs(w_s-1)}**")
            elif w_s in [4, 8, 12]:
                st.caption(f"📍 Currently Entering: **Week {w_s} (Event Week)**")
            else:
                st.caption(f"📍 Currently Entering: **Week {w_s}**")

            # 2. Handicap Logic
            if w_s <= 0:
                current_hcp = 0.0
                st.info("🛠️ Pre-Season: Logging rounds to establish your Week 1 handicap.")
            elif w_s in [4, 8, 12]:  # <--- UPDATED to include Week 12
                current_hcp = 0.0
                st.info("💡 GGG Event: No handicap applied for this round.")
            else:
                # Calls the new, consolidated logic that handles empty eligible rounds automatically
                current_hcp = calculate_rolling_handicap(p_data, w_s)
            
            # 3. Stats Dashboard
            h_disp = f"+{abs(current_hcp)}" if current_hcp < 0 else f"{current_hcp}"
            played_rounds = p_data[(p_data['Week'] > 0) & (p_data['DNF'] == False)].sort_values('Week')
            
            st.markdown(f"### 📊 {player_select}'s Season Dashboard")
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Current HCP", h_disp)
            m2.metric("Avg Net", f"{played_rounds['Net_Score'].mean():.1f}" if not played_rounds.empty else "N/A")
            m3.metric("Total Pars", int(played_rounds['Pars_Count'].sum()))
            m4.metric("Total Birdies", int(played_rounds['Birdies_Count'].sum()))
            m5.metric("Total Eagles", int(played_rounds['Eagle_Count'].sum()))

            # 4. Progress Chart
            if not played_rounds.empty:
                chart = alt.Chart(played_rounds).mark_line(color='#2e7d32', strokeWidth=3).encode(
                    x=alt.X('Week:O'),
                    y=alt.Y('Net_Score:Q', scale=alt.Scale(reverse=True, zero=False))
                ) + alt.Chart(played_rounds).mark_point(color='#2e7d32', size=100, filled=True).encode(x='Week:O', y='Net_Score:Q')
                st.altair_chart(chart.properties(height=250), use_container_width=True)

            st.divider()

            # 5. Score Entry Form
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

# --- New streamlined GGG Challenge tab (replace the existing with tabs[3] block) ---
with tabs[3]:  # GGG Challenge
    st.header("🏁 GGG Challenge")
    st.write("Seasonal challenges and reward opportunities for GGGolf members.")
    st.divider()

    challenge_options = ["Season Ball Challenge", "Gold Card", "Most Pars", "Most Birdies", "Most Eagles"]
    challenge_selection = st.radio("Select Challenge:", challenge_options, horizontal=True)

    st.info("Challenges will be announced here during the season. Each challenge includes a short description, cost (if any), eligibility rules, and how to participate.")

    col_main, col_side = st.columns([3, 1])

    with col_main:
        # --- EXISTING CHALLENGES ---
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

        # --- NEW CHALLENGES ---
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
                - Payouts will be awarded to the top 3 players (based on final tally).
                """)
                
            #st.markdown("### Registered Players")
            # Placeholder: Replace with your actual participant list logic
            #st.write("*(List of accepted participants will appear here)*")
            
            #if st.button(f"Join {challenge_selection}", key=f"join_{challenge_selection}"):
                #st.success(f"Registration request submitted for {challenge_selection}!")


# --- Registration Logic for GGG Challenges ---
        st.markdown("### Registered Players")
        
        # 1. Initialize participants variable to prevent NameError
        participants = []
        
        # 2. Fetch current registrations
        try:
            reg_df = conn.read(worksheet="ChallengeRegistrations")
            # Ensure the DataFrame is not empty before filtering
            if not reg_df.empty and 'ChallengeName' in reg_df.columns:
                participants = reg_df[reg_df['ChallengeName'] == challenge_selection]['PlayerName'].unique().tolist()
            
            if participants:
                for p in participants:
                    st.text(f"✅ {p}")
            else:
                st.write("No players registered yet.")
        except Exception as e:
            st.warning(f"Could not load registration list. Ensure 'ChallengeRegistrations' sheet exists and has headers. Error: {e}")

        # 3. Add Registration button
        if st.button(f"Join {challenge_selection}", key=f"join_{challenge_selection}"):
            player_name = st.session_state.get("unlocked_player")
            
            if not player_name:
                st.error("Please log in to register.")
            elif player_name in participants:
                st.info("You are already registered for this challenge.")
            else:
                # Proceed with registration...
                new_reg = pd.DataFrame([{
                    "PlayerName": player_name,
                    "ChallengeName": challenge_selection,
                    "RegistrationDate": pd.Timestamp.now().strftime("%Y-%m-%d")
                }])
                
                # Fetch fresh data to ensure we don't overwrite concurrent changes
                reg_df = conn.read(worksheet="ChallengeRegistrations")
                updated_reg_df = pd.concat([reg_df, new_reg], ignore_index=True)
                
                try:
                    conn.update(worksheet="ChallengeRegistrations", data=updated_reg_df)
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
        
with tabs[4]: # League Info
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
            **Player Advocacy:** This Committee serves as the formal link between the membership and leadership. 
            They are tasked with **maintaining competitive integrity, hearing member grievances, and vetting player-driven initiatives.** Their role ensures that the evolution of the league is always informed by the needs of the players.
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
        * **Option B:** If you do not complete 3 rounds, you will start Week 1 with a 0.0 handicap (or your current average) as per standard rolling math.
        """)

        st.divider()
        st.subheader("Handicap Calculation Transparency")
        st.write(
            "Use the tool below to inspect how a player's handicap is derived. "
            "This shows pre-season rounds, the last eligible rounds used, and the exact math (best 3 of last 4 to par 36)."
        )

        # Defensive: ensure df_main exists
        if 'df_main' not in globals() or df_main is None or df_main.empty:
            st.warning("No player data available to show handicap breakdown.")
        else:
            # Build player list from registration rows (Week == 0) or all players if registration rows missing
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

                # Fetch player rows
                p_df = df_main[df_main['Player'] == sel_player].copy()
                if p_df.empty:
                    st.warning("No recorded rounds for this player.")
                else:
                    # Pre-season rounds (Week <= 0)
                    pre_season = p_df[(p_df['Week'] <= 0) & (p_df['DNF'] == False) & (p_df['Total_Score'] > 0)].sort_values('Week', ascending=False)
                    # Regular eligible rounds: Week > 0, exclude event weeks, DNF False, and Week < target_week
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

                    # Compute the handicap breakdown using the same logic as calculate_rolling_handicap
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
                            used_scores = sorted_scores[:3]  # best 3 of last 4 (or 3 of 3)
                            avg_score = sum(used_scores) / 3
                            hcp_val = round(avg_score - 36, 1)
                            method = f"Best 3 of last 4 eligible rounds ({len(last_scores)} available rounds evaluated)"

                        # Display the numeric breakdown
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

                        # Show a small table marking which rounds were used
                        with st.expander("Detailed Rounds Table (marking used rounds)"):
                            # Build a combined table of all relevant rounds for context
                            combined = pd.concat([pre_season, regular_rounds]).drop_duplicates().sort_values('Week', ascending=False)
                            if combined.empty:
                                st.write("No rounds to display.")
                            else:
                                combined_display = combined[['Week', 'Total_Score', 'DNF']].reset_index(drop=True).copy()
                                # Mark used rows
                                def mark_used(row):
                                    try:
                                        return row['Total_Score'] in used_scores
                                    except Exception:
                                        return False
                                combined_display['UsedInCalc'] = combined_display.apply(mark_used, axis=1)
                                st.dataframe(combined_display, use_container_width=True, hide_index=True)

                        # Provide a short explanation and link back to rules
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
        ***Unless you meet the criteria of C1, C2, C3 or have approval from the players committee to play from a forward tee box:***
        Brown Deer: **Blue - 6306 yd**
        Dretzka: **Blue - 6538 yd**
        Oakwood: **Blue - 6737 yd**
        Whitnall: **Blue - 6308 yd**
        Currie: **Black - 6444 yd**
        
        * C1: If your handicap average equals 20+ you will play from the tee box ahead of the default tee box.
        * C2: If your handicap average equals 35+ or more, you may play from tee box ahead of C1.
        * C3: If you are of Senior Age (60+), you may play from the forward tee.\n\n

        
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
        
        # This replaces the old Live Round warning with a relevant Rules Note
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

        # 1. Organize data into a list of dictionaries for easier management
        prizes = [
            {"img": "GGGopenBanner2.jpg", "desc": "GGG 2026 Open Banner."},
            {"img": "rockstarBag1.jpg", "desc": "Limited Edition OGIO Rockstar carry/stand golf Bag."},
            {"img": "taylormadeBag.jpg", "desc": "TaylorMade Select ST Stand Bag - Lightweight and durable."},
            {"img": "PackerJacket.jpg", "desc": "GB Packers 3 layer softshell jacket. Size: XL"},
            {"img": "takeya.jpg", "desc": "TAKEYA Insulated Stainless 18oz drink container."},
            {"img": "radgolfgps.jpg", "desc": "RADGOLF GPS Watch."},
            {"img": "70wedge.jpg", "desc": "FULL CHOICE 70 degree Wedge."},
            {"img": "ForezoBallMarkers.jpg", "desc": "Slope Master Ball Marker & Forezo Putter Grip."}
            
        ]

        # 2. Use columns to create a responsive grid (2 columns wide)
        cols = st.columns(2)
        for i, prize in enumerate(prizes):
            # 1. This line defines which column to use
            with cols[i % 2]:
                # 2. This line MUST be indented relative to the 'with' above
                with st.container(border=True):
                    image_to_display = prize["img"]
                    if prize["img"] == "GGGopenBanner2.jpg":
                        img = Image.open("GGGopenBanner2.jpg")
                        image_to_display = img.rotate(-90, expand=True)

                    elif prize["img"] == "radgolfgps.jpg":
                        img = Image.open("radgolfgps.jpg")
                        image_to_display = img.rotate(90, expand=True)
                    st.image(image_to_display, use_container_width=True)
                    st.caption(prize["desc"])
                   

    elif info_category == "Expenses":
        st.subheader("💵 League Expenses")
        st.write("Breakdown of league fees and administrative costs.")

        # Load existing data from GSheets
        try:
            expenses_df = conn.read(worksheet="Expenses", ttl=0)
            # Clean up any completely empty rows/cols if they exist
            expenses_df = expenses_df.dropna(how='all')
        except Exception:
            expenses_df = pd.DataFrame(columns=["Prize", "Cost"])

        # --- Form to Add Expense ---
        with st.expander("Add a Prize / Expense", expanded=True):
            with st.form("add_expense_form", clear_on_submit=True):
                prize_desc = st.text_input("Prize Description", placeholder="e.g., Season Trophy")
                prize_cost = st.number_input("Cost (USD)", min_value=0.0, step=1.0, format="%.2f")
                if st.form_submit_button("Add Expense", use_container_width=True, type="primary"):
                    if prize_desc:
                        new_row = pd.DataFrame([{"Prize": prize_desc.strip(), "Cost": float(prize_cost)}])
                        updated_df = pd.concat([expenses_df, new_row], ignore_index=True)
                        conn.update(worksheet="Expenses", data=updated_df)
                        st.cache_data.clear()
                        st.success(f"Saved: {prize_desc}")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.warning("Please enter a description.")

        st.divider()

        # --- Display Table ---
        if not expenses_df.empty:
            # Formatting for display only
            disp_df = expenses_df.copy()
            disp_df["Cost"] = pd.to_numeric(disp_df["Cost"]).map(lambda x: f"${x:,.2f}")
            st.dataframe(disp_df, use_container_width=True, hide_index=True)
            
            total = pd.to_numeric(expenses_df["Cost"]).sum()
            st.markdown(f"### Total Estimated Cost: ${total:,.2f}")
        else:
            st.info("No expenses found in the Google Sheet.")

    elif info_category == "Members":
        st.subheader("👥 League Members")
        st.write("This list is automatically populated from registered players. New registrations will appear here after the sheet updates.\n\n"
                "GGGOLF 2026 registration fees is **$140**.\n\n"
                "Please pay registration fees by **Week 1** to Finance Officer: Mike Yang.\n\n"
                "Accepted form of payment: PayPal/Cash/Venmo/CashApp/Apple Pay/Zelle/EBTx2")

        # Build members list from df_main: registration rows are Week == 0
        if df_main is None or df_main.empty:
            st.info("No registered members yet.")
        else:
            members_df = df_main[df_main['Week'] == 0].copy()
            if members_df.empty:
                st.info("No registered members yet.")
            else:
                # Normalize columns for display
                display_cols = ['Player']
                if 'Acknowledged' in members_df.columns:
                    members_df['Acknowledged'] = members_df['Acknowledged'].astype(bool)
                    display_cols.append('Acknowledged')
                members_df = members_df[display_cols].drop_duplicates().sort_values('Player').reset_index(drop=True)
                
                st.markdown(f"**Total Members:** {len(members_df)}")
                st.dataframe(members_df, use_container_width=True, hide_index=True)

    elif info_category == "Bets":
        st.subheader("🤝 Season Bets")
        
        # Load existing data from GSheets
        try:
            bets_df = conn.read(worksheet="Bets", ttl=0)
            bets_df = bets_df.dropna(how='all')
        except Exception:
            bets_df = pd.DataFrame(columns=["Player 1", "Player 2", "Wager", "Terms", "Status"])

        # --- Form to Add Bet ---
        with st.expander("➕ Log a New Bet"):
            with st.form("new_bet_form", clear_on_submit=True):
                col1, col2 = st.columns(2)
                p1 = col1.selectbox("Player 1", options=EXISTING_PLAYERS)
                p2 = col2.selectbox("Player 2", options=EXISTING_PLAYERS)
                wager = st.text_input("The Wager")
                terms = st.text_area("Terms")
                
                if st.form_submit_button("Post Official Bet", use_container_width=True, type="primary"):
                    if p1 != p2 and wager:
                        new_bet = pd.DataFrame([{
                            "Player 1": p1, "Player 2": p2, 
                            "Wager": wager, "Terms": terms, "Status": "⏳ Pending"
                        }])
                        updated_bets = pd.concat([bets_df, new_bet], ignore_index=True)
                        conn.update(worksheet="Bets", data=updated_bets)
                        st.cache_data.clear()
                        st.success("Bet saved to Google Sheets!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Check player selection and wager details.")

        st.divider()

        # --- Display & Update Section ---
        if not bets_df.empty:
            st.dataframe(bets_df, use_container_width=True, hide_index=True)
            
            # Simple Update Tool
            with st.expander("🏅 Update a Bet Status"):
                bet_idx = st.selectbox("Select Bet #", range(len(bets_df)), format_func=lambda x: f"Bet {x+1}: {bets_df.iloc[x]['Player 1']} vs {bets_df.iloc[x]['Player 2']}")
                new_status = st.radio("Outcome", ["⏳ Pending", "🏆 P1 Wins", "🏆 P2 Wins", "🤝 Draw"])
                if st.button("Update Status"):
                    bets_df.at[bet_idx, "Status"] = new_status
                    conn.update(worksheet="Bets", data=bets_df)
                    st.cache_data.clear()
                    st.rerun()
        else:
            st.info("No active bets found in the Google Sheet.")
                        
#OLD BET CODE -- Keeping for reference
    #elif info_category == "Bets":
        #st.subheader("🤝 Season Bets")
        #st.write("Track all bets")
        #st.divider()
        
        #st.markdown("### Active Wagers")
        # Placeholder dataframe for bets
        #bets_data = pd.DataFrame([
            #{"Player 1": "Txv", "Player 2": "5Hundo", "Wager": "1 pack of Ribeye", "Terms": "Rory wins 2026 Master Txv Lose, Rory Lose 2026 Masters 5Hundo Lose"},
            #{"Player 1": "Lex", "Player 2": "Thunder", "Wager": "1 Duck", "Terms": "First Match, Loser pay 1 Duck"},
        #])
        #st.dataframe(bets_data, use_container_width=True, hide_index=True)


with tabs[5]: # Registration
    st.header("👤 Registration")
    
    # --- PRE-STEP: League Code Verification ---
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

    # --- STEP 2: Player Details ---
    else:
        # Informational note and acknowledgement requirement
        st.info(
            "By registering for the GGGolf Summer League you confirm that you have read, "
            "understand, and agree to abide by the League Rules, Handicaps, and Policies. "
            "Registration indicates acceptance of these terms."
        )

        # Require explicit acknowledgement before allowing registration
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
                        # 1. ADD TO MAIN DATABASE (now includes Acknowledged)
                        new_reg = pd.DataFrame([{
                            "Week": 0, "Player": n, "PIN": p, "Handicap": 0.0, "DNF": True,
                            "Pars_Count": 0, "Birdies_Count": 0, "Eagle_Count": 0,
                            "Total_Score": 0, "Net_Score": 0, "Acknowledged": True
                        }])
                        
                        updated_main = pd.concat([df_main, new_reg], ignore_index=True)
                        # use the existing connection created at module load
                        conn.update(data=updated_main[MASTER_COLUMNS])

                        # 3. FINALIZE
                        st.success(f"Welcome to the league, {n}!")
                        st.cache_data.clear()
                        time.sleep(1.5)
                        st.session_state["reg_access"] = False # Relock for next use
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"Registration Error: {e}")
                else:
                    st.warning("Please ensure name is filled and PIN is exactly 4 digits.")

with tabs[6]: # Admin
    st.header("⚙️ Admin Control Panel")
    
    # --- STEP 1: Secure Login Form ---
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

    # --- STEP 2: Admin Tools (Only visible after successful login) ---
    else:
        st.subheader("Leaderboard Management")
        st.warning("⚠️ Warning: Resetting the live board will delete all current scores in the 'Live Round' tab. This action cannot be undone.")

        # 1. The Reset Button (Wipes the sheet)
        if st.button("🚨 Reset Live Round Scoring", use_container_width=True, type="primary"):
            try:
                hole_headers = [str(i) for i in range(1, 10)]
                empty_df = pd.DataFrame(columns=['Player'] + hole_headers)
                
                conn.update(worksheet="LiveScores", data=empty_df)
                st.cache_data.clear()
                
                st.success("✅ Live Round has been reset!")
                time.sleep(1.5)
                st.rerun()
            except Exception as e:
                st.error(f"Failed to reset sheet: {e}")

        # 2. The Sync Button (Pre-populates the sheet with registered players)
        # ALL CODE BELOW IS NOW CORRECTLY INDENTED
        if st.button("🛠️ Sync All Players to Live Board", use_container_width=True):
            try:
                # Get everyone currently registered from the main data
                all_players = df_main['Player'].unique().tolist()
                hole_cols = [str(i) for i in range(1, 10)]
                
                # Create a fresh table with everyone starting at 0
                synced_df = pd.DataFrame(columns=['Player'] + hole_cols)
                
                for p_name in all_players:
                    if p_name: # skip empty entries
                        row_data = {'Player': p_name, **{col: 0 for col in hole_cols}}
                        synced_df = pd.concat([synced_df, pd.DataFrame([row_data])], ignore_index=True)
                
                # Push the full list to Google Sheets
                conn.update(worksheet="LiveScores", data=synced_df)
                st.cache_data.clear()
                st.success(f"Success! {len(synced_df)} players synced to the Live Board.")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"Sync failed: {e}")

        st.divider()
        
        # Logout / Maintenance Section
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Refresh Data Cache", use_container_width=True):
                st.cache_data.clear()
                st.toast("App data synced with Google Sheets.")
        
        with col2:
            if st.button("🔒 Lock Admin Panel", use_container_width=True):
                st.session_state["authenticated"] = False
                st.rerun()
