import json, sys
sys.stdout.reconfigure(encoding='utf-8')

with open('data/3_results.json', encoding='utf-8') as f:
    results = json.load(f)

for item in results:
    m = item['matchup']
    brain = item.get('fight_brain_output', {})
    tweets = brain.get('content_tweets', {})
    spot = brain.get('spotlight_content', '')
    print(f"{'='*60}")
    print(f"MATCHUP: {m}")
    print(f"{'='*60}")
    print(f"[SALI  ] {tweets.get('analysis_tweet','(yok)')}")
    print(f"[PERSEM] {tweets.get('violence_tweet','(yok)')}")
    print(f"[CUMARTE] {tweets.get('betting_tweet','(yok)')}")
    print(f"[CARSAM] {spot or '(yok)'}")
    print()
