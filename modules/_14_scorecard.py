"""
FightIQ Scorecard — prediction accuracy tracking.

Matches the AI's predictions (data/3_results.json) against the actual fight
results collected by Live Wire (data/live_wire_history.json), maintains an
all-time ledger (data/prediction_ledger.json), and produces a recap tweet
("We went 7/12 on winners this card — 63% all-time").

Design notes
------------
- The ledger is keyed by event name so re-running never double-counts.
- Recap posting is guarded by `recap_posted` in the ledger, so a second run
  on the same night will not spam a duplicate recap.
- Pure scoring (match_results / normalize_method / accuracy_stats) has NO
  side effects and is unit-tested in tests/test_units.py.

Usage:
    python modules/_14_scorecard.py            # update ledger + write recap file
    python modules/_14_scorecard.py --post     # also post recap to Twitter
    python modules/_14_scorecard.py --dry-run  # log recap, do not post
"""
import argparse
import json
import os
import sys
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.paths import get_data_path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

RESULTS_FILE = get_data_path("3_results.json")
LIVE_WIRE_HISTORY = get_data_path("live_wire_history.json")
CARD_FILE = get_data_path("1_card.json")
LEDGER_FILE = get_data_path("prediction_ledger.json")
RECAP_FILE = get_data_path("scorecard_ready.json")


# ==========================================
# PURE SCORING HELPERS (no I/O — unit tested)
# ==========================================

def normalize_method(method_str):
    """Collapse any method label to KO | SUB | DEC | OTHER."""
    if not method_str:
        return "OTHER"
    m = str(method_str).lower()
    if any(t in m for t in ("ko", "tko", "knockout", "punch", "kick", "elbow", "strikes")):
        # 'ko' also matches 'knockout'; guard against 'ko' inside unrelated words is unnecessary here
        return "KO"
    if any(t in m for t in ("sub", "choke", "armbar", "kimura", "guillotine",
                             "triangle", "rear-naked", "rear naked", "submission", "tap")):
        return "SUB"
    if any(t in m for t in ("dec", "decision")):
        return "DEC"
    return "OTHER"


def _norm_name(name):
    return "".join(ch for ch in str(name or "").lower() if ch.isalnum() or ch == " ").strip()


def _names_match(a, b):
    """True if two fighter names refer to the same person (last-name tolerant)."""
    na, nb = _norm_name(a), _norm_name(b)
    if not na or not nb:
        return False
    if na == nb or na in nb or nb in na:
        return True
    pa = [p for p in na.split() if len(p) > 2]
    pb = [p for p in nb.split() if len(p) > 2]
    # Share the (usually distinctive) last token
    return bool(pa and pb and pa[-1] == pb[-1])


def find_prediction_for(result, predictions):
    """Given an actual result {winner, loser}, find our prediction dict."""
    w, l = result.get("winner", ""), result.get("loser", "")
    for pred in predictions:
        f1, f2 = pred.get("f1", ""), pred.get("f2", "")
        pair = ((_names_match(w, f1) and _names_match(l, f2)) or
                (_names_match(w, f2) and _names_match(l, f1)))
        if pair:
            return pred
    return None


def score_one(result, prediction):
    """Return a per-fight scorecard row (or None if no matching prediction)."""
    if not prediction:
        return None
    predicted_winner = prediction.get("winner", "")
    actual_winner = result.get("winner", "")
    winner_correct = _names_match(predicted_winner, actual_winner)

    method_correct = (
        normalize_method(prediction.get("method")) == normalize_method(result.get("method"))
    )
    return {
        "matchup": prediction.get("matchup", f"{result.get('winner')} vs {result.get('loser')}"),
        "predicted_winner": predicted_winner,
        "actual_winner": actual_winner,
        "predicted_method": prediction.get("method", ""),
        "actual_method": result.get("method", ""),
        "confidence": prediction.get("confidence", 0),
        "winner_correct": winner_correct,
        "method_correct": bool(winner_correct and method_correct),
    }


def match_results(results, predictions):
    """Score every actual result against predictions. Returns list of rows."""
    rows = []
    for res in results:
        pred = find_prediction_for(res, predictions)
        row = score_one(res, pred)
        if row:
            rows.append(row)
    return rows


def accuracy_stats(rows):
    """Aggregate {correct, total, method_correct, pct}."""
    total = len(rows)
    correct = sum(1 for r in rows if r["winner_correct"])
    method_correct = sum(1 for r in rows if r["method_correct"])
    pct = round(100.0 * correct / total, 1) if total else 0.0
    return {"correct": correct, "total": total, "method_correct": method_correct, "pct": pct}


# ==========================================
# I/O + LEDGER
# ==========================================

def _load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def load_predictions():
    """Read 3_results.json into a flat list of prediction dicts."""
    raw = _load_json(RESULTS_FILE, [])
    preds = []
    for item in raw if isinstance(raw, list) else []:
        matchup = item.get("matchup", "")
        brain = item.get("fight_brain_output", {}) or {}
        pred = brain.get("prediction", {}) or {}
        if " vs " not in matchup or not pred.get("winner"):
            continue
        f1, f2 = matchup.split(" vs ", 1)
        preds.append({
            "matchup": matchup,
            "f1": f1.strip(),
            "f2": f2.strip(),
            "winner": pred.get("winner", ""),
            "method": pred.get("method", ""),
            "confidence": pred.get("confidence", 0),
        })
    return preds


def load_results():
    """Read live_wire_history.json into a list of {winner, loser, method}."""
    raw = _load_json(LIVE_WIRE_HISTORY, {})
    out = []
    if isinstance(raw, dict):
        for entry in raw.values():
            if isinstance(entry, dict) and entry.get("winner"):
                out.append(entry)
    return out


def _empty_ledger():
    return {"events": {}, "all_time": {"correct": 0, "total": 0, "method_correct": 0}}


def _recompute_all_time(ledger):
    at = {"correct": 0, "total": 0, "method_correct": 0}
    for ev in ledger["events"].values():
        at["correct"] += ev.get("correct", 0)
        at["total"] += ev.get("total", 0)
        at["method_correct"] += ev.get("method_correct", 0)
    at["pct"] = round(100.0 * at["correct"] / at["total"], 1) if at["total"] else 0.0
    ledger["all_time"] = at
    return ledger


def update_ledger(event_name, rows):
    """Insert/replace this event's scorecard in the persistent ledger.

    Returns (ledger, event_entry). Idempotent per event name.
    """
    ledger = _load_json(LEDGER_FILE, _empty_ledger())
    if "events" not in ledger:
        ledger = _empty_ledger()

    stats = accuracy_stats(rows)
    prior = ledger["events"].get(event_name, {})
    ledger["events"][event_name] = {
        "date": prior.get("date") or datetime.now().strftime("%Y-%m-%d"),
        "correct": stats["correct"],
        "total": stats["total"],
        "method_correct": stats["method_correct"],
        "pct": stats["pct"],
        "picks": rows,
        "recap_posted": prior.get("recap_posted", False),
    }
    _recompute_all_time(ledger)
    with open(LEDGER_FILE, "w", encoding="utf-8") as f:
        json.dump(ledger, f, indent=2, ensure_ascii=False)
    return ledger, ledger["events"][event_name]


def build_recap(event_name, event_entry, all_time):
    """Build the recap tweet + a highlight thread reply."""
    correct = event_entry["correct"]
    total = event_entry["total"]
    pct = event_entry["pct"]
    at_correct = all_time["correct"]
    at_total = all_time["total"]
    at_pct = all_time.get("pct", 0.0)

    verdict = "🎯" if pct >= 60 else ("📉" if pct < 40 else "📊")
    lead = (
        f"{verdict} FIGHTIQ SCORECARD — {event_name}\n\n"
        f"AI went {correct}/{total} on winners ({pct}%).\n"
        f"All-time: {at_correct}/{at_total} ({at_pct}%)\n"
        f"#UFC #MMA #FightIQ"
    )[:280]

    # Highlight the best correct calls (highest confidence hits)
    hits = sorted(
        [r for r in event_entry["picks"] if r["winner_correct"]],
        key=lambda r: r.get("confidence", 0),
        reverse=True,
    )[:3]
    reply = ""
    if hits:
        lines = ["✅ Called it:"]
        for h in hits:
            method_tag = " (method too)" if h["method_correct"] else ""
            lines.append(f"• {h['actual_winner']}{method_tag}")
        reply = "\n".join(lines)[:280]

    return lead, reply


def generate_scorecard(post=False, dry_run=False):
    """Main entry: score the latest event, update ledger, write recap, optionally post."""
    card = _load_json(CARD_FILE, {})
    event_name = card.get("event", "") or "Latest UFC Card"

    predictions = load_predictions()
    results = load_results()

    if not predictions:
        print("   ℹ️ No predictions found (3_results.json empty) — nothing to score.")
        return None
    if not results:
        print("   ℹ️ No fight results yet (live_wire_history.json empty) — nothing to score.")
        return None

    rows = match_results(results, predictions)
    if not rows:
        print("   ⚠️ No results matched any prediction (name mismatch?).")
        return None

    ledger, event_entry = update_ledger(event_name, rows)
    stats = accuracy_stats(rows)
    print(f"   📊 {event_name}: {stats['correct']}/{stats['total']} winners "
          f"({stats['pct']}%), method {stats['method_correct']}/{stats['total']}")
    print(f"   🏆 All-time: {ledger['all_time']['correct']}/{ledger['all_time']['total']} "
          f"({ledger['all_time'].get('pct', 0.0)}%)")

    lead, reply = build_recap(event_name, event_entry, ledger["all_time"])

    recap_payload = {
        "event": event_name,
        "generated": datetime.now().isoformat(),
        "lead": lead,
        "reply": reply,
        "stats": stats,
        "all_time": ledger["all_time"],
    }
    with open(RECAP_FILE, "w", encoding="utf-8") as f:
        json.dump(recap_payload, f, indent=2, ensure_ascii=False)
    print(f"   📁 Recap saved to {RECAP_FILE}")

    if post or dry_run:
        _post_recap(event_name, lead, reply, ledger, event_entry, dry_run=dry_run)

    return recap_payload


def _post_recap(event_name, lead, reply, ledger, event_entry, dry_run=False):
    if event_entry.get("recap_posted") and not dry_run:
        print("   ⏭️ Recap already posted for this event — skipping.")
        return
    try:
        from modules import _08_social_director as SD
    except ImportError as e:
        print(f"   ⚠️ Social Director unavailable: {e}")
        return

    try:
        director = SD.SocialDirector(dry_run=dry_run)
    except SystemExit:
        print("   ⚠️ Twitter not configured — cannot post recap.")
        return

    print(f"\n🐦 Posting scorecard recap for {event_name}...")
    lead_id = director.post_tweet(lead)
    if not lead_id:
        print("   ❌ Recap lead failed to post.")
        return
    if reply:
        director._sleep_between_posts(is_reply=True)
        director.post_tweet(reply, reply_to_id=lead_id)

    if not dry_run:
        event_entry["recap_posted"] = True
        with open(LEDGER_FILE, "w", encoding="utf-8") as f:
            json.dump(ledger, f, indent=2, ensure_ascii=False)
        print("   ✅ Recap posted and ledger marked.")


def main():
    parser = argparse.ArgumentParser(description="FightIQ Scorecard")
    parser.add_argument("--post", action="store_true", help="Post recap to Twitter")
    parser.add_argument("--dry-run", action="store_true", help="Log recap, do not post")
    args = parser.parse_args()

    print("--- 📊 FIGHTIQ SCORECARD (Prediction Accuracy) ---")
    generate_scorecard(post=args.post, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
