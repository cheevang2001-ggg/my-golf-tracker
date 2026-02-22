with tabs[1]: # Standings
    st.subheader("🏆 2026 Season Standings")
    if not df_main.empty:
        # Create a fresh copy for calculations
        calc_df = df_main.copy()
        calc_df['GGG_pts'] = 0.0
        
        # Iterate through each week to assign points
        for w in calc_df['Week'].unique():
            if w == 0: continue # Skip registration week
            
            # Filter for active rounds this week
            mask = (calc_df['Week'] == w) & (calc_df['DNF'] == False)
            if mask.any():
                week_data = calc_df.loc[mask].copy()
                # Rank: Lower net score = smaller rank number (1st, 2nd, etc)
                week_data['Rank'] = week_data['Net_Score'].rank(ascending=True, method='min')
                
                # Map ranks to FedEx points
                for idx, row in week_data.iterrows():
                    points = FEDEX_POINTS.get(int(row['Rank']), 10.0) # 10 pt floor
                    calc_df.at[idx, 'GGG_pts'] = float(points)
        
        # Aggregate totals by player
        standings = calc_df.groupby('Player')['GGG_pts'].sum().reset_index()
        
        # Calculate current handicap for display
        standings['HCP'] = [calculate_rolling_handicap(df_main[df_main['Player'] == p]) for p in standings['Player']]
        
        # Sort by points descending
        standings = standings.sort_values(by='GGG_pts', ascending=False).reset_index(drop=True)
        standings.index += 1 # 1-based leaderboard
        
        st.dataframe(
            standings[['Player', 'GGG_pts', 'HCP']], 
            use_container_width=True,
            column_config={
                "GGG_pts": st.column_config.NumberColumn("Total Points", format="%d"),
                "HCP": st.column_config.NumberColumn("Current HCP", format="%.1f")
            }
        )
    else:
        st.info("No scores recorded yet. Standings will appear after Week 1.")
