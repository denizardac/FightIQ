import json
import os
import time
import tweepy
from datetime import datetime
from dotenv import load_dotenv
import sys
import argparse

# ==========================================
# DRY-RUN MODE: use --dry-run to skip Twitter posts
# ==========================================
parser = argparse.ArgumentParser(add_help=False)
parser.add_argument("--dry-run", action="store_true", help="Log tweets to console, do NOT post to Twitter")
_args, _ = parser.parse_known_args()
DRY_RUN = _args.dry_run

if DRY_RUN:
    print("[DRY-RUN MODE] Tweets will NOT be posted to Twitter.")

# Add project root to path for core imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.paths import get_data_path, VISUALS_DIR

load_dotenv()
API_KEY = os.getenv("X_API_KEY")
API_SECRET = os.getenv("X_API_SECRET")
ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN")
ACCESS_SECRET = os.getenv("X_ACCESS_SECRET")

FILES = {
    "card": get_data_path("1_card.json"),
    "results": get_data_path("3_results.json"),
    "parlays": get_data_path("4_parlays.json"),
    "history": get_data_path("posted_history.json"),
    "visuals": VISUALS_DIR,
    "spotlight": get_data_path("spotlight_ready.json")
}

class SocialDirector:
    def __init__(self, dry_run=False):
        self.client = None
        self.api_v1 = None
        self.history = self.load_history()
        self.dry_run = dry_run
        
        if dry_run:
            print("[DRY-RUN] Twitter connection skipped.")
            return

        if not all([API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_SECRET]):
            print("❌ ERROR: Keys missing.")
            sys.exit(1)

        try:
            self.client = tweepy.Client(consumer_key=API_KEY, consumer_secret=API_SECRET, access_token=ACCESS_TOKEN, access_token_secret=ACCESS_SECRET)
            auth = tweepy.OAuth1UserHandler(API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_SECRET)
            self.api_v1 = tweepy.API(auth)
            print("✅ Twitter Connected.")
        except: sys.exit(1)

    def load_history(self):
        if not os.path.exists(FILES["history"]): return []
        try:
            with open(FILES["history"], "r") as f: return json.load(f)
        except: return []

    def save_history(self, item_id):
        if self.dry_run:
            print(f"  [DRY-RUN] Would save to history: {item_id}")
            return
        self.history.append(item_id)
        with open(FILES["history"], "w") as f: json.dump(self.history, f, indent=4)

    def find_image(self, f1, f2, visual_type="Versus"):
        safe_f1 = "".join([c for c in f1 if c.isalnum() or c == ' ']).replace(' ', '_')
        safe_f2 = "".join([c for c in f2 if c.isalnum() or c == ' ']).replace(' ', '_')

        if visual_type == "Versus":
            # Try both name orders
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

        # Generic fallback
        path = os.path.join(FILES["visuals"], f"{visual_type}_{safe_f1}_vs_{safe_f2}.png")
        return path if os.path.exists(path) else None
    
    def find_video(self, f1, f2, video_type="Matchup"):
        """Find matchup video in visuals directory"""
        safe_f1 = "".join([c for c in f1 if c.isalnum() or c==' ']).replace(' ', '_').lower()
        safe_f2 = "".join([c for c in f2 if c.isalnum() or c==' ']).replace(' ', '_').lower()
        
        # Try both name orders
        patterns = [
            f"Reel_{video_type}_{safe_f1}_vs_{safe_f2}.mp4",
            f"Reel_{video_type}_{safe_f2}_vs_{safe_f1}.mp4"
        ]
        
        for pattern in patterns:
            path = os.path.join(FILES["visuals"], pattern)
            if os.path.exists(path):
                return path
        return None
    
    def find_ticket(self, slip_type):
        """Find betting ticket image"""
        target = f"Ticket_{slip_type.capitalize()}.png"
        path = os.path.join(FILES["visuals"], target)
        return path if os.path.exists(path) else None

    def _upload_media(self, media_path):
        """Upload media via v1.1 API, return media_id or None."""
        if not self.api_v1 or not media_path or not os.path.exists(media_path):
            return None
        try:
            if media_path.lower().endswith(".mp4"):
                print(f"   🎥 Uploading Video: {media_path}")
                media = self.api_v1.media_upload(filename=media_path, media_category='TWEET_VIDEO', chunked=True)
            else:
                media = self.api_v1.media_upload(filename=media_path)
            return media.media_id
        except Exception as e:
            print(f"   ⚠️ Media upload failed: {e}")
            return None

    def _post_v2(self, text, media_id=None, reply_to_id=None, poll_options=None, poll_duration_minutes=None):
        """Try Twitter API v2 (create_tweet). Returns tweet id or raises."""
        poll_args = {}
        if poll_options:
            poll_args['poll_options'] = poll_options
            poll_args['poll_duration_minutes'] = poll_duration_minutes or 24 * 60

        if poll_options and media_id:
            print("   ⚠️ Poll + Media — posting as thread")
            resp = self.client.create_tweet(text=text, in_reply_to_tweet_id=reply_to_id, **poll_args)
            first_id = resp.data['id']
            print(f"   🚀 Poll tweet sent! ID: {first_id}")
            resp2 = self.client.create_tweet(text="🎥", media_ids=[media_id], in_reply_to_tweet_id=first_id)
            print(f"   🎥 Video reply sent! ID: {resp2.data['id']}")
            return first_id

        resp = self.client.create_tweet(
            text=text,
            media_ids=[media_id] if media_id else None,
            in_reply_to_tweet_id=reply_to_id,
            **poll_args
        )
        print(f"   🚀 Sent (v2)! ID: {resp.data['id']}")
        return resp.data['id']

    def _post_v1(self, text, media_id=None, reply_to_id=None):
        """Fallback to Twitter API v1.1 (update_status). Polls not supported."""
        kwargs = {}
        if media_id:
            kwargs['media_ids'] = [media_id]
        if reply_to_id:
            kwargs['in_reply_to_status_id'] = reply_to_id
            kwargs['auto_populate_reply_metadata'] = True
        status = self.api_v1.update_status(status=text, **kwargs)
        print(f"   🚀 Sent (v1.1 fallback)! ID: {status.id}")
        return str(status.id)

    def post_tweet(self, text, media_path=None, reply_to_id=None, poll_options=None, poll_duration_minutes=None):
        if self.dry_run:
            print(f"\n[DRY-RUN] TWEET PREVIEW (reply_to={reply_to_id}):")
            print(f"  TEXT: {text[:120]}")
            if media_path:
                print(f"  MEDIA: {media_path} (exists={os.path.exists(str(media_path))})")
            if poll_options:
                print(f"  POLL: {poll_options}")
            print(f"  -> Skipped (dry-run)")
            return "DRY_RUN_FAKE_ID"

        print(f"\n🐦 POSTING (Reply: {reply_to_id}):\n{text[:60]}...")
        media_id = self._upload_media(media_path) if media_path else None

        # Try v2 first; on 403 (Project restriction) fall back to v1.1
        if self.client:
            try:
                return self._post_v2(text, media_id=media_id, reply_to_id=reply_to_id,
                                     poll_options=poll_options, poll_duration_minutes=poll_duration_minutes)
            except Exception as e:
                err = str(e)
                if "403" in err and "Project" in err:
                    print(f"   ⚠️ v2 blocked (app not in Project). Falling back to v1.1…")
                elif "403" in err:
                    print(f"   ⚠️ v2 403: {err[:120]}. Falling back to v1.1…")
                else:
                    print(f"   ❌ v2 error: {err[:120]}")
                    return None

        # v1.1 fallback (polls not supported — post text+media only)
        if poll_options:
            print("   ⚠️ Polls not supported in v1.1 fallback — posting text only")
        if self.api_v1:
            try:
                return self._post_v1(text, media_id=media_id, reply_to_id=reply_to_id)
            except Exception as e:
                print(f"   ❌ v1.1 error: {e}")
        return None

    # --- IDLE MODU (GÜNCELLENDİ: THREAD DESTEĞİ) ---
    def post_spotlight_file(self):
        if not os.path.exists(FILES["spotlight"]): return
        try:
            with open(FILES["spotlight"], "r") as f: data = json.load(f)
            uid = f"SPOTLIGHT_{data['fighter']}_{datetime.today().strftime('%Y-%m-%d')}"
            
            if uid in self.history: return

            # Thread Listesini Al
            thread_texts = data.get('thread', [])
            if not thread_texts and 'tweet' in data: # Eski format desteği
                thread_texts = [data['tweet']]

            print(f"🚀 Posting Spotlight Thread ({len(thread_texts)} tweets)...")
            
            # STRATEGY: Twitter gets PNG Card (better aspect ratio for feed)
            # Video is saved but not posted to Twitter (reserved for TikTok/IG Reels)
            media_file = data.get('visual_path')  # Always use PNG card for Twitter
            
            # Extract Poll Options
            poll_options = data.get('poll_options')
            
            last_id = self.post_tweet(
                thread_texts[0], 
                media_path=media_file, 
                poll_options=poll_options,
                poll_duration_minutes=1440
            )
            
            if last_id:
                self.save_history(uid)
                # Diğer tweetleri reply olarak at
                for txt in thread_texts[1:]:
                    if not self.dry_run:
                        time.sleep(5)
                    last_id = self.post_tweet(txt, reply_to_id=last_id)
                
                # Dosyayı silmek yerine saklayalım test için, ya da silelim
                # os.remove(FILES["spotlight"]) 
                
        except Exception as e: print(f"❌ Spotlight Error: {e}")

    # --- DİĞER FONKSİYONLAR (AYNI KALACAK) ---
    def post_parlays(self):
        """Post parlay slips as a thread with ticket images."""
        try:
            with open(FILES["parlays"], "r") as f:
                parlays = json.load(f)
        except Exception:
            return
        uid = f"PARLAY_{datetime.today().strftime('%Y_%W')}"
        if uid in self.history:
            return

        def build_slip_caption(slip_key, slip_type, parlays):
            slip_data = parlays.get(slip_key, [])
            picks = [x.get('pick', '') for x in slip_data if x.get('pick')][:3]
            odds_vals = [str(x.get('odds', '')) for x in slip_data if x.get('odds')][:3]

            if slip_type == "safe":
                intro = "💰 SAFE SLIP — Lock these in.\n"
            elif slip_type == "violence":
                intro = "🩸 VIOLENCE SLIP — Chaos incoming.\n"
            else:
                intro = "💎 VALUE SLIP — Books got this wrong.\n"

            lines = []
            for i, pick in enumerate(picks):
                odds_str = f" @ {odds_vals[i]}" if i < len(odds_vals) else ""
                lines.append(f"✅ {pick}{odds_str}")
            body = "\n".join(lines)
            tag = "#UFC #Betting #FightIQ"
            full = f"{intro}{body}\n{tag}"
            return full[:278]

        slip_configs = [
            ('safe_slip',     'safe',     None),
            ('violence_slip', 'violence', None),
            ('value_slip',    'value',    None),
        ]

        last_id = None
        posted_count = 0

        # Lead tweet
        lead = "📊 FIGHTIQ PARLAY SLIPS — Fight Week Edition\n\nThree slips. Three strategies. Full breakdown below. 🧵\n#UFC #Betting"
        lead_id = self.post_tweet(lead)
        if lead_id:
            self.save_history(uid)
            last_id = lead_id
            posted_count += 1
            if not self.dry_run:
                time.sleep(5)

        for slip_key, slip_type, _ in slip_configs:
            slip_data = parlays.get(slip_key, [])
            if not slip_data:
                continue
            caption = build_slip_caption(slip_key, slip_type, parlays)
            ticket_img = self.find_ticket(slip_type)
            tweet_id = self.post_tweet(caption, media_path=ticket_img, reply_to_id=last_id)
            if tweet_id:
                last_id = tweet_id
                posted_count += 1
                if not self.dry_run:
                    time.sleep(5)

    def post_live_content(self, t_type, v_type, limit):
        """Post live fight week content. Always uses Versus cards for matchup visuals."""
        try:
            with open(FILES["results"], "r") as f:
                results = json.load(f)
        except Exception:
            return
        count = 0
        for item in results:
            if count >= limit:
                break
            match = item['matchup']
            uid = f"{match}_{t_type}"
            if uid in self.history:
                continue
            brain = item.get('fight_brain_output', {})
            if t_type == "spotlight":
                text = brain.get('spotlight_content', '')
            else:
                text = brain.get('content_tweets', {}).get(t_type, '')
            if not text:
                continue
            f1, f2 = match.split(" vs ")

            # Always prefer Versus card; fall back to stat card, then radar
            media = (
                self.find_image(f1, f2, "Versus")
                or self.find_image(f1, f2, "Card")
            )

            if self.post_tweet(text, media):
                self.save_history(uid)
                count += 1
                if not self.dry_run:
                    time.sleep(60)

    def _kickoff_tweet(self, event_name):
        """Monday: hype tweet with the main event Versus card attached."""
        uid = f"KICK_{datetime.today().strftime('%Y_%W')}"
        if uid in self.history:
            return
        try:
            with open(FILES["results"], "r") as f:
                results = json.load(f)
            main_event = results[0] if results else None
        except Exception:
            main_event = None

        fight_line = ""
        versus_card = None
        if main_event:
            matchup = main_event.get('matchup', '')
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
        self.post_tweet(tweet, media_path=versus_card)
        self.save_history(uid)

    def run_agenda(self):
        try:
            with open(FILES["card"]) as f:
                c = json.load(f)
                status = c.get("status", "IDLE")
                ename  = c.get("event", "UFC")
        except Exception:
            status = "IDLE"
            ename  = "UFC"

        day = datetime.today().weekday()
        print(f"📅 Agenda: {status} | Day: {day}")

        if status == "LIVE":
            if day == 0:
                # Monday — Fight Week kickoff + main event versus card
                self._kickoff_tweet(ename)
            elif day == 1:
                # Tuesday — Deep Dive analysis tweets + Versus cards
                self.post_live_content("analysis_tweet", "Versus", 3)
            elif day == 2:
                # Wednesday — Fighter Spotlight (stat card)
                self.post_live_content("spotlight", "Card", 2)
            elif day == 3:
                # Thursday — Violence tweets + Versus cards
                self.post_live_content("violence_tweet", "Versus", 3)
            elif day == 4:
                # Friday — Parlay slips with ticket visuals
                self.post_parlays()
            elif day == 5:
                # Saturday — Betting angles + Versus cards (all remaining fights)
                self.post_live_content("betting_tweet", "Versus", 15)
        else:
            # IDLE mode — spotlight engine content
            self.post_spotlight_file()

if __name__ == "__main__":
    SocialDirector(dry_run=DRY_RUN).run_agenda()