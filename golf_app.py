# golf_app_full_integrated.py
# Integrated and fixed Streamlit app for GGGolf League 2026
# - Restored About Us, Handicaps, Rules, Schedule, Prizes, Members content
# - Removed top-level destructive writes
# - Fixed Expenses and Members sections and removed unsupported Streamlit kwargs
# - Defensive reads from Google Sheets and robust UI behavior

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
SESSION_TIMEOUT = 2 * 60 * 60  # 2 hours in seconds

# Session defaults
if "api_cooling_until" not in st.session_state:
    st.session_state["api_cooling_until"] = 0
if "unlocked_player" not in st.session_state:
    st.session_state["unlocked_player"] = None
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "login_timestamp" not in st.session_state:
    st.session_state["login_timestamp"] = 0
if "reg_access" not in st.session_state:
    st.session_state["reg_access"] = False
if "needs_refresh" not in st.session_state:
    st.session_state["needs_refresh"] = False

# --- Cached connection and optimized I/O helpers ---
@st.cache_resource(ttl=60 * 60)
def get_gsheets_conn():
    try:
        return st.connection("gsheets", type=GSheetsConnection)
    except Exception:
        # Let callers handle the exception and show friendly UI messages
        raise

MASTER_COLUMNS = [
    "Week",
    "Player",
    "PIN",
    "Pars_Count",
    "Birdies_Count",
    "Eagle_Count",
    "Total_Score",
    "Handicap",
    "Net_Score",
    "DNF",
    "Acknowledged",
]

GGG_POINTS = {
    1: 100,
    2: 77,
    3: 64,
    4: 54,
    5: 47,
    6: 41,
    7: 36,
    8: 31,
    9: 27,
    10: 24,
    11: 21,
    12: 16,
    13: 13,
    14: 9,
    15: 5,
    16: 3,
    17: 1,
}

def _empty_master_df():
    df = pd.DataFrame(columns=MASTER_COLUMNS)
    # set safe dtypes
    numeric_cols = [
        "Week",
        "Pars_Count",
        "Birdies_Count",
        "Eagle_Count",
        "Total_Score",
        "Handicap",
        "Net_Score",
    ]
    for c in numeric_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in ["DNF", "Acknowledged"]:
        if c in df.columns:
            df[c] = df[c].astype("boolean")
    return df

@st.cache_data(ttl=10)
def _read_sheet_cached():
    conn = get_gsheets_conn()
    data = conn.read()
    if data is None or data.empty or "Player" not in data.columns:
        return _empty_master_df()
    df = data.copy()
    # Ensure canonical columns exist
    for c in MASTER_COLUMNS:
        if c not in df.columns:
            df[c] = pd.NA
    df = df[MASTER_COLUMNS]
    # Coerce numeric columns
    numeric_cols = [
        "Week",
        "Pars_Count",
        "Birdies_Count",
        "Eagle_Count",
        "Total_Score",
        "Handicap",
        "Net_Score",
    ]
    for c in numeric_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    # Coerce boolean columns where possible
    for c in ["DNF", "Acknowledged"]:
        if c in df.columns:
            try:
                df[c] = df[c].astype("boolean")
            except Exception:
                pass
    return df

def load_data():
    try:
        df = _read_sheet_cached()
        # store a small preview for fallback
        st.session_state["last_successful_head"] = df.head(50)
        return df
    except Exception:
        backoff = [0.5, 1.0, 2.0]
        for wait in backoff:
            time.sleep(wait)
            try:
                df = _read_sheet_cached()
                st.session_state["last_successful_head"] = df.head(50)
                return df
            except Exception:
                continue
        try:
            st.warning("⚠️ Unable to load data from Google Sheets. Showing empty dataset.")
        except Exception:
            pass
        return _empty_master_df()

def calculate_rolling_handicap(player_df, target_week):
    try:
        if "Total_Score" in player_df.columns:
            player_df = player_df.copy()
            player_df["Total_Score"] = pd.to_numeric(player_df["Total_Score"], errors="coerce")

        if target_week == 1:
            pre_season_rounds = player_df[
                (player_df["Week"] <= 0)
                & (player_df["DNF"] == False)
                & (player_df["Total_Score"].notna())
                & (player_df["Total_Score"] > 0)
            ].sort_values("Week", ascending=False)
            if len(pre_season_rounds) >= 3:
                scores = pre_season_rounds.head(3)["Total_Score"].tolist()
                hcp = round((sum(scores) / len(scores)) - 36, 1)
                return float(hcp)
            return 0.0

        excluded_weeks = [0, 4, 8]
        rounds = player_df[
            (player_df["Week"] > 0)
            & (~player_df["Week"].isin(excluded_weeks))
            & (player_df["DNF"] == False)
            & (player_df["Week"] < target_week)
            & (player_df["Total_Score"].notna())
            & (player_df["Total_Score"] > 0)
        ].sort_values("Week", ascending=False)

        if rounds.empty:
            return calculate_rolling_handicap(player_df, 1)

        last_scores = rounds.head(4)["Total_Score"].tolist()
        if len(last_scores) >= 4:
            last_scores.sort()
            hcp = round((sum(last_scores[:3]) / 3) - 36, 1)
        else:
            hcp = round((sum(last_scores) / len(last_scores)) - 36, 1)
        return float(hcp)
    except Exception:
        return 0.0

def save_weekly_data(week, player, pars, birdies, eagles, score_val, hcp_val, pin):
    is_dnf = (score_val == "DNF")
    final_gross = 0 if is_dnf else int(score_val)
    new_entry = pd.DataFrame(
        [
            {
                "Week": week,
                "Player": player,
                "Pars_Count": pars,
                "Birdies_Count": birdies,
                "Eagle_Count": eagles,
                "Total_Score": final_gross,
                "Handicap": hcp_val,
                "Net_Score": (final_gross - hcp_val) if not is_dnf else 0,
                "DNF": is_dnf,
                "PIN": pin,
                "Acknowledged": False,
            }
        ]
    )

    existing_data = load_data()
    mask = ~((existing_data["Week"] == week) & (existing_data["Player"] == player))
    updated_df = pd.concat([existing_data[mask], new_entry], ignore_index=True)
    updated_df = updated_df.reindex(columns=MASTER_COLUMNS).fillna("")
    existing_norm = existing_data.reindex(columns=MASTER_COLUMNS).fillna("")

    try:
        if not existing_norm.reset_index(drop=True).equals(updated_df.reset_index(drop=True)):
            conn = get_gsheets_conn()
            attempts = 3
            for i in range(attempts):
                try:
                    conn.update(data=updated_df[MASTER_COLUMNS])
                    st.session_state["last_successful_head"] = updated_df.head(50)
                    break
                except Exception as e:
                    if i < attempts - 1:
                        time.sleep(0.5 * (2 ** i))
                        continue
                    else:
                        st.error(f"Failed to save data after {attempts} attempts: {e}")
                        raise
        else:
            st.info("No changes detected; skipping Sheets update.")
    finally:
        try:
            st.cache_data.clear()
        except Exception:
            pass

    st.session_state["needs_refresh"] = True
    try:
        st.experimental_rerun()
    except Exception:
        st.info("Save complete. Please refresh the page if the UI does not update automatically.")

# --- 3. DATA LOAD ---
df_main = load_data()
EXISTING_PLAYERS = sorted(df_main["Player"].dropna().unique().tolist()) if not df_main.empty else []

# --- 4. APP UI ---
st.markdown("<div style='text-align: center;'>", unsafe_allow_html=True)
st.image("GGGOLF-2.png", width=120)
st.markdown("<h1>GGGOLF LEAGUE 2026</h1>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

tabs = st.tabs(
    [
        "📝 Scorecard",
        "🏆 Standings",
        "📅 History",
        "🏁 Challenges",
        "ℹ️ League Info",
        "👤 Registration",
        "⚙️ Admin",
    ]
)

# -------------------------
# Tab 0: Scorecard
# -------------------------
with tabs[0]:
    if not EXISTING_PLAYERS:
        st.warning("No players registered yet.")
    else:
        player_select = st.selectbox("Select Player", EXISTING_PLAYERS)

        is_unlocked = (
            (st.session_state.get("unlocked_player") == player_select)
            and (time.time() - st.session_state.get("login_timestamp", 0) < SESSION_TIMEOUT)
        ) or st.session_state.get("authenticated", False)

        if not is_unlocked:
            st.markdown("### 🔒 Player Verification")
            st.info(f"Please enter your 4-digit PIN to unlock the scorecard for **{player_select}**.")

            with st.form("unlock_form"):
                user_pin = st.text_input("Enter PIN", type="password", key=f"pin_input_{player_select}")
                submit_unlock = st.form_submit_button("🔓 Unlock Scorecard")
                if submit_unlock:
                    if user_pin:
                        p_info = df_main[df_main["Player"] == player_select]
                        reg_row = p_info[p_info["Week"] == 0]
                        if not reg_row.empty:
                            stored_pin = str(reg_row["PIN"].iloc[0]).split(".")[0].strip()
                            if user_pin.strip() == stored_pin:
                                st.session_state.update(
                                    {"unlocked_player": player_select, "login_timestamp": time.time()}
                                )
                                st.success("Identity Verified!")
                                time.sleep(0.5)
                                try:
                                    st.experimental_rerun()
                                except Exception:
                                    st.info("Unlocked. Please refresh if the UI does not update automatically.")
                            else:
                                st.error("❌ Incorrect PIN.")
                        else:
                            st.error("⚠️ Player not found in registration records.")
                    else:
                        st.warning("Please enter your PIN.")
        else:
            p_data = df_main[df_main["Player"] == player_select]

            week_options = list(range(-2, 1)) + list(range(1, 15))
            w_s = st.selectbox(
                "Select Week",
                week_options,
                format_func=lambda x: f"Pre-Season Round {abs(x-1)}" if x <= 0 else f"Week {x}",
                key=f"week_selector_{player_select}",
            )

            if w_s <= 0:
                current_hcp = 0.0
                st.info("🛠️ Pre-Season: Logging rounds to establish your Week 1 handicap.")
            elif w_s in [4, 8]:
                current_hcp = 0.0
                st.info("💡 GGG Event: No handicap applied for this round.")
            else:
                current_hcp = calculate_rolling_handicap(p_data, w_s)

            h_disp = f"+{abs(current_hcp)}" if current_hcp < 0 else f"{current_hcp}"
            played_rounds = p_data[(p_data["Week"] > 0) & (p_data["DNF"] == False)].sort_values("Week")

            st.markdown(f"### 📊 {player_select}'s Season Dashboard")
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Current HCP", h_disp)
            m2.metric("Avg Net", f"{played_rounds['Net_Score'].mean():.1f}" if not played_rounds.empty else "N/A")
            m3.metric("Total Pars", int(played_rounds["Pars_Count"].sum()) if not played_rounds.empty else 0)
            m4.metric("Total Birdies", int(played_rounds["Birdies_Count"].sum()) if not played_rounds.empty else 0)
            m5.metric("Total Eagles", int(played_rounds["Eagle_Count"].sum()) if not played_rounds.empty else 0)

            if not played_rounds.empty:
                chart = (
                    alt.Chart(played_rounds)
                    .mark_line(color="#2e7d32", strokeWidth=3)
                    .encode(x=alt.X("Week:O"), y=alt.Y("Net_Score:Q", scale=alt.Scale(reverse=True, zero=False)))
                    + alt.Chart(played_rounds)
                    .mark_point(color="#2e7d32", size=100, filled=True)
                    .encode(x="Week:O", y="Net_Score:Q")
                )
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

                if st.form_submit_button("Confirm & Submit Score"):
                    reg_row = p_data[p_data["Week"] == 0]
                    if not reg_row.empty:
                        pin = str(reg_row["PIN"].iloc[0]).split(".")[0].strip()
                    else:
                        pin = ""
                    save_weekly_data(w_s, player_select, p_c, b_c, e_c, s_v, h_r, pin)
                    st.success("Score Saved!")
                    time.sleep(1)
                    try:
                        st.experimental_rerun()
                    except Exception:
                        st.info("Saved. Please refresh if the UI does not update automatically.")

# -------------------------
# Tab 1: Standings
# -------------------------
with tabs[1]:
    st.subheader("🏆 Standings")
    if not df_main.empty:
        v = df_main[(df_main["Week"] > 0) & (df_main["DNF"] == False)].copy()
        if not v.empty:
            v["Pts"] = 0.0
            for w in v["Week"].unique():
                m = v["Week"] == w
                v.loc[m, "R"] = v.loc[m, "Net_Score"].rank(method="min")
                for idx, row in v[m].iterrows():
                    base_pts = GGG_POINTS.get(int(row["R"]), 10.0)
                    final_pts = base_pts * 2 if w == 12 else base_pts
                    v.at[idx, "Pts"] = final_pts
            res = (
                v.groupby("Player")
                .agg({"Pts": "sum", "Net_Score": "mean"})
                .reset_index()
                .rename(columns={"Pts": "Total Pts", "Net_Score": "Avg Net"})
            )
            res["Avg Net"] = res["Avg Net"].round(1)
            st.dataframe(res.sort_values(["Total Pts", "Avg Net"], ascending=[False, True]), use_container_width=True, hide_index=True)

# -------------------------
# Tab 2: History
# -------------------------
with tabs[2]:
    st.subheader("📅 Weekly Scores & GGG Points")
    h_df = df_main[(df_main["Week"] > 0) & (df_main["DNF"] == False)].copy()
    if not h_df.empty:
        h_df["Points"] = 0.0
        for w in h_df["Week"].unique():
            mask = h_df["Week"] == w
            h_df.loc[mask, "Rank"] = h_df.loc[mask, "Net_Score"].rank(method="min")
            for idx, row in h_df[mask].iterrows():
                base_pts = GGG_POINTS.get(int(row["Rank"]), 10.0)
                h_df.at[idx, "Points"] = base_pts * 2 if w == 12 else base_pts

        f_col1, f_col2 = st.columns(2)
        all_players = ["All Players"] + sorted(h_df["Player"].unique().tolist())
        sel_player = f_col1.selectbox("Filter by Player", all_players)
        all_weeks = ["All Weeks"] + sorted(h_df["Week"].unique().tolist())
        sel_week = f_col2.selectbox("Filter by Week", all_weeks)

        filtered_df = h_df.copy()
        if sel_player != "All Players":
            filtered_df = filtered_df[filtered_df["Player"] == sel_player]
        if sel_week != "All Weeks":
            filtered_df = filtered_df[filtered_df["Week"] == sel_week]

        display_df = filtered_df[["Week", "Player", "Total_Score", "Handicap", "Net_Score", "Points"]].copy()
        display_df = display_df.sort_values(["Week", "Points"], ascending=[False, False])

        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Points": st.column_config.NumberColumn("GGG Points", format="%d pts"),
                "Week": st.column_config.NumberColumn("Week", format="Wk %d"),
            },
        )
    else:
        st.info("No completed rounds recorded yet.")

# -------------------------
# Tab 3: GGG Challenge
# -------------------------
with tabs[3]:
    st.header("🏁 GGG Challenge")
    st.write("Seasonal challenges and reward opportunities for GGGolf members.")
    st.divider()

    st.info(
        "Challenges will be announced here during the season. "
        "Each challenge includes a short description, cost (if any), eligibility rules, and how to participate."
    )

    col_main, col_side = st.columns([3, 1])

    with col_main:
        st.subheader("Current Challenge")
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
        elig = pd.DataFrame(
            [
                {"Option": "Original Purchase", "Entry Deadline": "Before Week 1", "Prize Eligibility": "Top prize or $100"},
                {"Option": "REBUY 1", "Entry Deadline": "Before Week 3", "Prize Eligibility": "2nd prize pick or $50"},
                {"Option": "REBUY 2", "Entry Deadline": "Before Week 7", "Prize Eligibility": "4th prize pick or $20"},
                {"Option": "REBUY 3", "Entry Deadline": "Before Week 11", "Prize Eligibility": "6th prize pick"},
            ]
        )
        st.table(elig)

        st.divider()
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

# -------------------------
# Tab 4: League Info (About Us, Handicaps, Rules, Schedule, Prizes, Expenses, Members)
# -------------------------
with tabs[4]:
    st.header("ℹ️ League Information")
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
            "Formed in 2022, GGGOLF league promotes camaraderie through friendly golf competition and welcomes all skill levels. Members gain experience to prepare for community tournaments and events, while maintaining high standards of integrity in the game."
        )
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("League Officers")
            st.markdown("* **President**: Txoovnom Vang\n* **Vice President**: Cory Vue\n* **Finance**: Mike Yang")
            st.markdown(
                """
                **Executive Team:** The Officers hold primary responsibility for the league’s operational backbone. 
                Their focus is on **growth, financial oversight, and external promotion.** They ensure the league’s sustainability by managing the essential logistics that allow GGGolf to function as a professional-grade organization.
                """
            )
        with col2:
            st.subheader("Committees")
            st.markdown("* **Rules and Players Committee**: Lex Vue, Long Lee, Deng Kue\n")
            st.markdown(
                """
                **Player Advocacy:** This Committee serves as the formal link between the membership and leadership. 
                They are tasked with **maintaining competitive integrity, hearing member grievances, and vetting player-driven initiatives.** Their role ensures that the evolution of the league is always informed by the needs of the players.
                """
            )

        st.divider()
        with st.expander("GGGolf Organizational Protocol", expanded=False):
            st.markdown(
                """
                To ensure the effective administration of GGGolf, we operate under a dual-branch governance model:
                
                1. **Administrative Authority:** All final decisions regarding league expansion, financial allocations, and external partnerships reside with the **League Officers**.
                2. **Consultative Feedback:** Players seeking to implement change or address concerns must follow the established chain of command by bringing matters to the **Players Committee**. The Committee evaluates these proposals before presenting them to the Officers for executive review.
                
                This professional hierarchy is established to protect the integrity of the league and ensure that the voice of the player is represented within a disciplined administrative framework.
                """
            )
        st.divider()
        st.subheader("Code of Conduct")
        st.markdown(
            """
            * Practice common golfing etiquette and rules.
            * Integrity: Respect yourself, fellow league members, and others outside the league on the golf course.
            * Arrive promptly and timely.
            * Communicate clearly about schedules and issues.
            * Comply with all policies and guidelines.
            * Follow the structural chain
            """
        )

    # --- Handicaps ---
    elif info_category == "Handicaps":
        st.subheader("Establishing Your Handicap")
        st.info(
            """
            **Pre-Season Requirement:**
            To have an accurate handicap for Week 1, players are encouraged to log 3 Pre-Season rounds. Play with one or more 2026 GGG member and play from the Tee Box you feel is fair per your skill level.
            You may play at any course on the 2026 GGG Schedule, once you've logged a pre-season round it will be locked in for calculation for Week 1.
            
            * **Option A:** Complete 3 rounds before May 31. Your Week 1 handicap will be the average of these three pre-season scores.
            * **Option B:** If you do not complete 3 rounds, you will start Week 1 with a 0.0 handicap (or your current average) as per standard rolling math.
            """
        )

        st.divider()
        st.subheader("Handicap Calculation Transparency")
        st.write(
            "Rolling average of the best 3 of the last 4 rounds to a par 36. "
            "Use the tool below to inspect how a player's handicap is derived. "
            "This shows pre-season rounds, the last eligible rounds used, and the exact math (best 3 of last 4 to par 36)."
        )

        if "df_main" not in globals() or df_main is None or df_main.empty:
            st.warning("No player data available to show handicap breakdown.")
        else:
            try:
                reg_players = df_main[df_main["Week"] == 0]["Player"].dropna().unique().tolist()
                all_players = sorted(df_main["Player"].dropna().unique().tolist())
                player_options = reg_players if reg_players else all_players
            except Exception:
                player_options = sorted(df_main["Player"].dropna().unique().tolist())

            if not player_options:
                st.info("No registered players found.")
            else:
                sel_player = st.selectbox("Select Player to Inspect", player_options, key="handicap_transparency_player")
                sel_week = st.selectbox("Target Week (handicap to apply for)", list(range(1, 15)), index=0, key="handicap_transparency_week")

                p_df = df_main[df_main["Player"] == sel_player].copy()
                if p_df.empty:
                    st.warning("No recorded rounds for this player.")
                else:
                    pre_season = p_df[(p_df["Week"] <= 0) & (p_df["DNF"] == False) & (p_df["Total_Score"] > 0)].sort_values("Week", ascending=False)
                    excluded_weeks = [0, 4, 8]
                    regular_rounds = p_df[
                        (p_df["Week"] > 0)
                        & (~p_df["Week"].isin(excluded_weeks))
                        & (p_df["DNF"] == False)
                        & (p_df["Week"] < sel_week)
                    ].sort_values("Week", ascending=False)

                    with st.expander("View Rounds Used In Calculation", expanded=True):
                        st.markdown("**Pre-Season Rounds (Week <= 0)**")
                        if pre_season.empty:
                            st.write("No pre-season rounds recorded.")
                        else:
                            st.dataframe(pre_season[["Week", "Total_Score", "DNF"]].reset_index(drop=True), use_container_width=True, hide_index=True)

                        st.markdown("**Eligible Regular Rounds (excluding Weeks 0, 4, 8)**")
                        if regular_rounds.empty:
                            st.write("No eligible regular rounds recorded prior to the selected target week.")
                        else:
                            st.dataframe(regular_rounds[["Week", "Total_Score", "DNF"]].reset_index(drop=True), use_container_width=True, hide_index=True)

                    try:
                        if sel_week == 1:
                            if not pre_season.empty:
                                scores = pre_season.head(3)["Total_Score"].tolist()
                                used_scores = scores[:3]
                                avg_score = sum(used_scores) / len(used_scores)
                                hcp_val = round(avg_score - 36, 1)
                                st.write(f"Week 1 handicap (example): {hcp_val} — method: average of up to 3 pre-season rounds")
                            else:
                                st.write("Week 1 handicap: 0.0 (insufficient pre-season rounds)")
                        else:
                            st.write("Calculated handicap (preview):", calculate_rolling_handicap(p_df, sel_week))
                    except Exception:
                        st.write("Unable to compute handicap preview for this player.")

    # --- Rules ---
    elif info_category == "Rules":
        st.subheader("League Rules")
        st.markdown(
            """
            **Core Rules and Expectations**
            - Play honestly and record scores accurately.
            - Respect tee times and communicate scheduling changes promptly.
            - Follow local course rules and standard golf etiquette.
            - Report DNF (Did Not Finish) when applicable; DNF rounds are excluded from handicap calculations.
            - Event weeks (e.g., Weeks 4 and 8) may have special scoring rules; check event announcements.
            """
        )

    # --- Schedule ---
    elif info_category == "Schedule":
        st.subheader("Season Schedule")
        st.markdown(
            """
            **2026 Season (example schedule)**
            - Pre-Season rounds: Weeks -2, -1, 0 (used to establish Week 1 handicaps)
            - Regular season: Weeks 1–14 (with special event weeks at Week 4 and Week 8)
            - Finale and awards: Week 15 (season finale)
            """
        )
        st.divider()
        st.markdown("**Important Dates**")
        st.write("- Registration deadline: Before Week 1")
        st.write("- Rebuy deadlines: Before Weeks 3, 7, 11")
        st.write("- Season finale and awards: Week 15")

    # --- Prizes ---
    elif info_category == "Prizes":
        st.subheader("Prizes and Payouts")
        st.markdown(
            """
            **Prize Structure**
            - Top season points winners receive prize selections or cash options.
            - Event winners (special weeks) may receive bonus prizes.
            - GGG Challenge prizes are separate and announced per challenge.
            """
        )
        st.divider()
        st.markdown("**Expenses and Funding**")
        st.write("League funds come from membership dues and challenge entries. Expenses include trophies, awards, and administrative costs.")

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

    # --- Members ---
    elif info_category == "Members":
        st.subheader("GGG League Members")
        st.write("Welcome back, GGGOLF Members! We’re celebrating our fourth year thanks to all of you. Get out there, have a great time, and enjoy the battle!")

        # Build members list from df_main: registration rows are Week == 0
        if "df_main" not in globals() or df_main is None or df_main.empty:
            st.info("No registered members yet.")
        else:
            members_df = df_main[df_main["Week"] == 0].copy()
            if members_df.empty:
                st.info("No registered members yet.")
            else:
                display_cols = ["Player"]
                if "Acknowledged" in members_df.columns:
                    try:
                        members_df["Acknowledged"] = members_df["Acknowledged"].astype(bool)
                        display_cols.append("Acknowledged")
                    except Exception:
                        members_df["Acknowledged"] = members_df.get("Acknowledged", pd.Series([False] * len(members_df)))
                        display_cols.append("Acknowledged")

                members_df = members_df.loc[:, display_cols].drop_duplicates().sort_values("Player").reset_index(drop=True)
                st.markdown(f"**Total Members:** {len(members_df)}")
                st.dataframe(members_df, use_container_width=True, hide_index=True)

# -------------------------
# Tab 5: Registration (placeholder)
# -------------------------
with tabs[5]:
    st.header("👤 Registration")
    st.info("Registration UI goes here. Use the registration form to add new players.")
    with st.expander("Register a Test Player (Admin only)", expanded=False):
        if st.session_state.get("authenticated"):
            with st.form("test_register_form"):
                t_name = st.text_input("Player Name")
                t_pin = st.text_input("PIN (4 digits)")
                submit_test = st.form_submit_button("Register Test Player")
                if submit_test:
                    if not t_name or not t_pin:
                        st.warning("Provide both name and PIN.")
                    else:
                        try:
                            conn = get_gsheets_conn()
                            reg_row = pd.DataFrame([{"Week": 0, "Player": t_name, "PIN": t_pin, "DNF": False, "Acknowledged": False}])
                            current = load_data()
                            updated = pd.concat([current, reg_row], ignore_index=True)
                            updated = updated.reindex(columns=MASTER_COLUMNS).fillna("")
                            conn.update(data=updated[MASTER_COLUMNS])
                            st.success(f"Registered test player: {t_name}")
                            try:
                                st.cache_data.clear()
                            except Exception:
                                pass
                            try:
                                st.experimental_rerun()
                            except Exception:
                                st.info("Registered. Please refresh if the UI does not update automatically.")
                        except Exception as e:
                            st.error(f"Failed to register test player: {e}")
        else:
            st.info("Authenticate as admin to register test players here.")

# -------------------------
# Tab 6: Admin
# -------------------------
with tabs[6]:
    st.header("⚙️ Admin Control Panel")

    if not st.session_state.get("authenticated"):
        st.info("Please enter the Administrative Password to access league management tools.")
        with st.form("admin_login_form"):
            admin_input = st.text_input("Admin Password", type="password", key="admin_password_field")
            submit_admin = st.form_submit_button("🔓 Verify Admin")
            if submit_admin:
                if admin_input == ADMIN_PASSWORD:
                    st.session_state["authenticated"] = True
                    st.success("Access Granted!")
                    time.sleep(0.5)
                    try:
                        st.experimental_rerun()
                    except Exception:
                        st.info("Access granted. Please refresh if the UI does not update automatically.")
                else:
                    st.error("❌ Incorrect Admin Password.")
    else:
        st.subheader("Admin Tools")
        st.info("Admin tools can modify league data. Use caution when performing resets or bulk updates.")

        st.markdown("### One-Click Sheet Reset (Admin Only)")
        st.markdown(
            "This action **overwrites the main Google Sheet** with an empty master table. "
            "It is destructive and cannot be undone. Check the confirmation box to enable Reset."
        )

        confirm_reset = st.checkbox("I understand this will permanently erase all league data in the sheet", key="confirm_reset_checkbox")

        if st.button("Reset Google Sheet Now", disabled=not confirm_reset):
            try:
                empty_df = pd.DataFrame(columns=MASTER_COLUMNS)
                conn = get_gsheets_conn()
                # Optional: write an audit row to a separate sheet before overwriting
                conn.update(data=empty_df)
                try:
                    st.cache_data.clear()
                except Exception:
                    pass
                try:
                    st.cache_resource.clear()
                except Exception:
                    pass
                preserved = {"authenticated"}
                for k in list(st.session_state.keys()):
                    if k not in preserved:
                        del st.session_state[k]
                st.success("Google Sheet overwritten with an empty master table.")
                st.info("Caches and session state cleared (except admin login).")
                try:
                    st.experimental_rerun()
                except Exception:
                    st.warning("Reset complete. Please refresh the page if the UI does not update automatically.")
            except Exception as e:
                st.error(f"Reset failed: {e}")

        st.divider()
        with st.expander("Danger Zone (other destructive actions)", expanded=False):
            st.markdown(
                "**Warning:** Actions here can modify or erase data. To proceed, type the confirmation word and re-enter the admin password."
            )
            with st.form("admin_reset_form"):
                confirm_text = st.text_input("Type RESET to confirm", key="admin_reset_confirm")
                confirm_pass = st.text_input("Re-enter Admin Password", type="password", key="admin_reset_pass")
                submit_reset = st.form_submit_button("Confirm Reset Leaderboard")
            if submit_reset:
                if confirm_text == "RESET" and confirm_pass == ADMIN_PASSWORD:
                    try:
                        st.success("Leaderboard reset executed (placeholder).")
                        try:
                            st.experimental_rerun()
                        except Exception:
                            st.warning("Reset done. Please refresh the page if the UI does not update automatically.")
                    except Exception as e:
                        st.error(f"Reset failed: {e}")
                else:
                    st.error("Confirmation failed. Type RESET and provide the correct admin password to proceed.")

# -------------------------
# Admin debug snapshot
# -------------------------
if st.session_state.get("authenticated"):
    with st.expander("Admin Debug Snapshot", expanded=False):
        st.write("Data snapshot (head):")
        try:
            if "last_successful_head" in st.session_state:
                st.dataframe(st.session_state["last_successful_head"])
            else:
                st.dataframe(df_main.head(10))
        except Exception:
            st.write("No snapshot available.")
