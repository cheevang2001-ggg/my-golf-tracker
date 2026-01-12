# --- STEP 2: LOAD & PREPARE DATA ---
df_main = load_data()

if not df_main.empty:
    df_main = df_main.fillna(0)
    
    # NEW FEDEX/ANIMAL LOGIC: Rank by Net_Score (Lowest is better)
    # 1st = 100, 2nd = 85, etc.
    df_main['week_rank'] = df_main.groupby('Week')['Net_Score'].rank(ascending=True, method='min')
    df_main['animal_pts'] = df_main['week_rank'].map(FEDEX_POINTS).fillna(0)

# --- TAB 2: NO ANIMALS STANDING ---
with tab2:
    if not df_main.empty:
        st.header("🏁 No Animals Standing")
        
        # We now only sum up the weekly 'animal_pts' 
        # Pars, Birdies, and Feat points are removed from this leaderboard calculation
        standings = df_main.groupby('Player').agg({
            'animal_pts': 'sum', 
            'Net_Score': 'mean'
        }).rename(columns={
            'animal_pts': 'Animal Points', 
            'Net_Score': 'Avg Net'
        }).reset_index()
        
        # 'Total Animal Points' now strictly equals the accumulated 'Animal Points'
        standings['Total Animal Points'] = standings['Animal Points']
        
        # Sort by Animal Points (Highest first), then Net Score (Lowest first)
        standings = standings.round(2).sort_values(by=['Animal Points', 'Avg Net'], ascending=[False, True])
        
        # Display the leaderboard with your specific column names
        st.dataframe(standings[['Player', 'Animal Points', 'Total Animal Points', 'Avg Net']], 
                     use_container_width=True, hide_index=True)
    else:
        st.info("No data found. Submit scores to generate standings.")
