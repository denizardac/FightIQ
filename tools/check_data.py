import json, sys
sys.stdout.reconfigure(encoding='utf-8')

with open('data/3_results.json', encoding='utf-8') as f:
    results = json.load(f)

with open('data/2_data_final.json', encoding='utf-8') as f:
    raw = json.load(f)

with open('data/4_parlays.json', encoding='utf-8') as f:
    parlays = json.load(f)

# Build record + stats lookup from raw data
records = {}
raw_stats = {}
market_data = {}
for fight in raw:
    fighters = fight.get('fighters', [])
    stats_list = fight.get('stats', [{}, {}])
    for i, ds in enumerate(fight.get('deep_stats', [])):
        if not isinstance(ds, dict): continue
        name = ds.get('name', '')
        w = ds.get('wins', 0) or 0
        l = ds.get('losses', 0) or 0
        d = ds.get('draws', 0) or 0
        if name:
            records[name] = f'{w}-{l}-{d}'
            raw_stats[name] = ds
    md = fight.get('market_data', {})
    if fighters and isinstance(md, dict):
        market_data[f"{fighters[0]} vs {fighters[1]}"] = md

print("=" * 60)
print("VERSUS CARD DATA AUDIT")
print("=" * 60)
for item in results:
    m = item['matchup']
    brain = item.get('fight_brain_output', {})
    sp = brain.get('spotlight_stats', {})
    pred = brain.get('prediction', {})
    betting = brain.get('betting_angles', {})

    if not sp:
        print(f"[MISSING SPOTLIGHT] {m}")
        continue

    f_names = list(sp.keys())
    print(f"\n{m}")
    print(f"  Prediction: {pred.get('winner')} via {pred.get('method')} (conf:{pred.get('confidence')})")
    for fname in f_names:
        stats = sp[fname]
        rec_actual = records.get(fname, 'DB not found')
        print(f"  {fname}:")
        print(f"    Record (DB): {rec_actual}")
        print(f"    AI Scores: power={stats.get('power')} grappling={stats.get('grappling')} stamina={stats.get('stamina')} chin={stats.get('chin')} technique={stats.get('technique')}")
        print(f"    One-liner: {stats.get('one_liner')}")

print("\n" + "=" * 60)
print("TICKET DATA AUDIT (Odds vs Real Market)")
print("=" * 60)
for slip_key in ['safe_slip', 'violence_slip', 'value_slip']:
    print(f"\n{slip_key.upper()}:")
    for p in parlays.get(slip_key, []):
        fight = p.get('fight', '')
        pick = p.get('pick', '')
        odds = p.get('odds', 0)
        # Find real market odds for this fight
        md = market_data.get(fight, {})
        betist_odds = md.get('betist_odds', {})
        print(f"  [{fight}] {pick} @ {odds}")
        if betist_odds:
            print(f"    Betist available: {list(betist_odds.keys())[:3]}")
        elif md:
            print(f"    Market keys: {list(md.keys())}")
        else:
            print(f"    No market data found for this fight name")
