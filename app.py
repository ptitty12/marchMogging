from flask import Flask, jsonify, render_template
import pandas as pd
import json
import random
import sqlite3
import os
from datetime import datetime
from utils.scoreBracket import score_roll_vs_actual 

app = Flask(__name__)

basedir = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(basedir, 'leaderboard.db')
OUTCOME_PATH = os.path.join(basedir, 'lastYearOutcome.json')
COMPACT_RESULTS = os.path.join(basedir, 'utils', 'MNCAATourneyCompactResults.csv')
TOURNEY_SEEDS = os.path.join(basedir, 'utils', 'MNCAATourneySeeds.csv')

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS leaderboard 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, score INTEGER, bracket_json TEXT, timestamp DATETIME)''')
    conn.commit()
    conn.close()

init_db()

try:
    with open(OUTCOME_PATH, 'r') as f:
        last_year_data = json.load(f)
except:
    last_year_data = []

def build_matrices():
    try:
        results = pd.read_csv(COMPACT_RESULTS)
        seeds = pd.read_csv(TOURNEY_SEEDS)
        seeds['SeedNum'] = seeds['Seed'].apply(lambda x: int(x[1:3]))
        df = results[['Season', 'WTeamID', 'LTeamID']].copy()
        df = df.merge(seeds[['Season', 'TeamID', 'SeedNum']], left_on=['Season', 'WTeamID'], right_on=['Season', 'TeamID'])
        df.rename(columns={'SeedNum': 'WSeed'}, inplace=True)
        df.drop('TeamID', axis=1, inplace=True)
        df = df.merge(seeds[['Season', 'TeamID', 'SeedNum']], left_on=['Season', 'LTeamID'], right_on=['Season', 'TeamID'])
        df.rename(columns={'SeedNum': 'LSeed'}, inplace=True)
        df.drop('TeamID', axis=1, inplace=True)
        
        stats = pd.concat([
            pd.DataFrame({'TeamSeed': df['WSeed'], 'OpponentSeed': df['LSeed'], 'Win': 1}),
            pd.DataFrame({'TeamSeed': df['LSeed'], 'OpponentSeed': df['WSeed'], 'Win': 0})
        ]).groupby(['TeamSeed', 'OpponentSeed']).agg(WinRate=('Win', 'mean'), GamesPlayed=('Win', 'count')).reset_index()
        
        win_matrix = stats.pivot(index='TeamSeed', columns='OpponentSeed', values='WinRate').fillna('-')
        count_matrix = stats.pivot(index='TeamSeed', columns='OpponentSeed', values='GamesPlayed').fillna(0)
        win_matrix.columns = win_matrix.columns.astype(str)
        win_matrix.index = win_matrix.index.astype(str)
        return win_matrix, count_matrix
    except:
        return None, None

win_matrix, count_matrix = build_matrices()

def get_win_probability(s1, s2):
    try:
        val = win_matrix.loc[str(s1), str(s2)]
        return float(val) if val != '-' else 0.50 + ((s2 - s1) * 0.03)
    except:
        return 0.50 + ((s2 - s1) * 0.03)

def generate_starting_field():
    with open('teams.json', 'r') as f:
        data = json.load(f)
    
    base_order = [1, 16, 8, 9, 5, 12, 4, 13, 6, 11, 3, 14, 7, 10, 2, 15]
    field, team_id = [], 1
    
    # NEW ORDER: 
    # Index 0 & 1 (East/South) will meet in the Semifinals
    # Index 2 & 3 (West/Midwest) will meet in the Semifinals
    region_pairing = ['East', 'South', 'West', 'Midwest']
    
    for region in region_pairing:
        for seed in base_order:
            field.append({
                "id": team_id, 
                "name": data[region][str(seed)], 
                "seed": seed, 
                "region": region
            })
            team_id += 1
            
    return field

@app.route('/')
def home(): return render_template('index.html')

@app.route('/api/matrix')
def get_matrix(): return jsonify({"win_rates": win_matrix.to_dict(), "counts": count_matrix.to_dict()})

@app.route('/api/leaderboard')
def get_leaderboard():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT score, bracket_json, timestamp FROM leaderboard ORDER BY score DESC LIMIT 3")
    rows = c.fetchall()
    conn.close()
    return jsonify([{"score": r[0], "bracket": json.loads(r[1]), "date": r[2]} for r in rows])

@app.route('/api/bracket')
def simulate_bracket():
    current_round = generate_starting_field()
    all_rounds_data = [current_round]
    for r in range(6):
        next_round = []
        for i in range(0, len(current_round), 2):
            t1, t2 = current_round[i], current_round[i+1]
            winner = t1 if random.random() < get_win_probability(t1['seed'], t2['seed']) else t2
            t1['isWinner'], t2['isWinner'] = (winner['id'] == t1['id']), (winner['id'] == t2['id'])
            nt = winner.copy()
            nt['isWinner'] = False
            next_round.append(nt)
        all_rounds_data.append(next_round)
        current_round = next_round
    score, breakdown = score_roll_vs_actual(all_rounds_data, last_year_data)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO leaderboard (score, bracket_json, timestamp) VALUES (?, ?, ?)",
              (score, json.dumps(all_rounds_data), datetime.now().strftime("%Y-%m-%d %H:%M")))
    conn.commit()
    conn.close()
    return jsonify({"bracket": all_rounds_data, "score_data": {"total_score": score, "breakdown": breakdown}})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5003, debug=False)