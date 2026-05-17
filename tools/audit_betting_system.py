#!/usr/bin/env python3
"""
End-to-end audit: scraped odds → AI prompt → catalog → slips → sample outputs.
Writes: output/audit/odds_audit.json, output/audit/audit_report.txt
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.paths import get_data_path, get_output_path, VISUALS_DIR, PROJECT_ROOT
from core.market_catalog import catalog_bets, summarize_markets_for_prompt, select_best_bet
from core.prediction_validate import validate_and_unify

AUDIT_DIR = os.path.join(PROJECT_ROOT, "output", "audit")
os.makedirs(AUDIT_DIR, exist_ok=True)


def load_json(name):
    p = get_data_path(name)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def audit_markets(fights):
    """Per-fight: raw market_data keys + catalog options."""
    rows = []
    for fight in fights or []:
        fighters = fight.get("fighters", [])
        if len(fighters) != 2:
            continue
        f1, f2 = fighters[0], fighters[1]
        md = fight.get("market_data") or {}
        source = fight.get("odds_source_primary", fight.get("odds_confidence", "?"))
        conf = fight.get("odds_confidence", "?")

        raw_keys = list(md.keys()) if isinstance(md, dict) else []
        props = md.get("props") if isinstance(md, dict) else None
        prop_detail = {}
        if isinstance(props, dict):
            for pk, pv in props.items():
                if isinstance(pv, dict):
                    prop_detail[pk] = {k: v for k, v in pv.items()}

        ml = {}
        for k, v in (md.items() if isinstance(md, dict) else []):
            if str(k).lower() in ("moneyline", "kazanır", "1x2") and isinstance(v, dict):
                ml = dict(v)

        catalog = catalog_bets(md, f1, f2, f1, "Dec")
        catalog_list = [
            {"market": o.market, "label": o.label, "odds": o.odds, "type": o.bet_type}
            for o in catalog
        ]

        prompt_block = summarize_markets_for_prompt(md, f1, f2)

        rows.append({
            "matchup": f"{f1} vs {f2}",
            "odds_source": source,
            "odds_confidence": conf,
            "raw_market_keys": raw_keys,
            "moneyline_outcomes": ml,
            "props_nested": prop_detail,
            "catalog_option_count": len(catalog_list),
            "catalog_options": catalog_list,
            "ai_prompt_market_lines": prompt_block.split("\n") if prompt_block else [],
        })
    return rows


def audit_results(results):
    rows = []
    for item in results or []:
        m = item.get("matchup", "")
        brain = item.get("fight_brain_output", {})
        pred = brain.get("prediction", {})
        angles = brain.get("betting_angles", {})
        ctx = brain.get("market_context", {})
        tweets = brain.get("content_tweets", {})
        bars = brain.get("computed_ratings", {})

        rows.append({
            "matchup": m,
            "prediction": pred,
            "violence_score": brain.get("violence_score"),
            "safe_pick": angles.get("safe_pick"),
            "value_pick": angles.get("value_pick"),
            "violence_pick": angles.get("violence_pick"),
            "betting_tweet": tweets.get("betting_tweet"),
            "market_context": ctx,
            "bar_sample_f1": bars.get("fighter1") if bars else None,
            "bar_sample_f2": bars.get("fighter2") if bars else None,
        })
    return rows


def main():
    print("=" * 60)
    print("FIGHTIQ BETTING SYSTEM AUDIT")
    print("=" * 60)

    final = load_json("2_data_final.json")
    results = load_json("3_results.json")
    parlays = load_json("4_parlays.json")

    market_audit = audit_markets(final) if final else []
    brain_audit = audit_results(results) if results else []

    # Code reference (what scrapers TRY to get)
    code_capabilities = {
        "betist_primary": [
            "Any market returned in Betist API (type_title → market name)",
            "Normalized to Moneyline for Kazanır/1x2",
            "Other Turkish markets pass through as-is (rounds, method, etc.)",
        ],
        "bfo_secondary": [
            "Moneyline (fighter_a / fighter_b)",
            "method_of_victory: KO/TKO, Submission, Decision (from detail page scrape)",
            "total_rounds: Over_2.5, Under_2.5 (from detail page scrape)",
            "line_movement when available",
        ],
        "oddsportal_tertiary": [
            "Encrypted feed /feed/match-event/... (method + O/U when IP not blocked)",
            "Match discovery via DuckDuckGo + weight-class URL slugs",
        ],
        "the_odds_api": [
            "THE_ODDS_API_KEY in .env — UFC h2h from many books",
            "totals (O/U rounds) when books publish them for the fight",
        ],
        "action_network": [
            "actionnetwork.com/ufc/odds — averaged ML across US books (backup)",
        ],
        "ai_receives": [
            "Full market_data JSON in prompt",
            "summarize_markets_for_prompt() flat list (max 40 lines)",
            "scout_enrich fields: ranking_proxy, injury_news_flag, etc.",
            "matchup_context: reach, stance, momentum",
        ],
        "catalog_can_use": [
            "ml", "ko", "sub", "dec", "over", "under", "distance_yes", "distance_no", "other",
            "Only lines with valid decimal odds 1.01+",
        ],
    }

    out = {
        "code_capabilities": code_capabilities,
        "fights_with_markets": len(market_audit),
        "fights_with_brain": len(brain_audit),
        "market_audit": market_audit,
        "brain_audit": brain_audit,
        "parlays": parlays,
    }

    json_path = os.path.join(AUDIT_DIR, "odds_audit.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    txt_path = os.path.join(AUDIT_DIR, "audit_report.txt")
    lines = ["FIGHTIQ ODDS → AI → SLIPS AUDIT", "=" * 50, ""]

    lines.append("WHAT CODE IS DESIGNED TO SCRAPE:")
    for src, items in code_capabilities.items():
        lines.append(f"\n[{src}]")
        for i in items:
            lines.append(f"  - {i}")

    lines.append("\n\nLIVE SCRAPE RESULTS (this run):")
    lines.append("-" * 50)
    for row in market_audit[:15]:
        lines.append(f"\n{row['matchup']}")
        lines.append(f"  Source: {row['odds_source']} | Confidence: {row['odds_confidence']}")
        lines.append(f"  Raw keys in market_data: {row['raw_market_keys']}")
        if row["moneyline_outcomes"]:
            lines.append(f"  Moneyline: {row['moneyline_outcomes']}")
        if row["props_nested"]:
            lines.append(f"  Props: {json.dumps(row['props_nested'], ensure_ascii=False)}")
        lines.append(f"  Catalog parsed {row['catalog_option_count']} bet options:")
        for opt in row["catalog_options"][:12]:
            lines.append(f"    • [{opt['type']}] {opt['label']} @ {opt['odds']}")
        lines.append("  AI prompt lines (subset):")
        for pl in row["ai_prompt_market_lines"][:8]:
            lines.append(f"    {pl}")

    lines.append("\n\nFIGHT BRAIN OUTPUTS:")
    lines.append("-" * 50)
    for row in brain_audit[:8]:
        lines.append(f"\n{row['matchup']}")
        lines.append(f"  Pick: {row['prediction'].get('winner')} via {row['prediction'].get('method')} (conf {row['prediction'].get('confidence')})")
        for k in ("safe_pick", "value_pick", "violence_pick"):
            p = row.get(k) or {}
            lines.append(f"  {k}: {p.get('bet')} @ {p.get('odds')} [{p.get('bet_type', '?')}]")
        lines.append(f"  Tweet: {row.get('betting_tweet', '')[:120]}")
        if row.get("bar_sample_f1"):
            lines.append(f"  Bars F1: {row['bar_sample_f1']}")

    if parlays:
        lines.append("\n\nPARLAYS:")
        for slip in ("safe_slip", "violence_slip", "value_slip"):
            legs = parlays.get(slip, [])
            lines.append(f"\n  {slip} ({len(legs)} legs):")
            for leg in legs:
                lines.append(f"    - {leg.get('pick')} @ {leg.get('odds')}")

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Wrote {json_path}")
    print(f"Wrote {txt_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
