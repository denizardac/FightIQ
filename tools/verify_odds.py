import json, sys
sys.stdout.reconfigure(encoding='utf-8')

with open('data/2_data_with_odds.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

betist = bfo = none = 0
for fight in data:
    f1, f2 = fight['fighters']
    source = fight.get('odds_source_primary', '?')
    conf = fight.get('odds_confidence', '?')
    md = fight.get('market_data', {})
    ml = md.get('Moneyline', md.get('moneyline', {}))
    ml_summary = []
    if ml:
        for k, v in ml.items():
            if isinstance(v, dict):
                ml_summary.append(f"{k}={v.get('decimal','?')}d")
    m_count = len(md.keys()) if md else 0
    
    icon = "OK" if 'Betist' in str(source) else ("BFO" if 'BestFight' in str(source) else "FAIL")
    print(f"[{icon}] {f1} vs {f2} | Markets:{m_count} | ML: {' / '.join(ml_summary) if ml_summary else 'NONE'}")
    
    if 'Betist' in str(source): betist += 1
    elif 'BestFight' in str(source): bfo += 1
    else: none += 1

print(f"\nSUMMARY: {len(data)} fights | Betist={betist} BFO={bfo} None={none}")
