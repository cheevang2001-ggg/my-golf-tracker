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
# Set ttl=0 to ensure the app pulls FRESH data on every interaction
def load_data():
    try:
        data = conn.read(ttl=0)
        return data.dropna(how='all')
    except:
        return pd.DataFrame()

def save_data(week, player, pars, birdies, eagles, score_val, hcp_val, pin):
    # Clear cache BEFORE saving
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
    # Clear cache AFTER saving and rerun to show changes instantly
    st.cache_data.clear()
    st.rerun()

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

# THE 8 DEFINITIVE TABS
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "📝 Scorecard", "🏆 Standings", "📅 History", "📜 Info", 
    "⚖️ Rules", "⚙️ Admin", "🏆 Bracket", "👤 Registration"
])

# --- TAB 1: SCORECARD ---
with tab1:
    if not EXISTING_PLAYERS:
        st.warning("No players registered yet.")
    else:
        c1, c2 = st.columns(2)
        player_select = c1.selectbox("Player", EXISTING_PLAYERS, key="score_player_sel")
        week_select = c2.selectbox("Week", range(1, 13), key="score_week_sel")
        user_pin_input = st.text_input(f"PIN for {player_select}", type="password", key="score_pin_input")

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
            with st.form("score_entry", clear_on_submit=True):
                score_select = st.selectbox("Gross Score", ["DNF"] + [str(i) for i in range(25, 120)])
                hcp_in = st.number_input("Handicap", 0, 40, 10)
                
                col1, col2, col3 = st.columns(3)
                s_pars = col1.number_input("Pars", 0, 18, 0, key=f"p_{player_select}_{week_select}")
                s_birdies = col2.number_input("Birdies", 0, 18, 0, key=f"b_{player_select}_{week_select}")
                s_eagles = col3.number_input("Eagles", 0, 18, 0, key=f"e_{player_select}_{week_select}")
                
                if st.form_submit_button("Submit Score"):
                    save_data(week_select, player_select, s_pars, s_birdies, s_eagles, score_select, hcp_in, stored_pin)

# --- TAB 2: STANDINGS ---
with tab2:
    st.subheader("🏆 Summer League Standings")
    if not df_main.empty:
        st.write("Live standings will calculate here as scores are entered.")

# --- TAB 3: HISTORY ---
with tab3:
    st.subheader("📅 Weekly History")
    # Only show actual weeks, skip Week 0 (Registration)
    history_df = df_main[df_main['Week'] > 0] if not df_main.empty else pd.DataFrame()
    if not history_df.empty:
        st.dataframe(history_df.sort_values(["Week", "Player"], ascending=[False, True]), use_container_width=True, hide_index=True)
    else:
        st.info("No scores recorded yet.")

# --- TAB 4: INFO ---
with tab4:
    st.header("📜 League Info")
    st.write("Information regarding locations and dates.")

# --- TAB 5: RULES ---
with tab5:
    st.header("⚖️ League Rules")
    st.write("1. No Mulligans. 2. Record all scores. 3. Play fast.")

# --- TAB 6: ADMIN ---
with tab6:
    st.subheader("⚙️ Admin Settings")
    admin_pw = st.text_input("Admin Password", type="password", key="admin_key")
    if admin_pw == ADMIN_PASSWORD:
        st.session_state["authenticated"] = True
        st.success("Admin Verified")
        if st.button("🔄 Force Real-Time Sync"):
            st.cache_data.clear()
            st.rerun()
    else:
        st.session_state["authenticated"] = False

# --- TAB 7: BRACKET ---
with tab7:
    st.header("🏆 Tournament Bracket")
    st.info("12-Man Re-seeding Bracket")
    # Bracket logic stays here now, separate from Admin
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.subheader("Week 9")
        st.write("Seeds 1-4: BYE")
        st.divider()
        st.write("Match A: 5 vs 12")
        st.write("Match B: 6 vs 11")
        st.write("Match C: 7 vs 10")
        st.write("Match D: 8 vs 9")

# --- TAB 8: REGISTRATION ---
with tab8:
    st.header("👤 Player Registration")
    with st.form("reg_form", clear_on_submit=True):
        new_name = st.text_input("Name", key="reg_name")
        new_pin = st.text_input("4-Digit PIN", max_chars=4, type="password", key="reg_pin")
        starting_hcp = st.number_input("Starting Handicap", 0, 36, 10, key="reg_hcp")
        
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
                st.success(f"Registered {new_name}!")
                st.rerun()
