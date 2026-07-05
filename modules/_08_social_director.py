import json
import os
import time
import sys
import random
import argparse
from datetime import datetime
from dotenv import load_dotenv

# Windows console UTF-8 (emoji in prints) — missing here while every other
# module had it; crashed on cp1252 consoles.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# ==========================================
# DRY-RUN MODE: use --dry-run to skip Twitter posts
# ==========================================
parser = argparse.ArgumentParser(add_help=False)
parser.add_argument("--dry-run", action="store_true", help="Log tweets to console, do NOT post to Twitter")
_args, _ = parser.parse_known_args()
DRY_RUN = _args.dry_run

if DRY_RUN:
    print("[DRY-RUN MODE] Tweets will NOT be posted to Twitter.")

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.paths import get_data_path, VISUALS_DIR, PROJECT_ROOT
from core.naming import safe_filename, safe_filename_lower
from core.parlay_logic import combined_odds
from core.pipeline_meta import check_stage_fresh
from core.twitter_client import TwitterClient
import core.config as config

load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

FILES = {
    "card": get_data_path("1_card.json"),
    "results": get_data_path("3_results.json"),
    "parlays": get_data_path("4_parlays.json"),
    "history": get_data_path("posted_history.json"),
    "visuals": VISUALS_DIR,
    "spotlight": get_data_path("spotlight_ready.json"),
    "spotlight_history": get_data_path("spotlight_history.json"),
}


class SocialDirector:
    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        self.post_failed = False
        self.history = self.load_history()
        try:
            self.twitter = TwitterClient(dry_run=dry_run)
        except RuntimeError as e:
            print(f"❌ {e}")
            sys.exit(1)

    def load_history(self):
        if not os.path.exists(FILES["history"]):
            return []
        try:
            with open(FILES["history"], "r") as f:
                raw = json.load(f)
        except Exception:
            return []
        return self._sanitize_history(raw if isinstance(raw, list) else [])

    def _sanitize_history(self, history):
        """Drop legacy partial spotlight marks (saved before thread finished)."""
        cleaned = []
        removed = 0
        for item in history:
            if not isinstance(item, str):
                continue
            # Old bug: SPOTLIGHT_*_YYYY-MM-DD without _DONE blocked retries
            if item.startswith("SPOTLIGHT_") and not item.endswith("_DONE"):
                removed += 1
                continue
            cleaned.append(item)
        if removed and not self.dry_run:
            with open(FILES["history"], "w") as f:
                json.dump(cleaned, f, indent=4)
            print(f"   🧹 Cleared {removed} incomplete spotlight history entry(ies)")
        return cleaned

    def _done_id(self, uid):
        return uid if uid.endswith("_DONE") else f"{uid}_DONE"

    def _already_posted(self, uid):
        return self._done_id(uid) in self.history

    def save_history(self, item_id):
        if self.dry_run:
            print(f"  [DRY-RUN] Would save to history: {item_id}")
            return
        self.history.append(item_id)
        # Cap unbounded growth — keep the newest entries only
        max_entries = getattr(config, "POSTED_HISTORY_MAX_ENTRIES", 400)
        if len(self.history) > max_entries:
            self.history = self.history[-max_entries:]
        with open(FILES["history"], "w") as f:
            json.dump(self.history, f, indent=4)

    def _mark_spotlight_history(self, fighter_name):
        """Record the fighter in spotlight_history.json AFTER a successful post.

        Was previously written by the spotlight engine at generation time, so
        a failed post permanently 'burned' the fighter without any content
        ever reaching Twitter."""
        if self.dry_run or not fighter_name:
            return
        try:
            history = []
            if os.path.exists(FILES["spotlight_history"]):
                with open(FILES["spotlight_history"], "r") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, list):
                        history = loaded
            history.append({"name": fighter_name, "date": datetime.today().strftime("%Y-%m-%d")})
            with open(FILES["spotlight_history"], "w") as f:
                json.dump(history, f, indent=4)
        except Exception as e:
            print(f"   ⚠️ Could not update spotlight history: {e}")

    def _sleep_between_posts(self, is_reply: bool = False):
        if self.dry_run:
            return
        delay = self.twitter.thread_delay(is_reply=is_reply)
        jitter = 0
        if getattr(self.twitter, "backend", "") == "cookies":
            jitter = random.randint(5, config.TWITTER_DELAY_JITTER_SECONDS)
        total = delay + jitter
        print(f"   ⏳ Waiting {total}s before next post...")
        time.sleep(total)

    def _warmup_before_session(self):
        if self.dry_run:
            return
        if getattr(self.twitter, "backend", "") == "official":
            return
        wait = config.TWITTER_PRE_POST_DELAY_SECONDS
        print(f"   ⏳ Pre-post warmup {wait}s (reduces error 226)...")
        time.sleep(wait)

    def find_image(self, f1, f2, visual_type="Versus"):
        # Uses the SAME canonical sanitizer as the visual engine (core.naming)
        safe_f1 = safe_filename(f1)
        safe_f2 = safe_filename(f2)

        if visual_type == "Versus":
            for s1, s2 in [(safe_f1, safe_f2), (safe_f2, safe_f1)]:
                p = os.path.join(FILES["visuals"], f"Versus_{s1}_vs_{s2}.png")
                if os.path.exists(p):
                    return p
            return None

        if visual_type == "Card":
            for fname in [safe_f1, safe_f2]:
                p = os.path.join(FILES["visuals"], f"Card_{fname}.png")
                if os.path.exists(p):
                    return p
            return None

        if visual_type == "Radar":
            for s1, s2 in [(safe_f1, safe_f2), (safe_f2, safe_f1)]:
                p = os.path.join(FILES["visuals"], f"Radar_{s1}_vs_{s2}.png")
                if os.path.exists(p):
                    return p
            return None

        path = os.path.join(FILES["visuals"], f"{visual_type}_{safe_f1}_vs_{safe_f2}.png")
        return path if os.path.exists(path) else None

    def find_video(self, f1, f2, video_type="Matchup"):
        safe_f1 = safe_filename_lower(f1)
        safe_f2 = safe_filename_lower(f2)
        patterns = [
            f"Reel_{video_type}_{safe_f1}_vs_{safe_f2}.mp4",
            f"Reel_{video_type}_{safe_f2}_vs_{safe_f1}.mp4",
        ]
        for pattern in patterns:
            path = os.path.join(FILES["visuals"], pattern)
            if os.path.exists(path):
                return path
        return None

    def find_ticket(self, slip_type):
        target = f"Ticket_{slip_type.capitalize()}.png"
        path = os.path.join(FILES["visuals"], target)
        return path if os.path.exists(path) else None

    def post_tweet(self, text, media_path=None, reply_to_id=None, poll_options=None, poll_duration_minutes=None):
        print(f"\n🐦 POSTING (Reply: {reply_to_id}):\n{text[:60]}...")
        tweet_id = self.twitter.post(
            text,
            media_path=media_path,
            reply_to_id=reply_to_id,
            poll_options=poll_options,
            poll_duration_minutes=poll_duration_minutes,
        )
        if not tweet_id:
            self.post_failed = True
        return tweet_id

    def _resolve_media_path(self, media_file):
        if not media_file:
            return None
        if os.path.isabs(media_file) and os.path.exists(media_file):
            return media_file
        candidates = [
            media_file,
            os.path.join(PROJECT_ROOT, media_file.replace("/", os.sep)),
            os.path.join(FILES["visuals"], os.path.basename(media_file)),
        ]
        for path in candidates:
            if path and os.path.exists(path):
                return path
        return None

    def post_spotlight_file(self):
        if not os.path.exists(FILES["spotlight"]):
            return True
        # Stale guard: spotlight_ready.json is regenerated daily. If the
        # engine failed today, don't re-post yesterday's leftover content.
        age_hours = (time.time() - os.path.getmtime(FILES["spotlight"])) / 3600.0
        if age_hours > 20:
            print(f"   ⏭️ spotlight_ready.json is {age_hours:.0f}h old — skipping (stale).")
            return True
        try:
            with open(FILES["spotlight"], "r") as f:
                data = json.load(f)
            uid = f"SPOTLIGHT_{data['fighter']}_{datetime.today().strftime('%Y-%m-%d')}"

            if self._already_posted(uid):
                print(f"   ⏭️ Already posted today (complete): {self._done_id(uid)}")
                return True

            thread_texts = [t.strip() for t in data.get("thread", []) if t and t.strip()]
            if not thread_texts and data.get("tweet"):
                thread_texts = [data["tweet"]]

            media_file = self._resolve_media_path(data.get("visual_path"))
            if not media_file:
                print(f"❌ Spotlight image missing: {data.get('visual_path')}")
                self.post_failed = True
                return False

            print(f"🚀 Posting Spotlight ({len(thread_texts)} tweets) + {os.path.basename(media_file)}")
            self._warmup_before_session()

            last_id = self.post_tweet(thread_texts[0], media_path=media_file)
            if not last_id:
                return False

            for txt in thread_texts[1:]:
                self._sleep_between_posts(is_reply=True)
                reply_id = self.post_tweet(txt, reply_to_id=last_id)
                if not reply_id:
                    print("   ⚠️ Thread incomplete — not saving to history (retry tomorrow)")
                    return False
                last_id = reply_id

            self.save_history(self._done_id(uid))
            self._mark_spotlight_history(data.get("fighter"))
            return True

        except Exception as e:
            print(f"❌ Spotlight Error: {e}")
            self.post_failed = True
            return False

    def post_parlays(self):
        try:
            with open(FILES["parlays"], "r") as f:
                parlays = json.load(f)
        except Exception:
            return True

        uid = f"PARLAY_{datetime.today().strftime('%Y_%W')}"
        if self._already_posted(uid):
            return True

        def build_slip_caption(slip_type, slip_data):
            max_legs = config.PARLAY_MAX_LEGS
            picks = [x.get("pick", "") for x in slip_data if x.get("pick")][:max_legs]
            odds_vals = [x.get("odds") for x in slip_data if x.get("pick")][:max_legs]
            total = combined_odds(slip_data[:max_legs])

            if slip_type == "safe":
                intro = "💰 SAFE SLIP — High-confidence plays.\n"
            elif slip_type == "violence":
                intro = "🩸 VIOLENCE SLIP — Finish-focused card.\n"
            else:
                intro = "💎 EDGE SLIP — Model-backed 3-leg parlay.\n"

            lines = []
            for i, pick in enumerate(picks):
                odds_str = f" @ {odds_vals[i]}" if i < len(odds_vals) and odds_vals[i] else ""
                lines.append(f"✅ {pick}{odds_str}")
            body = "\n".join(lines)
            parlay_line = f"\n🔗 {len(picks)}-leg @ {total}" if len(picks) > 1 and total > 1 else ""
            tag = "#UFC #Betting #FightIQ"
            return f"{intro}{body}{parlay_line}\n{tag}"[:278]

        slip_configs = [
            ("safe_slip", "safe"),
            ("violence_slip", "violence"),
            ("value_slip", "value"),
        ]

        available = []
        for slip_key, slip_type in slip_configs:
            slip_data = parlays.get(slip_key, [])
            if not slip_data:
                print(f"   ⏭️ Skipping empty {slip_type} slip")
                continue
            ticket_img = self.find_ticket(slip_type)
            if not ticket_img:
                print(f"   ⚠️ No ticket image for {slip_type} — run ticket generator")
                continue
            available.append((slip_key, slip_type, slip_data, ticket_img))

        if not available:
            print("   ⚠️ No parlay slips with images to post.")
            return True

        names = {"safe": "Safe", "violence": "Violence", "value": "Edge"}
        if len(available) == 1:
            only = names[available[0][1]]
            lead = (
                f"📊 FIGHTIQ — {only.upper()} SLIP\n\n"
                f"Fight week play card below. 🧵\n#UFC #Betting"
            )
        else:
            labels = " · ".join(names[a[1]] for a in available)
            lead = (
                f"📊 FIGHTIQ PARLAY SLIPS — Fight Week\n\n"
                f"{labels}. Full cards below. 🧵\n#UFC #Betting"
            )

        self._warmup_before_session()
        last_id = self.post_tweet(lead)
        if not last_id:
            return False

        self._sleep_between_posts(is_reply=False)

        for slip_key, slip_type, slip_data, ticket_img in available:
            caption = build_slip_caption(slip_type, slip_data)
            tweet_id = self.post_tweet(caption, media_path=ticket_img, reply_to_id=last_id)
            if not tweet_id:
                print("   ⚠️ Parlay thread incomplete — not saving to history")
                return False
            last_id = tweet_id
            self._sleep_between_posts(is_reply=True)

        self.save_history(self._done_id(uid))
        return True

    def post_live_content(self, t_type, v_type, limit):
        try:
            with open(FILES["results"], "r") as f:
                results = json.load(f)
        except Exception:
            return True

        count = 0
        for item in results:
            if count >= limit:
                break
            match = item.get("matchup", "")
            if " vs " not in match:
                continue
            uid = f"{match}_{t_type}"
            if self._already_posted(uid):
                continue
            brain = item.get("fight_brain_output", {})
            if t_type == "spotlight":
                text = brain.get("spotlight_content", "")
            else:
                text = brain.get("content_tweets", {}).get(t_type, "")
            if not text:
                continue
            f1, f2 = match.split(" vs ", 1)
            media = self.find_image(f1, f2, "Versus") or self.find_image(f1, f2, "Card")

            if count == 0:
                self._warmup_before_session()
            if self.post_tweet(text, media):
                self.save_history(self._done_id(uid))
                count += 1
                if not self.dry_run:
                    time.sleep(config.TWITTER_LIVE_CONTENT_DELAY_SECONDS)
            else:
                return False
        return True

    def _kickoff_tweet(self, event_name):
        uid = f"KICK_{datetime.today().strftime('%Y_%W')}"
        if self._already_posted(uid):
            return True
        try:
            with open(FILES["results"], "r") as f:
                results = json.load(f)
            main_event = results[0] if results else None
        except Exception:
            main_event = None

        fight_line = ""
        versus_card = None
        if main_event:
            matchup = main_event.get("matchup", "")
            fight_line = f"\n\n🥊 MAIN EVENT: {matchup}"
            try:
                f1, f2 = matchup.split(" vs ")
                versus_card = self.find_image(f1, f2, "Versus")
            except Exception:
                pass

        tweet = (
            f"🚨 FIGHT WEEK: {event_name} 🚨"
            f"{fight_line}\n\n"
            f"Full AI breakdown drops all week.\n"
            f"#UFC #MMA #FightIQ"
        )
        self._warmup_before_session()
        if not self.post_tweet(tweet, media_path=versus_card):
            return False
        self.save_history(self._done_id(uid))
        return True

    def run_agenda(self) -> bool:
        try:
            with open(FILES["card"]) as f:
                c = json.load(f)
                status = c.get("status", "IDLE")
                ename = c.get("event", "UFC")
                days_until = c.get("days_until")
        except Exception:
            status = "IDLE"
            ename = "UFC"
            days_until = None

        if status == "ERROR":
            print("❌ Card status is ERROR — refusing to post anything.")
            return False

        print(f"📅 Agenda: {status} | Days until event: {days_until}")

        ok = True
        if status == "LIVE":
            # Stale-content guard: never post fight-week content generated
            # for a different event or an old run.
            fresh, reason = check_stage_fresh("3_results", event=ename)
            if not fresh:
                print(f"❌ LIVE content blocked: {reason}")
                return False

            # Agenda keyed to days-until-event (not weekday) so a fight week
            # detected mid-week still posts the right content and a missed
            # kickoff is caught up instead of skipped forever.
            if days_until is None:
                day = datetime.today().weekday()
                days_until = {0: 5, 1: 4, 2: 3, 3: 2, 4: 1, 5: 0}.get(day, 99)

            kick_uid = f"KICK_{datetime.today().strftime('%Y_%W')}"
            if days_until >= 5:
                ok = self._kickoff_tweet(ename)
            else:
                if days_until >= 1 and not self._already_posted(kick_uid):
                    ok = self._kickoff_tweet(ename) and ok
                if days_until == 4:
                    ok = self.post_live_content("analysis_tweet", "Versus", 3) and ok
                elif days_until == 3:
                    ok = self.post_live_content("spotlight", "Card", 2) and ok
                elif days_until == 2:
                    ok = self.post_live_content("violence_tweet", "Versus", 3) and ok
                elif days_until == 1:
                    ok = self.post_parlays() and ok
                elif days_until <= 0:
                    ok = self.post_live_content("betting_tweet", "Versus", 15) and ok
        else:
            ok = self.post_spotlight_file()

        if self.post_failed or not ok:
            print("❌ Social Director finished with posting failures.")
            return False
        return True


if __name__ == "__main__":
    success = SocialDirector(dry_run=DRY_RUN).run_agenda()
    sys.exit(0 if success else 1)
