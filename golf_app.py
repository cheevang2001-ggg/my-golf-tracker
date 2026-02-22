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
@st.cache_data(ttl=10) # Reduced TTL to 10 seconds for more frequent updates
def load_data():
    try:
        data = conn.read()
        return data.dropna(how='all') # Ensure we don't load totally empty rows
    except:
        return pd.DataFrame()

def save_data(week, player, pars, birdies, eagles, score_val, hcp_val):
    st.cache_data.clear() # Wipe cache so History updates immediately
    existing_data = conn.read(ttl=0)
    
    is_dnf = (score_val == "DNF")
    final_gross = 0 if is_dnf else int(score_val)
    final_net = 0 if is_dnf else (final_gross - hcp_val)
    
    new_entry = pd.DataFrame([{
        'Week': week, 'Player': player,
        'Pars_Count': pars, 'Birdies_Count': birdies, 'Eagle_Count': eagles,
        'Total_Score': final_gross, 'Handicap': hcp_val, 
        'Net_Score': final_net, 'DNF': is_dnf,
        'PIN': st.session_state.get('current_user_pin', '') # Carry over PIN
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

# Dynamically pull players
if not df_main.empty and 'Player' in df_main.columns:
    EXISTING_PLAYERS = sorted(df_main['Player'].unique().tolist())
else:
    EXISTING_PLAYERS = []

# --- STEP 4: UI ---
st.markdown("<div style='text-align: center;'>", unsafe_allow_html=True)
st.image("GGGOLF-2.png", width=120) 
st.markdown("<h1>GGGolf 2026 Summer League</h1>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "📝 Scorecard", "🏆 Standings", "📅 History", "📜 Info", 
    "⚖️ Rules", "⚙️ Admin", "🏆 Bracket", "👤 Registration"
])

# --- TAB 1: SCORECARD ---
with tab1:
    if not EXISTING_PLAYERS:
        st.warning("No players registered. Please go to Registration.")
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
                    st.session_state['current_user_pin'] = stored_pin

        if is_verified:
            # clear_on_submit=True resets the counters to 0 after clicking submit
            with st.form("score_entry", clear_on_submit=True):
                st.subheader(f"Week {week_select} Entry: {player_select}")
                
                score_select = st.selectbox("Gross Score", ["DNF"] + [str(i) for i in range(25, 120)])
                hcp_in = st.number_input("Handicap", 0, 40, 10)
                
                st.divider()
                st.caption("Enter your round stats:")
                col1, col2, col3 = st.columns(3)
                # Use unique keys for each player/week to force reset on change
                s_pars = col1.number_input("Pars", 0, 18, 0, key=f"p_{player_select}_{week_select}")
                s_birdies = col2.number_input("Birdies", 0, 18, 0, key=f"b_{player_select}_{week_select}")
                s_eagles = col3.number_input("Eagles", 0, 18, 0, key=f"e_{player_select}_{week_select}")
                
                # --- CALCULATION PREVIEW ---
                total_stats = s_pars + s_birdies + s_eagles
                st.info(f"📊 **Summary:** {s_pars} Pars, {s_birdies} Birdies, {s_eagles} Eagles | **Total Better-Than-Bogey:** {total_stats}")
                
                if st.form_submit_button("Submit Score"):
                    save_data(week_select, player_select, s_pars, s_birdies, s_eagles, score_select, hcp_in)
                    st.success("Score Saved! Data is updating...")
                    st.rerun()
        else:
            st.warning("Please enter your PIN.")

# --- TAB 3: HISTORY (Updated to handle empty sheets) ---
with tab3:
    st.subheader("Season History")
    if not df_main.empty:
        # Filter out "Week 0" initialization rows so history stays clean
        display_df = df_main[df_main['Week'] > 0]
        if not display_df.empty:
            st.dataframe(display_df.sort_values(["Week", "Player"], ascending=[False, True]), use_container_width=True, hide_index=True)
        else:
            st.write("No scores recorded for weeks 1-12 yet.")
    else:
        st.write("The league database is currently empty.")

# --- TAB 6: ADMIN (Add Force Refresh) ---
with tab6:
    st.subheader("Admin Controls")
    admin_pw = st.text_input("Admin Password", type="password", key="adm_pw")
    if admin_pw == ADMIN_PASSWORD:
        st.session_state["authenticated"] = True
        if st.button("Force Clear App Cache"):
            st.cache_data.clear()
            st.rerun()

# --- TAB 8: REGISTRATION (Improved Reset) ---
with tab8:
    st.header("👤 Player Registration")
    with st.form("reg_form", clear_on_submit=True):
        new_name = st.text_input("Full Name", key="n_name")
        new_pin = st.text_input("Create 4-Digit PIN", max_chars=4, type="password", key="n_pin")
        starting_hcp = st.number_input("Starting Handicap", 0, 36, 10)
        
        if st.form_submit_button("Register Player"):
            if new_name and len(new_pin) == 4:
                # Initialize with Week 0 and 0 counts
                new_reg = pd.DataFrame([{
                    "Week": 0, "Player": new_name, "PIN": new_pin, 
                    "Handicap": starting_hcp, "Total_Score": 0, "DNF": True,
                    "Pars_Count": 0, "Birdies_Count": 0, "Eagle_Count": 0, "Net_Score": 0
                }])
                updated_df = pd.concat([df_main, new_reg], ignore_index=True)
                conn.update(data=updated_df)
                st.cache_data.clear()
                st.success(f"Welcome {new_name}!")
                st.rerun()
