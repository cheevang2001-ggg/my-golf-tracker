import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import time
import random
import altair as alt

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

# --- Cached connection and optimized I/O helpers ---
@st.cache_resource(ttl=60*60)  # cache the connection for 1 hour
def get_gsheets_conn():
    try:
        return st.connection("gsheets", type=GSheetsConnection)
    except Exception as e:
        st.error("Google Sheets connection failed.")
        raise

MASTER_COLUMNS = [
    'Week', 'Player', 'PIN', 'Pars_Count', 'Birdies_Count', 
    'Eagle_Count', 'Total_Score', 'Handicap', 'Net_Score', 'DNF', 'Acknowledged'
]

GGG_POINTS = {
    1: 100, 2: 77, 3: 64, 4: 54, 5: 47, 6: 41,
    7: 36, 8: 31, 9: 27, 10: 24, 11: 21, 12: 16, 13: 13, 14: 9,
    15: 5, 16: 3, 17: 1 
}

def _empty_master_df():
    return pd.DataFrame(columns=MASTER_COLUMNS)

@st.cache_data(ttl=10)  # cache successful reads for 10 seconds
def _read_sheet_cached():
    conn = get_gsheets_conn()
    data = conn.read()
    if data is None or data.empty or 'Player' not in data.columns:
        return _empty_master_df()
    df = data.dropna(how='all')
    return df[df['Player'] != ""]

def load_data():
    """
    Wrapper around the cached reader that implements retry/backoff and
    keeps a last-successful fallback in session_state to reduce visible failures.
    """
    # Try the cached reader first (fast)
    try:
        df = _read_sheet_cached()
        # store last successful snapshot for fallback
        st.session_state["last_successful_df"] = df.copy()
        return df
    except Exception as e:
        # Retry with exponential backoff for transient errors (e.g., 429)
        backoff = [0.5, 1.0, 2.0]
        for wait in backoff:
            time.sleep(wait)
            try:
                df = _read_sheet_cached()
                st.session_state["last_successful_df"] = df.copy()
                return df
            except Exception:
                continue

        # If all retries fail, return the last successful cached snapshot if available
        if "last_successful_df" in st.session_state:
            st.warning("⚠️ Using last successful cached data due to Sheets API issues.")
            return st.session_state["last_successful_df"]
        # final fallback: empty frame with expected columns
        st.warning("⚠️ Unable to load data from Google Sheets. Showing empty dataset.")
        return _empty_master_df()

def calculate_rolling_handicap(player_df, target_week):
    try:
        # Ensure Total_Score is numeric for reliable math
        if 'Total_Score' in player_df.columns:
            player_df = player_df.copy()
            player_df['Total_Score'] = pd.to_numeric(player_df['Total_Score'], errors='coerce')

        # --- PHASE 1: WEEK 1 STARTING HANDICAP (PRE-SEASON) ---
        if target_week == 1:
            pre_season_rounds = player_df[
                (player_df['Week'] <= 0) &
                (player_df['DNF'] == False) &
                (player_df['Total_Score'].notna()) &
                (player_df['Total_Score'] > 0)
            ].sort_values('Week', ascending=False)

            # Require at least 3 pre-season rounds to establish a Week 1 handicap
            if len(pre_season_rounds) >= 3:
                scores = pre_season_rounds.head(3)['Total_Score'].tolist()
                hcp = round((sum(scores) / len(scores)) - 36, 1)
                return float(hcp)

            # If fewer than 3 pre-season rounds, start at 0.0 per league rule
            return 0.0

        # --- PHASE 2: REGULAR SEASON ROLLING LOGIC ---
        excluded_weeks = [0, 4, 8]

        rounds = player_df[
            (player_df['Week'] > 0) &
            (~player_df['Week'].isin(excluded_weeks)) &
            (player_df['DNF'] == False) &
            (player_df['Week'] < target_week) &
            (player_df['Total_Score'].notna()) &
            (player_df['Total_Score'] > 0)
        ].sort_values('Week', ascending=False)

        # If no regular season rounds played yet, fallback to Week 1 logic (which may return 0.0)
        if rounds.empty:
            return calculate_rolling_handicap(player_df, 1)

        last_scores = rounds.head(4)['Total_Score'].tolist()

        # Standard "Best 3 of last 4" logic
        if len(last_scores) >= 4:
            last_scores.sort()
            hcp = round((sum(last_scores[:3]) / 3) - 36, 1)
        else:
            hcp = round((sum(last_scores) / len(last_scores)) - 36, 1)

        return float(hcp)
    except Exception:
        return 0.0


def save_weekly_data(week, player, pars, birdies, eagles, score_val, hcp_val, pin):
    """
    Efficient save:
    - Read current sheet (fast cached read)
    - Build new entry and only write if it changes the sheet
    - Update in-memory fallback cache after successful write
    """
    # Build new entry
    is_dnf = (score_val == "DNF")
    final_gross = 0 if is_dnf else int(score_val)
    new_entry = pd.DataFrame([{
        'Week': week, 'Player': player, 'Pars_Count': pars, 'Birdies_Count': birdies,
        'Eagle_Count': eagles, 'Total_Score': final_gross, 'Handicap': hcp_val,
        'Net_Score': (final_gross - hcp_val) if not is_dnf else 0, 'DNF': is_dnf, 'PIN': pin
    }])

    # Load existing data (cached)
    existing_data = load_data()

    # Remove any existing row for same player/week and append new entry
    mask = ~((existing_data['Week'] == week) & (existing_data['Player'] == player))
    updated_df = pd.concat([existing_data[mask], new_entry], ignore_index=True)

    # Normalize column order and types for reliable comparison
    updated_df = updated_df.reindex(columns=MASTER_COLUMNS).fillna("")
    existing_norm = existing_data.reindex(columns=MASTER_COLUMNS).fillna("")

    # Only push to Sheets if there is a difference
    try:
        if not existing_norm.reset_index(drop=True).equals(updated_df.reset_index(drop=True)):
            conn = get_gsheets_conn()
            # attempt write with simple retry/backoff
            attempts = 3
            for i in range(attempts):
                try:
                    conn.update(data=updated_df[MASTER_COLUMNS])
                    # update in-memory fallback cache
                    st.session_state["last_successful_df"] = updated_df.copy()
                    break
                except Exception as e:
                    if i < attempts - 1:
                        time.sleep(0.5 * (2 ** i))
                        continue
                    else:
                        st.error(f"Failed to save data after {attempts} attempts: {e}")
                        raise
        else:
            # no-op write avoided
            st.info("No changes detected; skipping Sheets update.")
    finally:
        # Keep UI responsive: clear only the cached read (not the connection)
        try:
            st.cache_data.clear()
        except Exception:
            pass

    # Refresh UI state after save
    st.experimental_rerun()

# --- 3. DATA LOAD ---
df_main = load_data()
EXISTING_PLAYERS = sorted(df_main['Player'].unique().tolist()) if not df_main.empty else []

# --- 4. APP UI ---
st.markdown("<div style='text-align: center;'>", unsafe_allow_html=True)
st.image("GGGOLF-2.png", width=120) 
st.markdown("<h1>GGGolf</h1>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

tabs = st.tabs(["📝 Scorecard", "🏆 Standings", "📅 History", "🏁 Challenges", "ℹ️ League Info", "👤 Registration", "⚙️ Admin"])

with tabs[0]: # Scorecard
    if not EXISTING_PLAYERS: 
        st.warning("No players registered yet.")
    else:
        player_select = st.selectbox("Select Player", EXISTING_PLAYERS)
        
        # Check if the session is still valid (2-hour timeout logic)
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
            # Now p_data is defined safely inside this block
            p_data = df_main[df_main['Player'] == player_select]
            
            # 1. Week Selection
            week_options = list(range(-2, 1)) + list(range(1, 15))
            w_s = st.selectbox(
                "Select Week", 
                week_options, 
                format_func=lambda x: f"Pre-Season Round {abs(x-1)}" if x <= 0 else f"Week {x}",
                key=f"week_selector_{player_select}"
            )

            # 2. Handicap Logic
            if w_s <= 0:
                current_hcp = 0.0
                st.info("🛠️ Pre-Season: Logging rounds to establish your Week 1 handicap.")
            elif w_s in [4, 8]:
                current_hcp = 0.0
                st.info("💡 GGG Event: No handicap applied for this round.")
            else:
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

    st.info(
        "Challenges will be announced here during the season. "
        "Each challenge includes a short description, cost (if any), eligibility rules, and how to participate."
    )

    col_main, col_side = st.columns([3, 1])

    # Main column: Current Challenge card
    with col_main:
        st.subheader("Current Challenge")
        # Example challenge card — update text as needed when a challenge is active
        st.markdown("#### Season Ball Challenge")
        st.markdown("**Entry:** $20 for a GGG sleeve of balls")
        st.markdown("**Overview:** Use the GGG sleeve during league play. Return at least one ball from the sleeve at the season finale to qualify for the top prize.")
        st.divider()

        st.markdown("**How it works**")
        st.markdown(
            "1. Purchase a GGG sleeve for $20 to join the challenge.\n"
            "2. Use the GGG balls during regular league and event play. If you lose all balls, you may REBUY (see timeline below).\n"
            "3. At the season finale, return at least one ball from your sleeve to qualify for the top prize (or $100 cash option)."
        )

        st.divider()
        st.markdown("**Eligibility and Rebuy Options**")
        # Compact eligibility table for quick scanning
        import pandas as _pd
        elig = _pd.DataFrame([
            {"Option": "Original Purchase", "Entry Deadline": "Before Week 1", "Prize Eligibility": "Top prize or $100"},
            {"Option": "REBUY 1", "Entry Deadline": "Before Week 3", "Prize Eligibility": "2nd prize pick or $50"},
            {"Option": "REBUY 2", "Entry Deadline": "Before Week 7", "Prize Eligibility": "4th prize pick or $20"},
            {"Option": "REBUY 3", "Entry Deadline": "Before Week 11", "Prize Eligibility": "6th prize pick"}
        ])
        st.table(elig)

        st.divider()
        # CTA (disabled placeholder until admin enables)
        st.write("**Participation**")
        st.button("Join Season Ball Challenge", disabled=True)
        st.caption("Admin will enable signups and payment links when the challenge is active.")

        with st.expander("Full Rules and Examples", expanded=False):
            st.markdown(
                "**Key Rules**\n\n"
                "- Purchasing the sleeve registers you for the challenge under the corresponding entry deadline.\n"
                "- If you purchase a REBUY, you are only eligible for the prize tier associated with that REBUY (you forfeit eligibility for earlier tiers).\n"
                "- Balls lost during play may be rebought using the REBUY options above; each REBUY has its own deadline.\n"
                "- To claim a prize at the finale you must return at least one ball from the sleeve you purchased.\n\n"
                "**Examples**\n\n"
                "- If you buy before Week 1 and return a ball at the finale, you qualify for the top prize or $100 cash.\n"
                "- If you buy as REBUY 1 (before Week 3), you are not eligible for the top prize but can claim the REBUY 1 prize (2nd pick or $50).\n"
            )

    # Side column: quick admin actions and notes
    with col_side:
        st.subheader("Quick Actions")
        st.write("Admin controls will appear here when implemented.")
        st.button("Request Challenge Edit Access", disabled=True)
        st.divider()
        st.markdown("**Notes for Players**")
        st.markdown(
            "- Keep your sleeve balls separate so returned balls can be verified.\n"
            "- Questions about eligibility should be directed to the Rules and Players Committee."
        )


with tabs[4]: # League Info
    st.header("ℹ️ League Information")
    # --- Info / Category selector and content blocks (replace existing section) ---
info_category = st.radio(
    "Select a Category:",
    ["About Us", "Handicaps", "Rules", "Schedule", "Prizes", "Expenses", "Members"],
    horizontal=True,
)

st.divider()

# --- About Us ---
if info_category == "About Us":
    st.subheader("GGGolf Summer League 2026")
    st.write(
        "Formed in 2022, GGGOLF league promotes camaraderie through friendly golf competition and welcomes all skill levels."
    )
    st.divider()
    st.subheader("League Officers")
    st.markdown("* **President**: Txoovnom Vang\n* **Vice President**: Cory Vue\n* **Finance**: Mike Yang")

# --- Handicaps ---
elif info_category == "Handicaps":
    st.subheader("Establishing Your Handicap")
    st.info(
        "Pre-season rounds establish Week 1 handicap. If fewer than 3 pre-season rounds, Week 1 handicap defaults to 0.0."
    )

# --- Rules (placeholder) ---
elif info_category == "Rules":
    st.subheader("League Rules")
    st.write("Rules and policies will be posted here.")

# --- Schedule (placeholder) ---
elif info_category == "Schedule":
    st.subheader("Season Schedule")
    st.write("Schedule will be posted here.")

# --- Prizes (placeholder) ---
elif info_category == "Prizes":
    st.subheader("Prizes")
    st.write("Prize structure and details will be posted here.")

# --- Expenses (full block) ---
elif info_category == "Expenses":
    st.subheader("💵 League Expenses")
    st.write("Breakdown of league fees and administrative costs.")

    # Initialize session state safely
    if "expenses_table" not in st.session_state:
        st.session_state["expenses_table"] = []  # list of dicts: {"Prize": str, "Cost": float}
    if "expenses_edit_unlocked" not in st.session_state:
        st.session_state["expenses_edit_unlocked"] = False

    # Read-only view
    st.markdown("**Current Prize / Expense List (read-only)**")
    if not st.session_state["expenses_table"]:
        st.info("No prize expenses recorded yet.")
    else:
        expenses_df = pd.DataFrame(st.session_state["expenses_table"])
        expenses_df_display = expenses_df.copy()
        expenses_df_display["Cost"] = expenses_df_display["Cost"].map(lambda x: f"${x:,.2f}")
        st.dataframe(expenses_df_display.reset_index(drop=True), use_container_width=True, hide_index=True)
        total_cost = expenses_df["Cost"].sum()
        st.markdown(f"**Total Estimated Cost:** **${total_cost:,.2f}**")

    st.divider()

    # Edit controls (restricted)
    st.markdown("**Edit Controls (restricted)**")
    if st.session_state["expenses_edit_unlocked"]:
        st.success("Editing unlocked. You may add or remove expense items.")

        # Lock editing (simple button)
        if st.button("🔒 Lock Editing"):
            st.session_state["expenses_edit_unlocked"] = False
            try:
                st.experimental_rerun()
            except Exception:
                st.warning("Editing locked. Please refresh the page if the UI does not update automatically.")

        # Add new expense entry
        with st.expander("Add a Prize / Expense", expanded=True):
            with st.form("add_expense_form", clear_on_submit=True):
                prize_desc = st.text_input("Prize Description", placeholder="e.g., Season Trophy, Gift Cards")
                prize_cost = st.number_input("Cost (USD)", min_value=0.0, step=1.0, format="%.2f")
                add_sub = st.form_submit_button("Add Expense")
                if add_sub:
                    if not prize_desc:
                        st.warning("Please enter a prize description.")
                    else:
                        st.session_state["expenses_table"].append({"Prize": prize_desc.strip(), "Cost": float(prize_cost)})
                        st.success(f"Added: {prize_desc} — ${prize_cost:,.2f}")
                        try:
                            st.cache_data.clear()
                        except Exception:
                            pass
                        try:
                            st.experimental_rerun()
                        except Exception:
                            st.info("Added. Please refresh the page if the UI does not update automatically.")

        st.divider()

        # Manage / remove items
        if st.session_state["expenses_table"]:
            with st.expander("Manage Expenses (Remove an item)", expanded=False):
                remove_options = [
                    f"{i+1}. {r['Prize']} — ${r['Cost']:,.2f}" for i, r in enumerate(st.session_state["expenses_table"])
                ]
                to_remove = st.selectbox("Select an item to remove", ["None"] + remove_options, index=0)

                # Confirm removal via form
                with st.form("remove_expense_form"):
                    st.write("Selected item to remove:")
                    st.write(to_remove if to_remove != "None" else "No item selected")
                    confirm_remove = st.form_submit_button("Remove Selected Item")
                if confirm_remove:
                    if to_remove == "None":
                        st.warning("No item selected. Please choose an expense to remove.")
                    else:
                        idx = remove_options.index(to_remove)
                        removed = st.session_state["expenses_table"].pop(idx)
                        st.success(f"Removed: {removed['Prize']} — ${removed['Cost']:,.2f}")
                        try:
                            st.cache_data.clear()
                        except Exception:
                            pass
                        try:
                            st.experimental_rerun()
                        except Exception:
                            st.info("Removal complete. Please refresh the page if the UI does not update automatically.")
    else:
        # Unlock form
        with st.expander("Request Edit Access (requires code)", expanded=False):
            with st.form("unlock_expenses_form"):
                unlock_code = st.text_input("Enter Edit Code", type="password", placeholder="Enter admin code to unlock editing")
                submit_unlock = st.form_submit_button("Unlock Editing")
                if submit_unlock:
                    if unlock_code and unlock_code == ADMIN_PASSWORD:
                        st.session_state["expenses_edit_unlocked"] = True
                        st.success("Edit access granted.")
                        time.sleep(0.5)
                        try:
                            st.experimental_rerun()
                        except Exception:
                            st.warning("Edit access granted. Please refresh the page if the UI does not update automatically.")
                    else:
                        st.error("❌ Incorrect code. Editing remains locked.")

        st.info("Editing is restricted. Members can view expenses above. To add or remove items, request edit access and provide the edit code.")

# --- Members (full block) ---
elif info_category == "Members":
    st.subheader("GGG League Members")
    st.write("Welcome back, GGGOLF Members! We’re celebrating our fourth year thanks to all of you. Get out there, have a great time, and enjoy the battle!")

    # Build members list from df_main: registration rows are Week == 0
    if 'df_main' not in globals() or df_main is None or df_main.empty:
        st.info("No registered members yet.")
    else:
        members_df = df_main[df_main['Week'] == 0].copy()
        if members_df.empty:
            st.info("No registered members yet.")
        else:
            # Normalize columns for display
            display_cols = ['Player']
            if 'Acknowledged' in members_df.columns:
                try:
                    members_df['Acknowledged'] = members_df['Acknowledged'].astype(bool)
                    display_cols.append('Acknowledged')
                except Exception:
                    members_df['Acknowledged'] = members_df.get('Acknowledged', pd.Series([False] * len(members_df)))
                    display_cols.append('Acknowledged')

            members_df = members_df.loc[:, display_cols].drop_duplicates().sort_values('Player').reset_index(drop=True)
            st.markdown(f"**Total Members:** {len(members_df)}")
            st.dataframe(members_df, use_container_width=True, hide_index=True)


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
                        conn = get_gsheets_conn()
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
    
    # --- STEP 1: Secure LOGIN Form ---
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
        st.warning("⚠️ Warning: Resetting")
