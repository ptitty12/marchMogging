from flask import Flask, jsonify, render_template
import pandas as pd
import json
import random
import os
from utils.scoreBracket import score_roll_vs_actual 

app = Flask(__name__)

# --- Configuration & Data Loading ---
OUTCOME_PATH = 'lastYearOutcome.json'
compactResults = r"utils\MNCAATourneyCompactResults.csv"
tourneySeeds = r"utils\MNCAATourneySeeds.csv"

# Load static outcome for scoring
with open(OUTCOME_PATH, 'r') as f:
    last_year_data = json.load(f)

def build_matrices():
    print("Building historical matrices from raw data...")
    try:
        results = pd.read_csv(compactResults)
        seeds = pd.read_csv(tourneySeeds)
        
        seeds['SeedNum'] = seeds['Seed'].apply(lambda x: int(x[1:3]))
        df = results[['Season', 'WTeamID', 'LTeamID']].copy()
        
        # Merge Winner Seeds
        df = df.merge(seeds[['Season', 'TeamID', 'SeedNum']], left_on=['Season', 'WTeamID'], right_on=['Season', 'TeamID'])
        df.rename(columns={'SeedNum': 'WSeed'}, inplace=True)
        df.drop('TeamID', axis=1, inplace=True)
        
        # Merge Loser Seeds
        df = df.merge(seeds[['Season', 'TeamID', 'SeedNum']], left_on=['Season', 'LTeamID'], right_on=['Season', 'TeamID'])
        df.rename(columns={'SeedNum': 'LSeed'}, inplace=True)
        df.drop('TeamID', axis=1, inplace=True)
        
        # Aggregate Win Rate and Game Count
        df_winners = pd.DataFrame({'TeamSeed': df['WSeed'], 'OpponentSeed': df['LSeed'], 'Win': 1})
        df_losers = pd.DataFrame({'TeamSeed': df['LSeed'], 'OpponentSeed': df['WSeed'], 'Win': 0})
        all_matchups = pd.concat([df_winners, df_losers], ignore_index=True)
        
        stats = all_matchups.groupby(['TeamSeed', 'OpponentSeed']).agg(
            WinRate=('Win', 'mean'),
            GamesPlayed=('Win', 'count')
        ).reset_index()
        
        win_matrix = stats.pivot(index='TeamSeed', columns='OpponentSeed', values='WinRate').fillna('-')
        count_matrix = stats.pivot(index='TeamSeed', columns='OpponentSeed', values='GamesPlayed').fillna(0)
        
        # Convert index/columns to strings for JSON serialization
        win_matrix.columns = win_matrix.columns.astype(str)
        win_matrix.index = win_matrix.index.astype(str)
        count_matrix.columns = count_matrix.columns.astype(str)
        count_matrix.index = count_matrix.index.astype(str)
        
        return win_matrix, count_matrix
    except Exception as e:
        print(f"Error building matrices: {e}")
        return None, None

win_matrix, count_matrix = build_matrices()

# --- Simulation Logic ---

def get_win_probability(seed1, seed2):
    if seed1 == seed2:
        return 0.50
    try:
        val = win_matrix.loc[str(seed1), str(seed2)]
        if pd.isna(val) or val == '-':
            prob = 0.50 + ((seed2 - seed1) * 0.03)
        else:
            prob = float(val)
    except:
        prob = 0.50 + ((seed2 - seed1) * 0.03)
    return max(0.01, min(0.99, prob))

def load_teams():
    with open('teams.json', 'r') as f:
        return json.load(f)

def generate_starting_field():
    regions_data = load_teams()
    base_order = [1, 16, 8, 9, 5, 12, 4, 13, 6, 11, 3, 14, 7, 10, 2, 15]
    regions_order = ['East', 'West', 'South', 'Midwest']
    
    field = []
    team_id = 1
    for region in regions_order:
        for seed in base_order:
            field.append({
                "id": team_id,
                "name": regions_data[region][str(seed)],
                "seed": seed,
                "region": region
            })
            team_id += 1
    return field

# --- Routes ---

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/matrix')
def get_matrix():
    """Missing route that caused the 404"""
    if win_matrix is None or count_matrix is None:
        return jsonify({"error": "Matrices not initialized"}), 500
    return jsonify({
        "win_rates": win_matrix.to_dict(),
        "counts": count_matrix.to_dict()
    })

@app.route('/api/bracket')
def simulate_bracket():
    current_round = generate_starting_field()
    all_rounds_data = [current_round]

    for r in range(6):
        next_round = []
        for i in range(0, len(current_round), 2):
            t1, t2 = current_round[i], current_round[i+1]
            prob = get_win_probability(t1['seed'], t2['seed'])
            winner = t1 if random.random() < prob else t2
            
            t1['isWinner'] = (winner['id'] == t1['id'])
            t2['isWinner'] = (winner['id'] == t2['id'])
            
            next_team = winner.copy()
            next_team['isWinner'] = False
            next_round.append(next_team)
            
        all_rounds_data.append(next_round)
        current_round = next_round

    # Scoring
    score, breakdown = score_roll_vs_actual(all_rounds_data, last_year_data)

    response_data = {
        "bracket": all_rounds_data,
        "score_data": {
            "total_score": score,
            "breakdown": breakdown
        }
    }

    with open('currentRoll.json', "w") as json_file:
        json.dump(response_data, json_file)

    return jsonify(response_data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5003, debug=False)