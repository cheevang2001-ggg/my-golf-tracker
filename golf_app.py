import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# --- STEP 1: CONFIGURATION & SETUP ---
st.set_page_config(page_title="GGGolf No Animals Winter League", layout="wide") 

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

ADMIN_PASSWORD = "InsigniaSeahawks6145" 

# Added Lefty with Handicap 5
DEFAULT_HANDICAPS = {
    "Cory": 3, "Lex": 7, "Mike": 9,
    "Carter": 5, "Dale": 4, "Long": 6, "Txv": 4,
    "Matt": 2, "NomThai": 4, "VaMeng": 0,
    "Xuka": 0, "Beef": 9, "Lefty": 5
}

FEDEX_POINTS = {
    1: 100, 2: 77, 3: 64, 4: 54, 5: 47, 6: 41,
    7: 36, 8: 31, 9: 27, 10: 24, 11: 21, 12: 18, 13: 16
}

conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=600)
def load_data():
    return conn.read()

def calculate_rolling_handicap(player_df, current_week):
    valid_rounds = player_df[(player_df['Total_Score'] > 0) & (player_df['Week'] < current_week)]
    valid_rounds = valid_rounds.sort_values('Week', ascending=False)
    if len(valid_rounds) < 4:
        return None 
    last_4 = valid_rounds.head(4)['Total_Score'].tolist()
    last_4.remove(max(last_4))
    avg_gross = sum(last_4) / 3
    return int(round(max(0, avg_gross - 36)))

def get_handicaps(current_week):
    df = load_data() 
    calculated_hcps = {}
    for player, hcp in DEFAULT_HANDICAPS.items():
        if not df.empty:
            player_data = df[df['Player'] == player]
            rolling = calculate_rolling_handicap(player_data, current_week)
            calculated_hcps[player] = rolling if rolling is not None else hcp
        else:
            calculated_hcps[player] = hcp
    return calculated_hcps

def save_data(week, player, pars, birdies, eagles, score_val, hcp_val):
    st.cache_data.clear()
    existing_data = conn.read(ttl=0)
    
    is_dnf = (score_val == "DNF")
    final_gross = 0 if is_dnf else int(score_val)
    final_net = 0 if is_dnf else (final_gross - hcp_val)
    new_entry = pd.DataFrame([{
        'Week': week, 'Player': player,
        'Pars_Count': pars, 'Birdies_Count': birdies, 'Eagle_Count': eagles,
        'Total_Score': final_gross, 'Handicap': hcp_val, 
        'Net_Score': final_net, 'DNF': is_dnf
    }])
    if not existing_data.empty:
        updated_df = existing_data[~((existing_data['Week'] == week) & (existing_data['Player'] == player))]
        final_df = pd.concat([updated_df, new_entry], ignore_index=True)
    else:
        final_df = new_entry
    conn.update(data=final_df)
    st.cache_data.clear()

# --- DATA PROCESSING ---
df_main = load_data()
if not df_main.empty:
    df_main = df_main.fillna(0)
    df_main['DNF'] = df_main.get('DNF', False).astype(bool)
    df_main['animal_pts'] = 0.0
    for week in df_main['Week'].unique():
        mask = (df_main['Week'] == week) & (df_main['DNF'] == False)
        if mask.any():
            ranks = df_main.loc[mask, 'Net_Score'].rank(ascending=True, method='min')
            df_main.loc[mask, 'animal_pts'] = ranks.map(FEDEX_POINTS).fillna(0)

# --- UI ---
st.markdown("<div style='text-align: center;'>", unsafe_allow_html=True)
st.image("GGGOLF-2.png", width=120) 
st.markdown("<h1 style='margin-top: -10px;'>GGGolf - No Animals</h1><p style='margin-top: -20px; color: gray;'>Winter League 2026</p>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

st.divider()

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📝 Scorecard", "🏆 Standings", "📅 History", "📜 Info", "⚙️ Admin", "🏆 Bracket"])

# --- TAB 1: SCORECARD ---
with tab1:
    c1, c2 = st.columns(2)
    player_select = c1.selectbox("Select Player", sorted(DEFAULT_HANDICAPS.keys()), key="p_sel")
    week_select = c2.selectbox("Select Week", range(1, 13), key="w_sel")
    
    current_hcps_map = get_handicaps(week_select)
    suggested_hcp = current_hcps_map.get(player_select)
    
    if not df_main.empty:
        hist_prior = df_main[(df_main['Player'] == player_select) & (df_main['Week'] < week_select)]
        s_pars_prior = int(hist_prior['Pars_Count'].sum())
        s_birdies_prior = int(hist_prior['Birdies_Count'].sum())
        s_eagles_prior = int(hist_prior['Eagle_Count'].sum())
        
        this_wk = df_main[(df_main['Player'] == player_select) & (df_main['Week'] == week_select)]
        wk_p = int(this_wk.iloc[0]['Pars_Count']) if not this_wk.empty else 0
        wk_b = int(this_wk.iloc[0]['Birdies_Count']) if not this_wk.empty else 0
        wk_e = int(this_wk.iloc[0]['Eagle_Count']) if not this_wk.empty else 0
        wk_s = int(this_wk.iloc[0]['Total_Score']) if (not this_wk.empty and this_wk.iloc[0]['Total_Score'] != 0) else 45
        wk_h = int(this_wk.iloc[0]['Handicap']) if not this_wk.empty else suggested_hcp
    else:
        s_pars_prior = s_birdies_prior = s_eagles_prior = 0
        wk_p = wk_b = wk_e = 0
        wk_s, wk_h = 45, suggested_hcp

    st.divider()

    r1 = st.columns(3)
    sel_pars = r1[0].selectbox("Pars (Week)", options=range(10), index=wk_p, key=f"p_in_{player_select}_{week_select}")
    sel_birdies = r1[1].selectbox("Birdies (Week)", options=range(10), index=wk_b, key=f"b_in_{player_select}_{week_select}")
    sel_eagles = r1[2].selectbox("Eagles (Week)", options=range(10), index=wk_e, key=f"e_in_{player_select}_{week_select}")

    met1, met2, met3 = st.columns(3)
    met1.metric("Total Pars", s_pars_prior + sel_pars)
    met2.metric("Total Birdies", s_birdies_prior + sel_birdies)
    met3.metric("Total Eagles", s_eagles_prior + sel_eagles)
    
    st.divider()

    m1, m2, m3, m4 = st.columns([2, 2, 2, 2])
    score_options = ["DNF"] + list(range(30, 73))
    score_select = m1.selectbox("Gross Score", options=score_options, index=(0 if wk_s==0 else score_options.index(wk_s)), key=f"gs_in_{player_select}_{week_select}")
    hcp_in = m2.number_input("Enter Handicap", value=wk_h, key=f"h_in_{player_select}_{week_select}")
    
    m3.metric("Suggested HCP", suggested_hcp)
    
    if score_select == "DNF":
        m4.metric("Net Score", "DNF")
    else:
        m4.metric("Net Score", int(score_select) - hcp_in)

    if st.session_state["authenticated"]:
        if st.button("Submit Score", use_container_width=True, key="sub_btn"):
            save_data(week_select, player_select, sel_pars, sel_birdies, sel_eagles, score_select, hcp_in)
            st.success(f"Scores updated for {player_select}!")
            st.rerun()
    else:
        st.warning("Read-Only Mode. Login in Admin tab to edit.")
        st.button("Submit Score", use_container_width=True, disabled=True, key="sub_dis")

# --- TAB 2: STANDINGS ---
with tab2:
    if not df_main.empty:
        st.markdown("<h2 style='text-align: center;'>League Standings</h2>", unsafe_allow_html=True)
        valid_scores = df_main[df_main['DNF'] == False]
        standings = df_main.groupby('Player').agg({'animal_pts': 'sum'}).rename(columns={'animal_pts': 'Animal Pts'}).reset_index()
        avg_nets = valid_scores.groupby('Player').agg({'Net_Score': 'mean'}).rename(columns={'Net_Score': 'Avg Net'}).reset_index()
        standings = standings.merge(avg_nets, on='Player', how='left').fillna(0)
        final_standings = standings.round(1).sort_values(by=['Animal Pts', 'Avg Net'], ascending=[False, True])

        dynamic_height = (len(final_standings) + 1) * 35 + 3

        left_spacer, center_content, right_spacer = st.columns([1, 4, 1])
        with center_content:
            st.dataframe(
                final_standings, 
                use_container_width=True, 
                hide_index=True,
                height=dynamic_height
            )
    else:
        st.info("No scores recorded yet.")

# --- TAB 3: WEEKLY HISTORY ---
with tab3:
    st.markdown("<h2 style='text-align: center;'>📅 Weekly History</h2>", unsafe_allow_html=True)
    if not df_main.empty:
        # 1. Filters
        f1, f2 = st.columns([1, 2])
        filter_player = f1.multiselect("Filter Player", options=sorted(DEFAULT_HANDICAPS.keys()), key="hist_p")
        filter_week = f2.multiselect("Filter Week", options=sorted(df_main['Week'].unique(), reverse=True), key="hist_w")
        
        # 2. Filtering Logic
        history_df = df_main.copy()
        if filter_player:
            history_df = history_df[history_df['Player'].isin(filter_player)]
        if filter_week:
            history_df = history_df[history_df['Week'].isin(filter_week)]
            
        history_df = history_df.sort_values(['Week', 'Player'], ascending=[False, True])
        history_df['Status'] = history_df['DNF'].map({True: "DNF", False: "Active"})
        
        # RENAME the calculated column
        history_df = history_df.rename(columns={'animal_pts': 'Animal Points'})
        
        # 3. Define columns in the specific order requested
        display_cols = [
            'Week', 
            'Player', 
            'Status', 
            'Total_Score', 
            'Handicap', 
            'Net_Score', 
            'Animal Points',  # Moved after Net_Score
            'Pars_Count', 
            'Birdies_Count', 
            'Eagle_Count'
        ]
        final_history = history_df[display_cols]

        # 4. Calculate Dynamic Height
        dynamic_height_hist = max(200, (len(final_history) + 1) * 35 + 3)

        # 5. Display centered
        l_sp, center_hist, r_sp = st.columns([0.1, 9.8, 0.1])
        with center_hist:
            st.dataframe(
                final_history,
                use_container_width=True,
                hide_index=True,
                height=dynamic_height_hist
            )
    else:
        st.info("No history found. Once scores are submitted, they will appear here.")

# --- TAB 4: LEAGUE INFO & PRIZES ---
with tab4:
    # Sub-navigation within the Info Tab
    info_page = st.radio(
        "Select Information Page:",
        ["General Info", "Prizes"],
        horizontal=True,
        key="info_sub_nav"
    )
    
    st.divider()

    if info_page == "General Info":
        st.header("📜 League Information")
        st.markdown("""
        **Drawing:** 5:45pm | **Tee Time:** 6:00pm
        * **Partners:** Randomized by picking playing cards. ***Unless players agree to play versus each other.***
        * **Makeups:** Set your own time with Pin High and complete the round before it expires; the following Friday at 12AM.
        * **Bottom 2 each bay:** Bottom two from each bay buy a bucket next week.
        * **Missed Week:** Return to buy a bucket at start of round.
        * **No Animal Bets:** Bet your Bets, Drink your bets.
        * **No Animal Bay Etiquette:** Return ball to hitting area for next player (1/4 drink penalty).
        * **First Putt/Chips:** In-hole results in drinks for the bay (1/4 or 1/2).
        * **Mulligans:** Owe 1 a bucket right away.
        """)

    elif info_page == "Prizes":
        st.header("Season Prize & Expense Breakdown")
        st.write("Total Pot: **$780** (13 Players x $60)")
        
        # 1. Cash Payout Table
        st.subheader("Cash Payouts")
        payout_data = {
            "Rank": ["1st Place", "2nd Place", "3rd Place", "4th Place", "Total Cash"],
            "Amount": ["$200.00", "$140.00", "$100.00", "$60.00", "$500.00"],
            "Note": ["+ Championship Trophy", "Runner Up", "Third Place", "Fourth Place", "Cash Prize Pool"]
        }
        st.table(pd.DataFrame(payout_data))

        # 2. Expenses Table
        st.subheader("League Expenses")
        expense_data = {
            "Item": ["Championship Trophy", "2 Dozen Golf Balls", "Remaining Balance", "BD Committee - Dale"],
            "Cost": ["$80.00", "$100.00", "$40.00", "$60.00"],
            "Total": ["", "", "", "$280.00"]
        }
        st.table(pd.DataFrame(expense_data))

        # Final Summary
        st.divider()
        st.markdown(f"""
        **Total Accounting:**
        * Total Cash Payouts: **$500**
        * Total League Expenses: **$280**
        * **Grand Total: $780**
        """)
        st.info("$100 remaining will be used for in season tournament.")

# --- TAB 5: ADMIN ---
with tab5:
    st.subheader("Admin Access")
    
    def check_password():
        if st.session_state["admin_pwd_input"] == ADMIN_PASSWORD:
            st.session_state["authenticated"] = True
            st.success("Admin Access Granted!")
        else:
            st.session_state["authenticated"] = False
            if st.session_state["admin_pwd_input"] != "":
                st.error("Incorrect Password")

    st.text_input(
        "Enter Admin Password", 
        type="password", 
        key="admin_pwd_input", 
        on_change=check_password
    )

    if st.session_state["authenticated"]:
        st.write("✅ **You are currently logged in as Admin.**")
        if st.button("🔄 Sync/Refresh Data", key="syn_admin"):
            st.cache_data.clear()
            st.rerun()
        if st.button("🚪 Logout"):
            st.session_state["authenticated"] = False
            st.rerun()
    else:
        st.info("Enter the password and press Enter to enable editing.")

# Update your tabs line to include the new one
# tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📝 Scorecard", "🏆 Standings", "📅 History", "📜 Info", "⚙️ Admin", "🏆 Bracket"])
        
# --- TAB 6: TOURNAMENT BRACKET (12-Man Re-seeding) ---
with tab6:
    st.header("🏆 12-Man Re-Seeding Tournament")
    st.info("Tournament starts Week 9. Bracket is re-seeded after Round 1 so top seeds play the lowest remaining seeds. Highest Seed refers to the player with the best rank (closest to 1) and the Lowest Seed refers to the player with the worst rank.")
       
    c1, c2, c3, c4 = st.columns(4)
    
    with c1:
        st.subheader("Week 9")
        st.caption("Round 1 (Byes)")
        st.write("🟢 **Seed 1 (BYE)**")
        st.write("🟢 **Seed 2 (BYE)**")
        st.write("🟢 **Seed 3 (BYE)**")
        st.write("🟢 **Seed 4 (BYE)**")
        st.divider()
        st.markdown("**Matchups:**")
        st.write("M1: Seed 5 vs Seed 12")
        st.write("M2: Seed 6 vs Seed 11")
        st.write("M3: Seed 7 vs Seed 10")
        st.write("M4: Seed 8 vs Seed 9")

    with c2:
        st.subheader("Week 10")
        st.caption("Quarter-Finals (Re-seeded)")
        # Logic: Top seeds play the lowest survivors
        st.write("Seed 1 vs Lowest Remaining Seed")
        st.write("Seed 2 vs 2nd Lowest Remaining")
        st.divider()
        st.write("Seed 3 vs 3rd Lowest Remaining")
        st.write("Seed 4 vs Highest Remaining Seed")

    with c3:
        st.subheader("Week 11")
        st.caption("Semi-Finals")
        st.write("Top Bracket Winner")
        st.write("vs")
        st.write("Bottom Bracket Winner")

    with c4:
        st.subheader("Week 12")
        st.caption("CHAMPIONSHIP")
        st.markdown("<h2 style='text-align: center;'>🏆</h2>", unsafe_allow_html=True)
        st.write("Final Match")




























