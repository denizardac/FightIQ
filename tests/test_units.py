"""
Unit tests for pure core helpers (no network, no API keys).

Run:  pytest tests/test_units.py -v
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.naming import (
    safe_filename,
    safe_filename_lower,
    versus_basename,
    radar_basename,
    card_basename,
)
from core.fighter_rating import compute_streaks
from core.parlay_logic import pick_matches_winner, combined_odds, trim_slip
from core.odds_converter import american_to_decimal

# Import scorecard scoring helpers (pure, no I/O)
import importlib.util as _ilu
_sc_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "modules", "_14_scorecard.py")
_spec = _ilu.spec_from_file_location("_14_scorecard", _sc_path)
scorecard = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(scorecard)


# ---------- naming ----------

def test_safe_filename_apostrophe():
    assert safe_filename("Casey O'Neill") == "Casey_ONeill"


def test_safe_filename_hyphen():
    assert safe_filename("Kai Kara-France") == "Kai_KaraFrance"


def test_safe_filename_accents():
    assert safe_filename("José Aldo") == "Jose_Aldo"


def test_safe_filename_empty():
    assert safe_filename("") == ""
    assert safe_filename(None) == ""


def test_safe_filename_multiple_spaces():
    assert safe_filename("Jon  Jones") == "Jon_Jones"


def test_basenames():
    assert versus_basename("A B", "C D") == "Versus_A_B_vs_C_D.png"
    assert radar_basename("A B", "C D") == "Radar_A_B_vs_C_D.png"
    assert card_basename("A B") == "Card_A_B.png"


def test_safe_filename_lower():
    assert safe_filename_lower("Jon Jones") == "jon_jones"


# ---------- streaks ----------

def test_streaks_win_streak():
    assert compute_streaks(["win", "win", "loss", "win", "win"]) == (2, 0)


def test_streaks_loss_streak():
    assert compute_streaks(["loss", "loss", "win"]) == (0, 2)


def test_streaks_all_wins():
    assert compute_streaks(["win"] * 5) == (5, 0)


def test_streaks_empty_and_invalid():
    assert compute_streaks([]) == (0, 0)
    assert compute_streaks(None) == (0, 0)
    assert compute_streaks(["nc", "win"]) == (0, 0)


# ---------- parlay logic ----------

def test_pick_matches_winner_full_name():
    assert pick_matches_winner("Jon Jones ML", "Jon Jones", "Jon Jones", "Stipe Miocic")


def test_pick_matches_winner_last_name():
    assert pick_matches_winner("Costa ML", "Melquizael Costa", "Melquizael Costa", "Other Guy")


def test_pick_matches_winner_wrong_fighter():
    assert not pick_matches_winner("Stipe Miocic ML", "Jon Jones", "Jon Jones", "Stipe Miocic")


def test_combined_odds():
    legs = [{"odds": 1.5}, {"odds": 2.0}]
    assert combined_odds(legs) == 3.0


def test_combined_odds_skips_invalid():
    legs = [{"odds": 1.5}, {"odds": None}, {"odds": "bad"}]
    assert combined_odds(legs) == 1.5


def test_trim_slip():
    legs = [{"pick": str(i)} for i in range(10)]
    assert len(trim_slip(legs, max_legs=3)) == 3


# ---------- odds converter ----------

def test_american_to_decimal_plus():
    assert abs(american_to_decimal(150) - 2.5) < 0.01


def test_american_to_decimal_minus():
    assert abs(american_to_decimal(-200) - 1.5) < 0.01


# ---------- scorecard (prediction accuracy) ----------

def test_normalize_method():
    assert scorecard.normalize_method("KO/TKO Punch") == "KO"
    assert scorecard.normalize_method("SUB Rear-Naked Choke") == "SUB"
    assert scorecard.normalize_method("U-DEC") == "DEC"
    assert scorecard.normalize_method("Decision - Unanimous") == "DEC"
    assert scorecard.normalize_method("") == "OTHER"


def test_names_match():
    assert scorecard._names_match("Jon Jones", "jon jones")
    assert scorecard._names_match("Costa", "Melquizael Costa")
    assert not scorecard._names_match("Jon Jones", "Stipe Miocic")


def test_find_prediction_reversed_order():
    preds = [{"f1": "Jon Jones", "f2": "Stipe Miocic", "matchup": "Jon Jones vs Stipe Miocic",
              "winner": "Jon Jones", "method": "KO"}]
    # Live Wire lists winner first, which may be either fighter
    result = {"winner": "Stipe Miocic", "loser": "Jon Jones", "method": "U-DEC"}
    assert scorecard.find_prediction_for(result, preds) is preds[0]


def test_score_one_winner_and_method_published():
    """Method credit ONLY when the published bet was a method prop that hit."""
    pred = {"matchup": "A vs B", "winner": "Jon Jones", "method": "KO", "confidence": 8}
    result = {"winner": "Jon Jones", "loser": "B", "method": "KO/TKO Punch"}
    pub = {"bet": "Jon Jones by KO/TKO", "bet_type": "ko"}
    row = scorecard.score_one(result, pred, published=pub)
    assert row["winner_correct"] is True
    assert row["method_correct"] is True


def test_score_one_no_published_method_no_credit():
    """Internal method prediction without a published method bet gets NO credit."""
    pred = {"matchup": "A vs B", "winner": "Jon Jones", "method": "KO", "confidence": 8}
    result = {"winner": "Jon Jones", "loser": "B", "method": "KO/TKO Punch"}
    row = scorecard.score_one(result, pred, published={"bet": "Jon Jones ML", "bet_type": "ml"})
    assert row["winner_correct"] is True
    assert row["method_correct"] is False  # ML bet published — no method claim allowed


def test_score_one_winner_wrong():
    pred = {"matchup": "A vs B", "winner": "Jon Jones", "method": "KO", "confidence": 8}
    result = {"winner": "Stipe Miocic", "loser": "Jon Jones", "method": "U-DEC"}
    row = scorecard.score_one(result, pred)
    assert row["winner_correct"] is False
    assert row["method_correct"] is False


def test_score_method_not_credited_when_winner_wrong():
    # Right method category but wrong winner must NOT count as method_correct
    pred = {"matchup": "Max Holloway vs Ilia Topuria", "winner": "Max Holloway",
            "method": "Dec", "confidence": 6}
    result = {"winner": "Ilia Topuria", "loser": "Max Holloway", "method": "U-DEC"}
    row = scorecard.score_one(result, pred)
    assert row["winner_correct"] is False
    assert row["method_correct"] is False


def test_accuracy_stats():
    rows = [
        {"winner_correct": True, "method_correct": True},
        {"winner_correct": True, "method_correct": False},
        {"winner_correct": False, "method_correct": False},
        {"winner_correct": True, "method_correct": False},
    ]
    stats = scorecard.accuracy_stats(rows)
    assert stats == {"correct": 3, "total": 4, "method_correct": 1, "pct": 75.0}


def test_accuracy_stats_empty():
    assert scorecard.accuracy_stats([]) == {"correct": 0, "total": 0, "method_correct": 0, "pct": 0.0}


# ---------- fight_brain JSON extraction ----------

_fb_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "modules", "_05_fight_brain.py")


def _load_extract_json():
    import importlib.util
    # Import only the pure helper without triggering module-level API client init
    # by reading the function source. Simpler: exec the file with a fake genai.
    # We instead just import the symbol lazily; _05 needs GEMINI key at import.
    # So parse the function out via a minimal namespace.
    src = open(_fb_path, encoding="utf-8").read()
    start = src.index("def extract_json(")
    end = src.index("\n\n", src.index("return t[start:]"))
    ns = {}
    exec(src[start:end], ns)
    return ns["extract_json"]


extract_json = _load_extract_json()


def test_extract_json_extra_data():
    import json as _j
    raw = '{"a": 1, "b": "text with } brace"}\n\ntrailing commentary'
    assert _j.loads(extract_json(raw)) == {"a": 1, "b": "text with } brace"}


def test_extract_json_markdown_fence():
    import json as _j
    raw = '```json\n{"x": [1,2], "y": {"z": 3}}\n```'
    assert _j.loads(extract_json(raw)) == {"x": [1, 2], "y": {"z": 3}}


def test_extract_json_escaped_quotes():
    import json as _j
    raw = '{"reason": "He said \\"hi\\"", "n": 5} garbage'
    assert _j.loads(extract_json(raw)) == {"reason": 'He said "hi"', "n": 5}


# ---------- betting tweet composition ----------

from core.prediction_validate import _compose_betting_tweet


def test_betting_tweet_no_midword_cut():
    kf = ("Holloway's relentless pace and iron chin will outlast McGregor's early "
          "burst and cruise to a clear unanimous decision on the scorecards tonight for sure")
    t = _compose_betting_tweet("Over_2.5", " @ 2.7", kf)
    assert len(t) <= 280
    assert t.endswith("#UFC #Betting")
    # The character right before the ellipsis/suffix must not be a lone cut word letter
    assert " a #UFC" not in t and " a…" not in t


def test_betting_tweet_short_untouched():
    t = _compose_betting_tweet("Cory Sandhagen ML", " @ 1.69", "Wins the range battle.")
    assert t == "Best bet: Cory Sandhagen ML @ 1.69. Wins the range battle. #UFC #Betting"


def test_betting_tweet_pretty_market_label():
    from core.prediction_validate import pretty_bet_label
    assert pretty_bet_label("Over_2.5") == "Over 2.5 Rounds"
    assert pretty_bet_label("Under_1.5") == "Under 1.5 Rounds"
    assert pretty_bet_label("Jon Jones ML") == "Jon Jones ML"
    t = _compose_betting_tweet("Over_2.5", " @ 2.7", "High output fight.")
    assert "Over_2.5" not in t and "Over 2.5 Rounds @ 2.7" in t


# ---------- odds hallucination guard (Phase 1) ----------

from core.odds_resolve import resolve_pick_odds

_ML_ONLY_BOARD = {
    "moneyline": {
        "Jon Jones": {"decimal": 1.65, "american": "-153"},
        "Stipe Miocic": {"decimal": 2.30, "american": "+130"},
    }
}


def test_ai_invented_prop_price_rejected():
    """AI says 'Jones by KO @ 4.4' but board only has ML -> must NOT return 4.4."""
    dec, label, ok = resolve_pick_odds(
        "Jon Jones by KO/TKO", "ko", _ML_ONLY_BOARD,
        "Jon Jones", "Stipe Miocic", "Jon Jones", "KO", ai_odds=4.4,
    )
    assert dec != 4.4
    # Falls back to the REAL ML price
    assert ok and dec == 1.65 and "ML" in label


def test_ai_price_matching_board_within_tolerance_accepted():
    """AI quotes 1.66 (within 5% of board ML 1.65) -> board price used."""
    dec, label, ok = resolve_pick_odds(
        "Jones moneyline", "ml", _ML_ONLY_BOARD,
        "Jon Jones", "Stipe Miocic", "Jon Jones", "Dec", ai_odds=1.66,
    )
    assert ok and dec == 1.65


def test_no_board_at_all_returns_unavailable():
    dec, label, ok = resolve_pick_odds(
        "Jon Jones by KO/TKO", "ko", {},
        "Jon Jones", "Stipe Miocic", "Jon Jones", "KO", ai_odds=4.4,
    )
    assert not ok and dec is None


def test_non_winner_prop_without_board_line_unavailable():
    """Over/Under with no totals on board and invented AI price -> unavailable."""
    dec, label, ok = resolve_pick_odds(
        "Over 2.5 Rounds", "over", _ML_ONLY_BOARD,
        "Jon Jones", "Stipe Miocic", "Jon Jones", "Dec", ai_odds=3.9,
    )
    assert not ok and dec is None


# ---------- Live Wire published-pick honesty (Phase 2) ----------

import importlib.util as _ilu2
_lw_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "modules", "_13_live_wire.py")
_lw_spec = _ilu2.spec_from_file_location("_13_live_wire", _lw_path)
livewire = _ilu2.module_from_spec(_lw_spec)
_lw_spec.loader.exec_module(livewire)


def test_outcome_no_published_pick():
    out = livewire.evaluate_published_pick(None, {"winner": "A", "loser": "B", "method": "KO"})
    assert out["category"] == "NO_PICK"


def test_outcome_full_win_method_prop():
    pub = {"bet": "Jon Jones by KO/TKO", "bet_type": "ko", "predicted_winner": "Jon Jones"}
    res = {"winner": "Jon Jones", "loser": "Stipe", "method": "KO/TKO Punch", "round": 1, "time": "2:00"}
    out = livewire.evaluate_published_pick(pub, res)
    assert out["category"] == "FULL_WIN" and out["bet_won"] is True


def test_outcome_winner_only_when_method_missed():
    """Published 'by KO' but fight ended by decision -> WINNER_ONLY, no CASH IT."""
    pub = {"bet": "Luke Riley by KO/TKO", "bet_type": "ko", "predicted_winner": "Luke Riley"}
    res = {"winner": "Luke Riley", "loser": "Kai Kamaka", "method": "U-DEC", "round": 3, "time": "5:00"}
    out = livewire.evaluate_published_pick(pub, res)
    assert out["category"] == "WINNER_ONLY"
    assert out["bet_won"] is False


def test_outcome_loss_on_wrong_winner():
    pub = {"bet": "Nikita Krylov by KO/TKO", "bet_type": "ko", "predicted_winner": "Nikita Krylov"}
    res = {"winner": "Robert Whittaker", "loser": "Nikita Krylov", "method": "KO", "round": 1, "time": "3:00"}
    out = livewire.evaluate_published_pick(pub, res)
    assert out["category"] == "LOSS"


def test_outcome_over_bet_settled_by_duration():
    """Over 2.5 published; fight ends R1 KO -> the bet LOST even though we might have the winner."""
    pub = {"bet": "Over 2.5 Rounds", "bet_type": "over", "predicted_winner": ""}
    res = {"winner": "Damian Pinas", "loser": "Cesar Almeida", "method": "KO", "round": 1, "time": "4:30"}
    out = livewire.evaluate_published_pick(pub, res)
    assert out["bet_won"] is False and out["category"] == "LOSS"


def test_outcome_over_bet_wins_on_decision():
    pub = {"bet": "Over 2.5 Rounds", "bet_type": "over", "predicted_winner": ""}
    res = {"winner": "A", "loser": "B", "method": "U-DEC", "round": 3, "time": "5:00"}
    out = livewire.evaluate_published_pick(pub, res)
    assert out["bet_won"] is True and out["category"] == "FULL_WIN"


def test_fallback_reaction_never_claims_without_pick():
    txt = livewire._fallback_reaction("A", "B", "KO", {"category": "NO_PICK"})
    assert "called" not in txt.lower() and "pick" not in txt.lower()


# ---------- ticket surname + pick card helpers (Phases 4-5) ----------

def _load_module(relpath, name):
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), relpath)
    spec = _ilu2.spec_from_file_location(name, path)
    mod = _ilu2.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_surname_skips_generational_suffix():
    tickets = _load_module(os.path.join("modules", "_06b_ticket_generator.py"), "_06b")
    assert tickets.surname("Kai Kamaka III") == "Kamaka"
    assert tickets.surname("Luke Riley") == "Riley"
    assert tickets.surname("Roberto Soldic Jr.") == "Soldic"
    assert tickets.format_match_name("Luke Riley vs Kai Kamaka III") == "Riley vs Kamaka"


def test_scrub_internal_terms():
    from core.prediction_validate import scrub_internal_terms
    t = "With a 96.0 ranking proxy and reach. injury_news_flag set. finish_rate_pct 52.9."
    out = scrub_internal_terms(t)
    assert "ranking proxy" not in out.lower()
    assert "injury_news_flag" not in out
    assert "finish_rate_pct" not in out


def test_style_one_liner_exclude():
    from core.fighter_rating import style_one_liner
    scout = {"SLpM": "6.9", "Str_Acc": "48%", "SApM": "4.5", "Str_Def": "58%",
             "TD_Avg": "0.2", "TD_Acc": "40%", "TD_Def": "80%", "Sub_Avg": "0.3"}
    deep = {"ko_rate": 30, "sub_rate": 5, "wins": 27, "total_fights": 36,
            "avg_fight_time_sec": 900}
    tag1 = style_one_liner(scout, deep)
    tag2 = style_one_liner(scout, deep, exclude=tag1)
    assert tag1.lower() != tag2.lower()
