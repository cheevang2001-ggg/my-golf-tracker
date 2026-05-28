# --------------------------------------------------------------- DEV ENVIRONMENT FOR GGG GOLF ---------------------------------------------------------------
import streamlit as st
import pandas as pd
import time

# --- 1. CONFIGURATION & DATABASE CONNECTION ---
st.set_page_config(page_title="DEV GGGolf League Environment", layout="wide")

from st_supabase_connection import SupabaseConnection
conn = st.connection("supabase", type=SupabaseConnection)

# --- 2. CORE DATA LOADING ---
def load_data():
    try:
        # Pull active players directly from your new event player table
        response = conn.table("battle_events").select("Player").execute()
        data = pd.DataFrame(response.data)
        
        if data.empty or 'Player' not in data.columns: 
            return pd.DataFrame(columns=['Player'])
        
        df = data.dropna(how='all')
        df = df[df['Player'].str.lower() != 'john']
        return df[df['Player'] != ""]
        
    except Exception as e:
        st.warning(f"Database error loading players: {e}")
        return pd.DataFrame(columns=['Player'])

# --- 3. LIVE SCORING INTERFACE ---
def render_live_scoring():
    st.subheader("⛳ Live Scoring")
    
    if not EXISTING_PLAYERS: 
        st.warning("No players found in the event player list table.")
        return

    # --- PLAYER SELECTION ---
    player_select = st.segmented_control(
        "Select Your Profile to Score", 
        options=EXISTING_PLAYERS,
        selection_mode="single",
        key="live_player_select"
    )

    if not player_select:
        st.info("Please select your name above to begin live scoring.")
    else:
        # --- INPUT SECTION (No PIN Lock Required) ---
        st.success(f"Scoring active for: **{player_select}**")
        
        if 'active_hole' not in st.session_state:
            st.session_state.active_hole = 1

        st.write("**Select Hole**")
        
        hole = st.radio(
            "Hole Selection",
            options=list(range(1, 19)),
            index=list(range(1, 19)).index(st.session_state.active_hole),
            horizontal=True,
            label_visibility="collapsed",
            key="live_hole_radio"
        )
        
        st.session_state.active_hole = hole

        # Score Entry Form
        with st.form("live_score_entry_form", clear_on_submit=True):
            score = st.slider("Score", min_value=1, max_value=20, value=4)
            
            if st.form_submit_button("Submit Score", type="primary", use_container_width=True):
                try:
                    new_score = {
                        "week": 1, 
                        "player_name": player_select,
                        "hole_number": st.session_state.active_hole,
                        "score": score,
                        "updated_at": "now()"
                    }
                    # Upserts directly to your live scores event table
                    conn.table("live_scores").upsert(new_score, on_conflict="week,player_name,hole_number").execute()
                    
                    st.success(f"Hole {st.session_state.active_hole} saved!")
                    
                    # Auto-advance helper logic to the next hole
                    if st.session_state.active_hole < 18:
                        st.session_state.active_hole += 1
                    
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Save Failed: {e}")

    # --- PUBLIC LEADERBOARD VIEW ---
    st.divider()
    st.subheader("📊 Live Leaderboard & Scorecard")
    
    if st.button("🔄 Refresh Leaderboard"):
        st.rerun()
    
    try:
        response = conn.table("live_scores").select("*").eq("week", 1).execute()
        df_live = pd.DataFrame(response.data)
        
        if not df_live.empty:
            # Pivot the flat database rows into a standard horizontal matrix scorecard
            scorecard = df_live.pivot(index="player_name", columns="hole_number", values="score")
            for i in range(1, 19):
                if i not in scorecard.columns: scorecard[i] = None
            
            scorecard = scorecard.apply(pd.to_numeric, errors='coerce').fillna(0).astype(int)
            
            # Calculate Front 9, Back 9, and Total metrics
            scorecard["Front 9"] = scorecard[range(1, 10)].sum(axis=1)
            scorecard["Back 9"] = scorecard[range(10, 19)].sum(axis=1)
            scorecard["Total"] = scorecard["Front 9"] + scorecard["Back 9"]
            
            st.write("### 🏆 Current Top 3")
            leaderboard = scorecard[scorecard["Total"] > 0].sort_values(by="Total", ascending=True)
            
            podium_cols = st.columns(3)
            medals = ["🥇 1st", "🥈 2nd", "🥉 3rd"]
            
            for rank in range(3):
                if rank < len(leaderboard):
                    player = leaderboard.index[rank]
                    score = leaderboard.iloc[rank]["Total"]
                    podium_cols[rank].metric(
                        label=f"{medals[rank]} - {player}",
                        value=f"{score} Strokes"
                    )
                else:
                    podium_cols[rank].metric(label=medals[rank], value="Waiting...")
                    
            st.divider()
            
            st.write("### 📋 Full Scorecard")
            cols_order = list(range(1, 10)) + ["Front 9"] + list(range(10, 19)) + ["Back 9", "Total"]
            display_df = scorecard[cols_order].replace(0, '-')
            
            st.dataframe(display_df, use_container_width=True)
            
        else:
            st.info("No scores recorded yet.")
    except Exception as e:
        st.warning("Scorecard database collection is currently unavailable.")

# --- 4. INITIALIZATION & APP LAUNCH ---
df_main = load_data()
EXISTING_PLAYERS = sorted(df_main['Player'].unique().tolist()) if not df_main.empty else []

# Branding Header layout
st.markdown("<div style='text-align: center;'>", unsafe_allow_html=True)
st.image("GGGOLF-2.png", width=120) 
st.markdown("<h1>----DEV GGGolf Live Event Scoring----</h1>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

# Run live scoring as the primary framework module
render_live_scoring()
