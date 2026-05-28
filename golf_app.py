# --------------------------------------------------------------- DEV ENVIRONMENT FOR GGG GOLF ---------------------------------------------------------------
import streamlit as st
import pandas as pd
import time

# --- 1. CONFIGURATION & DATABASE CONNECTION ---
st.set_page_config(page_title="July 4 Battle 2026", layout="wide")

ADMIN_PASSWORD = "!@#Seahawks6145!@#"

from st_supabase_connection import SupabaseConnection
conn = st.connection("supabase", type=SupabaseConnection)

# --- 2. DYNAMIC PLAYER SOURCING FROM BATTLE_EVENTS ---
def load_active_players():
    try:
        # Pull player profiles strictly from battle_events
        response = conn.table("battle_events").select("Player").execute()
        if response.data:
            df = pd.DataFrame(response.data)
            return sorted(df['Player'].dropna().unique().tolist())
        return []
    except Exception:
        return []

# --- 3. CORE APPLICATION LAYOUT ---
st.markdown("<div style='text-align: center;'>", unsafe_allow_html=True)
st.image("CurrieMemorial2026.jpg", width=480) 
st.markdown("<h1>July 4 Battle 2026</h1>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

# Fetch current list of event players
active_players = load_active_players()

st.subheader("⛳ Live Scoring")

# COMPACT RADIO BUTTON ROW FOR PLAYER SELECTION
selection_options = active_players + ["➕ Add New Player"]
player_choice = st.radio(
    "Select Your Name to Score:",
    options=selection_options,
    index=None,  # Keeps it blank until a selection is explicitly clicked
    horizontal=True,
    key="player_radio_selector"
)

player_name = None
if player_choice == "➕ Add New Player":
    new_name_input = st.text_input("Type Your Full Name to Register & Score:", key="new_player_name_field").strip()
    if new_name_input:
        player_name = new_name_input
elif player_choice is not None:
    player_name = player_choice

# Render inputs only if a player identity is established
if player_name:
    st.success(f"Scoring Session Active For: **{player_name}**")
    
    if 'active_hole' not in st.session_state:
        st.session_state.active_hole = 1

    # Horizontal Hole Selection Bar
    hole = st.radio(
        "Select Hole to Score",
        options=list(range(1, 19)),
        index=list(range(1, 19)).index(st.session_state.active_hole),
        horizontal=True,
        key="live_hole_radio"
    )
    st.session_state.active_hole = hole

    # Score Submission Form
    with st.form("live_score_entry_form", clear_on_submit=True):
        score = st.slider("Strokes", min_value=1, max_value=20, value=4)
        
        if st.form_submit_button("Submit Score", type="primary", use_container_width=True):
            try:
                # Automate database insertion if they are a completely new player
                if player_choice == "➕ Add New Player" and player_name not in active_players:
                    conn.table("battle_events").insert({"Player": player_name, "Week": 0}).execute()
                
                new_score = {
                    "week": 1, 
                    "player_name": player_name,
                    "hole_number": st.session_state.active_hole,
                    "score": score,
                    "updated_at": "now()"
                }
                
                # Write strictly to live_scores_event
                conn.table("live_scores_event").upsert(new_score, on_conflict="week,player_name,hole_number").execute()
                
                st.success(f"Hole {st.session_state.active_hole} saved!")
                
                # Automatically forward to the next hole layout
                if st.session_state.active_hole < 18:
                    st.session_state.active_hole += 1
                
                time.sleep(0.8)
                st.rerun()
            except Exception as e:
                st.error(f"Database Communication Failed: {e}")

# --- 4. LEADERBOARD & FIXED SEQUENCE SCORECARD ---
st.divider()
st.subheader("📊 Live Leaderboard & Scorecard")

if st.button("🔄 Refresh Board Data", use_container_width=True):
    st.rerun()

try:
    response = conn.table("live_scores_event").select("*").eq("week", 1).execute()
    df_live = pd.DataFrame(response.data)
    
    if not df_live.empty:
        # Pivot standard data rows into structured layout matrix
        scorecard = df_live.pivot(index="player_name", columns="hole_number", values="score")
        
        # FORCE cast index columns to strict numerical integers to stop alphabetical string jumping
        scorecard.columns = [int(c) for c in scorecard.columns]
        
        # Inject missing structural dimensions safely if players haven't tracking scores yet
        for i in range(1, 19):
            if i not in scorecard.columns: 
                scorecard[i] = 0
        
        scorecard = scorecard.fillna(0).astype(int)
        
        # Calculate segmented totals using explicit matrix coordinates
        scorecard["Front 9"] = scorecard[list(range(1, 10))].sum(axis=1)
        scorecard["Back 9"] = scorecard[list(range(10, 19))].sum(axis=1)
        scorecard["Total"] = scorecard["Front 9"] + scorecard["Back 9"]
        
        # Podium calculation parsing
        leaderboard = scorecard[scorecard["Total"] > 0].sort_values(by="Total", ascending=True)
        
        st.write("### 🏆 Current Top 4")
        podium_cols = st.columns(4)
        medals = ["🥇 1st", "🥈 2nd", "🥉 3rd", "🥉 4th"]
        
        for rank in range(4):
            if rank < len(leaderboard):
                p_name = leaderboard.index[rank]
                p_score = leaderboard.iloc[rank]["Total"]
                podium_cols[rank].metric(label=f"{medals[rank]} - {p_name}", value=f"{p_score}")
            else:
                podium_cols[rank].metric(label=medals[rank], value="--")
                
        st.divider()
        st.write("### Full Score Card - Enter your total strokes per hole")
        
        # STRICT COLUMN SEQUENCE MAP (Locks horizontal layout order perfectly)
        perfect_columns_order = list(range(1, 10)) + ["Front 9"] + list(range(10, 19)) + ["Back 9", "Total"]
        
        display_df = scorecard[perfect_columns_order].replace(0, '-')
        st.dataframe(display_df, use_container_width=True)
        
    else:
        st.info("No strokes recorded on the live server yet.")
except Exception as e:
    st.error(f"Scoreboard engine assembly error: {e}")

# --- 5. SECURE ADMIN MODULE (Wipes Battle Tables Only) ---
st.divider()
with st.expander("⚙️ Administrative Control Panel"):
    input_pwd = st.text_input("Enter System Admin Password", type="password", key="panel_gate_admin")
    
    if input_pwd == ADMIN_PASSWORD:
        st.warning("⚠️ CRITICAL OPERATIONS: Resetting will clear all live scores and registered event players.")
        confirm_gate = st.checkbox("I authorize clearing all data for this event session.")
        
        if st.button("🚨 WIPE LIVE EVENT SCORING BOARD", type="primary", disabled=not confirm_gate, use_container_width=True):
            try:
                # Wipe scores table completely
                conn.table("live_scores_event").delete().neq("id", 0).execute()
                # Wipe current event players out of battle_events table
                conn.table("battle_events").delete().neq("id", 0).execute()
                
                st.cache_data.clear()
                st.success("All event data and rosters wiped successfully! Resetting canvas...")
                time.sleep(1.5)
                st.rerun()
            except Exception as ex:
                st.error(f"Database execution dropped: {ex}")
    elif input_pwd != "":
        st.error("Authentication credentials invalid.")
