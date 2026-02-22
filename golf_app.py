import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# --- STEP 1: CONFIGURATION & SETUP ---
st.set_page_config(page_title="2026 GGGolf Summer League", layout="wide") 

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

ADMIN_PASSWORD = "InsigniaSeahawks6145" 
conn = st.connection("gsheets", type=GSheetsConnection)

# --- STEP 2: FUNCTIONS ---
@st.cache_data(ttl=600)
def load_data():
    return conn.read()

def calculate_rolling_handicap(player_df, current_week):
    # Filter for rounds where a score was actually entered [cite: 3]
    valid_rounds = player_df[(player_df['Total_Score'] > 0) & (player_df['Week'] < current_week)]
    valid_rounds = valid_rounds.sort_values('Week', ascending=False)
    if len(valid_rounds) < 4:
        return None 
    last_4 = valid_rounds.head(4)['Total_Score'].tolist()
    last_4.remove(max(last_4))
    avg_gross = sum(last_4) / 3
    return int(round(max(0, avg_gross - 36)))

def get_handicaps(current_week, player_list):
    df = load_data() 
    calculated_hcps = {}
    for player in player_list:
        if not df.empty:
            player_data = df[df['Player'] == player]
            rolling = calculate_rolling_handicap(player_data, current_week)
            # Default to 10 if no history found [cite: 3]
            calculated_hcps[player] = rolling if rolling is not None else 10
        else:
            calculated_hcps[player] = 10
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

# --- STEP 3: DATA PROCESSING ---
df_main = load_data()

# Dynamically pull players from the Google Sheet [cite: 8]
if not df_main.empty and 'Player' in df_main.columns:
    EXISTING_PLAYERS = sorted(df_main['Player'].unique().tolist())
else:
    EXISTING_PLAYERS = []

FEDEX_POINTS = {
    1: 100, 2: 77, 3: 64, 4: 54, 5: 47, 6: 41,
    7: 36, 8: 31, 9: 27, 10: 24, 11: 21, 12: 18, 13: 16
}

if not df_main.empty:
    df_main = df_main.fillna(0)
    df_main['DNF'] = df_main.get('DNF', False).astype(bool)
    df_main['animal_pts'] = 0.0
    for week in df_main['Week'].unique():
        mask = (df_main['Week'] == week) & (df_main['DNF'] == False)
        if mask.any():
            ranks = df_main.loc[mask, 'Net_Score'].rank(ascending=True, method='min')
            df_main.loc[mask, 'animal_pts'] = ranks.map(FEDEX_POINTS).fillna(0)

# --- STEP 4: UI HEADER ---
st.markdown("<div style='text-align: center;'>", unsafe_allow_html=True)
st.image("GGGOLF-2.png", width=120) 
st.markdown("<h1 style='margin-top: -10px;'>GGGolf 2026</h1><p style='margin-top: -20px; color: gray;'>Summer League 2026</p>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)
st.divider()

# --- STEP 5: TABS DEFINITION ---
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "📝 Scorecard", "🏆 Standings", "📅 History", "📜 Info", 
    "⚖️ Rules", "⚙️ Admin", "🏆 Bracket", "👤 Player Registration"
])

# --- TAB 1: SCORECARD ---
with tab1:
    if not EXISTING_PLAYERS:
        st.warning("No players registered yet. Please go to the Player Registration tab.")
    else:
        c1, c2 = st.columns(2)
        player_select = c1.selectbox("Select Player", EXISTING_PLAYERS)
        week_select = c2.selectbox("Select Week", range(1, 13), key="w_sel")
        
        user_pin_input = st.text_input(f"Enter PIN for {player_select}", type="password", key="pin_input")

        is_verified = False
        if st.session_state["authenticated"]:
            is_verified = True
        elif user_pin_input and not df_main.empty:
            # Locate PIN from the first time the player appears in the sheet [cite: 9, 10]
            player_info = df_main[df_main['Player'] == player_select]
            if not player_info.empty:
                stored_pin = str(player_info.iloc[0].get('PIN', '')).split('.')[0].strip()
                if user_pin_input.strip() == stored_pin:
                    is_verified = True

        if is_verified:
            st.success(f"✅ Access Granted for {player_select}")
            with st.form("score_entry"):
                current_hcps_map = get_handicaps(week_select, EXISTING_PLAYERS)
                hcp_in = st.number_input("Handicap", value=current_hcps_map.get(player_select, 10))
                score_select = st.selectbox("Gross Score", ["DNF"] + [str(i) for i in range(25, 100)])
                
                col1, col2, col3 = st.columns(3)
                sel_pars = col1.number_input("Pars", 0, 18, 0)
                sel_birdies = col2.number_input("Birdies", 0, 18, 0)
                sel_eagles = col3.number_input("Eagles", 0, 18, 0)
                
                if st.form_submit_button("Submit Score"):
                    save_data(week_select, player_select, sel_pars, sel_birdies, sel_eagles, score_select, hcp_in)
                    st.success("Score Saved!")
                    st.rerun()
        else:
            st.warning("Locked: Please enter your 4-digit PIN.")

# --- TAB 2: STANDINGS ---
with tab2:
    if not df_main.empty:
        standings = df_main.groupby('Player').agg({'animal_pts': 'sum'}).rename(columns={'animal_pts': 'Animal Pts'}).reset_index()
        st.dataframe(standings.sort_values("Animal Pts", ascending=False), use_container_width=True, hide_index=True)
    else:
        st.info("No scores recorded yet.")

# --- TAB 3: HISTORY ---
with tab3:
    if not df_main.empty:
        st.dataframe(df_main.sort_values(["Week", "Player"], ascending=[False, True]), use_container_width=True, hide_index=True)

# --- TAB 4: INFO ---
with tab4:
    st.header("📜 League Information")
    st.markdown("""
    **General Info:**
    * **Tee Time:** About 2:00pm [cite: 22]
    * **Makeups:** There are no makeups; a DNF will be issued[cite: 22].
    * **Handicap:** Average of best 3 rounds used[cite: 22].
    """)

# --- TAB 5: RULES ---
with tab5:
    st.header("⚖️ League Rules & Etiquette")
    col_r1, col_r2 = st.columns(2)
    with col_r1:
        st.subheader("Gameplay")
        st.write("- Net stroke play format[cite: 32].")
        st.write("- Mulligans: 1-bucket penalty[cite: 33].")
    with col_r2:
        st.subheader("Etiquette")
        st.write("- Reset hitting area after turn[cite: 36].")

# --- TAB 6: ADMIN ---
with tab6:
    st.subheader("⚙️ Admin Controls")
    admin_input = st.text_input("Enter Admin Password", type="password", key="admin_pwd")
    if admin_input == ADMIN_PASSWORD:
        st.session_state["authenticated"] = True
        st.success("Admin Logged In")
        if st.button("Refresh Data"):
            st.cache_data.clear()
            st.rerun()
    else:
        st.session_state["authenticated"] = False

# --- TAB 7: BRACKET ---
with tab7:
    st.header("🏆 Tournament Bracket")
    st.info("Re-seeding Bracket - TBD based on final regular season standings.")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.subheader("Week 9")
        st.write("Matchups TBD")

# --- TAB 8: REGISTRATION ---
with tab8:
    st.header("👤 Player Registration")
    st.info("Register below to join the Summer League. Once you click register, the page will refresh for the next person.")
    
    # Use a unique form key to help Streamlit manage the state
    with st.form("reg_form", clear_on_submit=True):
        # Adding unique keys to these inputs helps the 'clear_on_submit' feature
        new_name = st.text_input("Full Name", key="reg_name_input")
        new_pin = st.text_input("Create 4-Digit PIN (used for scorecard)", max_chars=4, type="password", key="reg_pin_input")
        starting_hcp = st.number_input("Starting Handicap", 0, 36, 10, key="reg_hcp_input")
        
        if st.form_submit_button("Register Player"):
            if new_name and len(new_pin) == 4:
                # Prepare the new row
                new_reg = pd.DataFrame([{
                    "Week": 0, "Player": new_name, "PIN": new_pin, 
                    "Handicap": starting_hcp, "Total_Score": 0, "DNF": True,
                    "Pars_Count": 0, "Birdies_Count": 0, "Eagle_Count": 0, "Net_Score": 0
                }])
                
                # Update Google Sheets
                updated_df = pd.concat([df_main, new_reg], ignore_index=True)
                conn.update(data=updated_df)
                
                # CRITICAL: Clear cache so the new player appears in Scorecard dropdown immediately
                st.cache_data.clear()
                
                st.success(f"Welcome {new_name}! Registration successful.")
                
                # Force the app to restart, clearing all input fields for the next user
                st.rerun()
            else:
                st.error("Please provide a name and a 4-digit PIN.")

