import json

def score_roll_vs_actual(roll_data, actual_data):
    ROUND_SCORES = [10, 20, 40, 80, 160, 320]
    total_score = 0
    results_breakdown = {}

    for r_idx, points_per_game in enumerate(ROUND_SCORES):
        if r_idx >= len(roll_data) or r_idx >= len(actual_data):
            break
            
        pred_winners = [t for t in roll_data[r_idx] if t.get('isWinner')]
        actual_winners = [t for t in actual_data[r_idx] if t.get('isWinner')]
        
        # TWEAK: If we are in the Final Four (index 4) or later, 
        # we ignore the region and only match on seed.
        if r_idx >= 4:
            actual_slots = [t['seed'] for t in actual_winners]
        else:
            actual_slots = [(t['seed'], t['region']) for t in actual_winners]
        
        round_correct_count = 0
        for p_team in pred_winners:
            # Match logic
            p_match_val = p_team['seed'] if r_idx >= 4 else (p_team['seed'], p_team['region'])
            
            if p_match_val in actual_slots:
                round_correct_count += 1
                actual_slots.remove(p_match_val)
        
        round_total = round_correct_count * points_per_game
        total_score += round_total
        results_breakdown[f"Round {r_idx + 1}"] = {"points": round_total}
        
    return total_score, results_breakdown

# --- CORRECTED RUN BLOCK ---
# 1. Load the actual data from the file
#with open('lastYearOutcome.json', 'r') as f:
    #lastYearData = json.load(f)

# 2. Load your current roll (or use the variable if it's already a list)
# If currentRoll is already the list of lists you pasted:
# 1. Load the actual data from the file
#with open('currentRoll.json', 'r') as f:
    #rollData = json.load(f)
# 3. Run the score
#score, breakdown = score_roll_vs_actual(rollData, lastYearData)

#print(f"Total Score: {score}")
#print("Breakdown:", json.dumps(breakdown, indent=2))