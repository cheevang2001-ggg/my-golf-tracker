import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# --- STEP 1: CONFIGURATION ---
st.set_page_config(page_title="2026 GGGolf Summer League", layout="wide") 

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

ADMIN_PASSWORD = "InsigniaSeahawks6145" 
conn = st.connection("gsheets", type=GSheetsConnection)

# --- STEP 2: FUNCTIONS ---
@st.cache_data(ttl=10) # Low TTL to help prevent "Ghost Data"
def load_data():
    try:
        # read(ttl=0) ensures we bypass local cache to check the actual sheet
        data = conn.read(ttl=0)
        return data.dropna(how='all')
    except:
        return pd.DataFrame()

def save_data(week, player, pars, birdies, eagles, score_val, hcp_val, pin):
    st.cache_data.clear()
    existing_data = conn.read(ttl=0)
    
    is_dnf = (score_val == "DNF")
    final_gross = 0 if is_dnf else int(score_val)
    final_net = 0 if is_dnf else (final_gross - hcp_val)
    
    new_entry = pd.DataFrame([{
        'Week': week, 'Player': player,
        'Pars_Count': pars, 'Birdies_Count': birdies, 'Eagle_Count': eagles,
        'Total_Score': final_gross, 'Handicap': hcp_val, 
        'Net_Score': final_net, 'DNF': is_dnf, 'PIN': pin
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

if not df_main.empty and 'Player' in df_main.columns:
    EXISTING_PLAYERS = sorted(df_main['Player'].unique().tolist())
else:
    EXISTING_PLAYERS = []

# --- STEP 4: UI LAYOUT ---
st.markdown("<div style='text-align: center;'>", unsafe_allow_html=True)
st.image("GGGOLF-2.png", width=120) 
st.markdown("<h1>GGGolf Summer League 2026</h1>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

# Fixed Tab Unpacking (8 Variables for 8 Tabs)
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "📝 Scorecard", "🏆 Standings", "📅 History", "📜 Info", 
    "⚖️ Rules", "⚙️ Admin", "🏆 Bracket", "👤 Registration"
])

# --- TAB 1: SCORECARD ---
with tab1:
    if not EXISTING_PLAYERS:
        st.warning("No players registered.")
    else:
        c1, c2 = st.columns(2)
        player_select = c1.selectbox("Player", EXISTING_PLAYERS)
        week_select = c2.selectbox("Week", range(1, 13))
        user_pin_input = st.text_input(f"PIN for {player_select}", type="password")

        is_verified = False
        stored_pin = ""
        if st.session_state["authenticated"]:
            is_verified = True
        elif user_pin_input and not df_main.empty:
            player_info = df_main[df_main['Player'] == player_select]
            if not player_info.empty:
                stored_pin = str(player_info.iloc[0].get('PIN', '')).split('.')[0].strip()
                if user_pin_input.strip() == stored_pin:
                    is_verified = True

        if is_verified:
            # clear_on_submit forces counters back to 0
            with st.form("score_entry", clear_on_submit=True):
                score_select = st.selectbox("Gross Score", ["DNF"] + [str(i) for i in range(25, 120)])
                hcp_in = st.number_input("Handicap", 0, 40, 10)
                
                col1, col2, col3 = st.columns(3)
                # Unique keys per week/player prevent values carrying over
                s_pars = col1.number_input("Pars", 0, 18, 0, key=f"p_{player_select}_{week_select}")
                s_birdies = col2.number_input("Birdies", 0, 18, 0, key=f"b_{player_select}_{week_select}")
                s_eagles = col3.number_input("Eagles", 0, 18, 0, key=f"e_{player_select}_{week_select}")
                
                if st.form_submit_button("Submit Score"):
                    save_data(week_select, player_select, s_pars, s_birdies, s_eagles, score_select, hcp_in, stored_pin)
                    st.success("Score Saved!")
                    st.rerun()
        else:
            st.info("Enter PIN to unlock.")

# --- TAB 2: STANDINGS ---
with tab2:
    st.subheader("League Standings")
    if not df_main.empty:
        st.write("Calculation Logic TBD")

# --- TAB 3: HISTORY ---
with tab3:
    st.subheader("Season History")
    if not df_main.empty:
        # FILTER: Only show weeks 1-12 (hides the Week 0 registration data)
        history_df = df_main[df_main['Week'] > 0]
        if history_df.empty:
            st.info("No weekly scores recorded yet.")
        else:
            st.dataframe(history_df.sort_values("Week", ascending=False), use_container_width=True, hide_index=True)
    else:
        st.info("Database is empty.")

# --- TAB 4: INFO ---
with tab4:
    st.write("League details go here.")

# --- TAB 5: RULES ---
with tab5:
    st.write("Rules go here.")

# --- TAB 6: ADMIN ---
with tab6:
    st.subheader("⚙️ Admin Settings")
    admin_pw = st.text_input("Admin Password", type="password")
    if admin_pw == ADMIN_PASSWORD:
        st.session_state["authenticated"] = True
        if st.button("🔄 Force Clear Ghost Data (Cache)"):
            st.cache_data.clear()
            st.rerun()
    else:
        st.session_state["authenticated"] = False

# --- TAB 7: BRACKET ---
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


# --- TAB 8: REGISTRATION ---
with tab8:
    st.header("👤 New Player Registration")
    with st.form("reg_form", clear_on_submit=True):
        new_name = st.text_input("Name")
        new_pin = st.text_input("4-Digit PIN", max_chars=4, type="password")
        starting_hcp = st.number_input("Handicap", 0, 36, 10)
        
        if st.form_submit_button("Register"):
            if new_name and len(new_pin) == 4:
                new_reg = pd.DataFrame([{
                    "Week": 0, "Player": new_name, "PIN": new_pin, 
                    "Handicap": starting_hcp, "Total_Score": 0, "DNF": True,
                    "Pars_Count": 0, "Birdies_Count": 0, "Eagle_Count": 0, "Net_Score": 0
                }])
                updated_df = pd.concat([df_main, new_reg], ignore_index=True)
                conn.update(data=updated_df)
                st.cache_data.clear()
                st.success("Registered!")
                st.rerun()

