from flask import Flask, jsonify, render_template
import pandas as pd
import json
import random

app = Flask(__name__)

# Process raw Kaggle data on startup to get both win rates AND counts
def build_matrices():
    try:
        results = pd.read_csv('MNCAATourneyCompactResults.csv')
        seeds = pd.read_csv('MNCAATourneySeeds.csv')
    except FileNotFoundError:
        print("Error: Missing Kaggle CSV files in root directory.")
        return None, None

    # Clean and merge
    seeds['SeedNum'] = seeds['Seed'].apply(lambda x: int(x[1:3]))
    
    df = results[['Season', 'WTeamID', 'LTeamID']].copy()
    df = df.merge(seeds[['Season', 'TeamID', 'SeedNum']], left_on=['Season', 'WTeamID'], right_on=['Season', 'TeamID'])
    df.rename(columns={'SeedNum': 'WSeed'}, inplace=True)
    df.drop('TeamID', axis=1, inplace=True)
    
    df = df.merge(seeds[['Season', 'TeamID', 'SeedNum']], left_on=['Season', 'LTeamID'], right_on=['Season', 'TeamID'])
    df.rename(columns={'SeedNum': 'LSeed'}, inplace=True)
    df.drop('TeamID', axis=1, inplace=True)
    
    # Calculate both perspectives
    df_winners = pd.DataFrame({'TeamSeed': df['WSeed'], 'OpponentSeed': df['LSeed'], 'Win': 1})
    df_losers = pd.DataFrame({'TeamSeed': df['LSeed'], 'OpponentSeed': df['WSeed'], 'Win': 0})
    all_matchups = pd.concat([df_winners, df_losers], ignore_index=True)
    
    # Aggregate Win Rate and Game Count
    stats = all_matchups.groupby(['TeamSeed', 'OpponentSeed']).agg(
        WinRate=('Win', 'mean'),
        GamesPlayed=('Win', 'count')
    ).reset_index()
    
    win_matrix = stats.pivot(index='TeamSeed', columns='OpponentSeed', values='WinRate').fillna('-')
    count_matrix = stats.pivot(index='TeamSeed', columns='OpponentSeed', values='GamesPlayed').fillna(0)
    
    # Convert index/columns to strings so JSON serialization handles them perfectly
    win_matrix.columns = win_matrix.columns.astype(str)
    win_matrix.index = win_matrix.index.astype(str)
    count_matrix.columns = count_matrix.columns.astype(str)
    count_matrix.index = count_matrix.index.astype(str)
    
    return win_matrix, count_matrix

win_matrix, count_matrix = build_matrices()

# --- HELPERS ---
def get_win_probability(s1, s2):
    try:
        val = win_matrix.loc[str(s1), str(s2)]
        prob = float(val) if val != '-' else 0.50 + ((s2 - s1) * 0.03)
    except:
        prob = 0.50 + ((s2 - s1) * 0.03)
# --- Simulation Logic ---

# --- HELPERS ---
def get_win_probability(s1, s2):
    try:
        val = win_matrix.loc[str(seed1), str(seed2)]
        if pd.isna(val) or val == '-':
            prob = 0.50 + ((seed2 - seed1) * 0.03)
        else:
            prob = float(val)
    except KeyError:
        prob = 0.50 + ((seed2 - seed1) * 0.03)
    return max(0.01, min(0.99, prob))

def generate_starting_field():
    with open('teams.json', 'r') as f:
        regions_data = json.load(f)
    base_order = [1, 16, 8, 9, 5, 12, 4, 13, 6, 11, 3, 14, 7, 10, 2, 15]
    field, team_id = [], 1
    for region in ['East', 'West', 'South', 'Midwest']:
        for seed in base_order:
            field.append({"id": team_id, "name": regions_data[region][str(seed)], "seed": seed, "region": region})
            team_id += 1
    return field

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/matrix')
def get_matrix():
    # Send both matrices back to the frontend
    return jsonify({
        "win_rates": win_matrix.to_dict() if win_matrix is not None else {},
        "counts": count_matrix.to_dict() if count_matrix is not None else {}
    })

@app.route('/api/bracket')
def simulate_bracket():
    current_round = generate_starting_field()
    all_rounds_data = [current_round]
    for r in range(6):
        next_round = []
        for i in range(0, len(current_round), 2):
            t1 = current_round[i]
            t2 = current_round[i+1]
            
            prob = get_win_probability(t1['seed'], t2['seed'])
            winner = t1 if random.random() < prob else t2
            
            t1['isWinner'] = (winner['id'] == t1['id'])
            t2['isWinner'] = (winner['id'] == t2['id'])
            
            next_team = winner.copy()
            next_team['isWinner'] = False
            next_round.append(next_team)
            
        all_rounds_data.append(next_round)
        current_round = next_round

    return jsonify(all_rounds_data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5003, debug=False)