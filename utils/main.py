import pandas as pd
import numpy as np

def generate_seed_matrix():
    print("Loading data...")
    # 1. Load the Data
    # Update these filenames if you want to run it for the Women's tournament (WNCAATourney...)
    try:
        results = pd.read_csv('MNCAATourneyCompactResults.csv')
        seeds = pd.read_csv('MNCAATourneySeeds.csv')
    except FileNotFoundError as e:
        print(f"Error: {e}. Please ensure the CSV files are in the same directory as this script.")
        return

    print("Cleaning seed data...")
    # 2. Clean the Seeds
    # The Seed column contains region/play-in letters (e.g., 'W01', 'X16a'). 
    # We slice out just the digits (index 1 and 2) and convert to integer.
    seeds['SeedNum'] = seeds['Seed'].apply(lambda x: int(x[1:3]))

    print("Merging seeds with game results...")
    # 3. Merge Seeds onto Results
    # Merge for the winning team
    df = results[['Season', 'WTeamID', 'LTeamID']].copy()
    df = df.merge(seeds[['Season', 'TeamID', 'SeedNum']], 
                  left_on=['Season', 'WTeamID'], 
                  right_on=['Season', 'TeamID'], 
                  how='inner')
    df.rename(columns={'SeedNum': 'WSeed'}, inplace=True)
    df.drop('TeamID', axis=1, inplace=True)

    # Merge for the losing team
    df = df.merge(seeds[['Season', 'TeamID', 'SeedNum']], 
                  left_on=['Season', 'LTeamID'], 
                  right_on=['Season', 'TeamID'], 
                  how='inner')
    df.rename(columns={'SeedNum': 'LSeed'}, inplace=True)
    df.drop('TeamID', axis=1, inplace=True)

    print("Calculating win rates...")
    # 4. Calculate Matchups from Both Perspectives
    # To build a full matrix, we need to record every game twice:
    # Once from the winner's perspective (Win = 1)
    df_winners = pd.DataFrame({
        'TeamSeed': df['WSeed'],
        'OpponentSeed': df['LSeed'],
        'Win': 1
    })

    # Once from the loser's perspective (Win = 0)
    df_losers = pd.DataFrame({
        'TeamSeed': df['LSeed'],
        'OpponentSeed': df['WSeed'],
        'Win': 0
    })

    # Combine them into one giant log of outcomes
    all_matchups = pd.concat([df_winners, df_losers], ignore_index=True)

    # 5. Group and Calculate Percentages
    # Grouping by the two seeds and getting the mean of 'Win' gives us the win percentage.
    # We also calculate the count just in case you want to see how many games were played.
    matchup_stats = all_matchups.groupby(['TeamSeed', 'OpponentSeed']).agg(
        WinRate=('Win', 'mean'),
        GamesPlayed=('Win', 'count')
    ).reset_index()

    # Convert decimal to percentage for readability (e.g., 0.75 -> 75.0)
    matchup_stats['WinRate'] = (matchup_stats['WinRate'] * 100).round(1)

    print("Pivoting into a matrix...")
    # 6. Pivot into a Matrix
    # TeamSeed goes on the Y-axis (index), OpponentSeed goes on the X-axis (columns)
    win_matrix = matchup_stats.pivot(index='TeamSeed', columns='OpponentSeed', values='WinRate')

    # Some matchups (like 1 vs 15) rarely/never happen, so we fill NaNs with a placeholder like '-'
    win_matrix = win_matrix.fillna('-')

    # 7. Save and Print the Result
    output_filename = 'Seed_Win_Rate_Matrix.csv'
    win_matrix.to_csv(output_filename)
    print(f"\nSuccess! The matrix has been saved to '{output_filename}'.")
    
    # Print a preview
    print("\nHere is a preview of your Seed vs. Seed Win Rate Matrix (%):")
    print("-" * 60)
    print(win_matrix.iloc[:5, :5])  # Showing just the top left 5x5 corner
    print("-" * 60)
    print("Read rows as 'Row Seed' win % against 'Column Seed'.")

if __name__ == "__main__":
    generate_seed_matrix()