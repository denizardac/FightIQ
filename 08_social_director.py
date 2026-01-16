import json
import os
import time
import tweepy
from datetime import datetime
from dotenv import load_dotenv
import sys

load_dotenv()
API_KEY = os.getenv("X_API_KEY")
API_SECRET = os.getenv("X_API_SECRET")
ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN")
ACCESS_SECRET = os.getenv("X_ACCESS_SECRET")

FILES = {
    "card": "1_card.json",
    "results": "3_results.json",
    "parlays": "4_parlays.json",
    "history": "posted_history.json",
    "visuals": "visuals",
    "spotlight": "spotlight_ready.json"
}

class SocialDirector:
    def __init__(self):
        self.client = None
        self.api_v1 = None
        self.history = self.load_history()
        
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
        self.history.append(item_id)
        with open(FILES["history"], "w") as f: json.dump(self.history, f, indent=4)

    def find_image(self, f1, f2, visual_type="Radar"):
        safe_f1 = "".join([c for c in f1 if c.isalnum() or c==' ']).replace(' ', '_')
        safe_f2 = "".join([c for c in f2 if c.isalnum() or c==' ']).replace(' ', '_')
        target = f"Radar_{safe_f1}_vs_{safe_f2}.png"
        if visual_type == "Card":
            target = f"Card_{safe_f1}.png"
            if not os.path.exists(os.path.join(FILES["visuals"], target)): target = f"Card_{safe_f2}.png"
        path = os.path.join(FILES["visuals"], target)
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

    def post_tweet(self, text, media_path=None, reply_to_id=None, poll_options=None, poll_duration_minutes=None):
        print(f"\n🐦 POSTING (Reply: {reply_to_id}):\n{text[:60]}...")
        try:
            media_id = None
            if media_path and self.api_v1:
                # Determine media type
                if media_path.lower().endswith(".mp4"):
                    print(f"   🎥 Uploading Video: {media_path}")
                    # Use chunked upload for video
                    media = self.api_v1.media_upload(filename=media_path, media_category='TWEET_VIDEO', chunked=True)
                else:
                    media = self.api_v1.media_upload(filename=media_path)
                
                media_id = media.media_id
            
            # Construct Poll args
            poll_args = {}
            if poll_options:
                poll_args['poll_options'] = poll_options
                poll_args['poll_duration_minutes'] = poll_duration_minutes or 24*60 # Default 24h
            
            # TWITTER API LIMITATION: Cannot have both poll and media in same tweet
            # Solution: If poll exists, post it first, then reply with media
            if poll_options and media_id:
                print("   ⚠️ Poll + Media detected - posting as thread")
                # Tweet 1: Text + Poll (no media)
                resp = self.client.create_tweet(
                    text=text,
                    in_reply_to_tweet_id=reply_to_id,
                    **poll_args
                )
                first_tweet_id = resp.data['id']
                print(f"   🚀 Poll tweet sent! ID: {first_tweet_id}")
                
                # Tweet 2: Media as reply (no text needed, just video)
                resp2 = self.client.create_tweet(
                    text="",  # Empty or just emoji
                    media_ids=[media_id],
                    in_reply_to_tweet_id=first_tweet_id
                )
                print(f"   🎥 Video reply sent! ID: {resp2.data['id']}")
                return first_tweet_id  # Return poll tweet ID
            
            # Normal case: Either poll OR media (not both)
            resp = self.client.create_tweet(
                text=text, 
                media_ids=[media_id] if media_id else None, 
                in_reply_to_tweet_id=reply_to_id,
                **poll_args
            )
            print(f"   🚀 Sent! ID: {resp.data['id']}")
            return resp.data['id']
        except Exception as e:
            print(f"   ❌ Error: {e}")
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
            
            # 1. Tweet (Video varsa video, yoksa resim)
            media_file = data.get('video_path') if data.get('video_path') else data.get('visual_path')
            
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
                    time.sleep(5) # Biraz bekle
                    last_id = self.post_tweet(txt, reply_to_id=last_id)
                
                # Dosyayı silmek yerine saklayalım test için, ya da silelim
                # os.remove(FILES["spotlight"]) 
                
        except Exception as e: print(f"❌ Spotlight Error: {e}")

    # --- DİĞER FONKSİYONLAR (AYNI KALACAK) ---
    def post_parlays(self):
        """Post parlay slips with visual tickets"""
        try:
            with open(FILES["parlays"], "r") as f: parlays = json.load(f)
        except: return
        uid = f"PARLAY_{datetime.today().strftime('%Y_%W')}"
        if uid in self.history: return
        
        # NEW: Build thread with ticket images
        slip_configs = [
            ('safe_slip', 'safe', "💰 This week's SAFE SLIP is LOADED. Tap for the breakdown. 🎯 #UFC #Betting"),
            ('violence_slip', 'violence', "🩸 VIOLENCE SLIP: Finish guaranteed. Early KO/SUB expected. 💥 #UFC #Betting"),
            ('value_slip', 'value', "💎 VALUE SLIP: Sharp money detected. The books got this wrong. 🚀 #UFC #Betting")
        ]
        
        last_id = None
        posted_count = 0
        
        for slip_key, slip_type, caption in slip_configs:
            slip_data = parlays.get(slip_key, [])
            if not slip_data:
                continue
            
            # Find ticket image
            ticket_img = self.find_ticket(slip_type)
            
            if ticket_img:
                # Post with ticket image
                tweet_id = self.post_tweet(caption, media_path=ticket_img, reply_to_id=last_id)
            else:
                # Fallback to text-only (old behavior)
                tweet_text = f"{caption}\n\n" + "\n".join([f"✅ {x['pick']}" for x in slip_data[:4]])
                tweet_id = self.post_tweet(tweet_text, reply_to_id=last_id)
            
            if tweet_id:
                if posted_count == 0:
                    self.save_history(uid)
                last_id = tweet_id
                posted_count += 1
                time.sleep(5)

    def post_live_content(self, t_type, v_type, limit):
        """Post live fight week content with video preference"""
        try:
            with open(FILES["results"], "r") as f: results = json.load(f)
        except: return
        count = 0
        for item in results:
            if count >= limit: break
            match = item['matchup']
            uid = f"{match}_{t_type}"
            if uid in self.history: continue
            brain = item.get('fight_brain_output', {})
            text = brain.get('spotlight_content', '') if t_type == "spotlight" else brain.get('content_tweets', {}).get(t_type, '')
            f1, f2 = match.split(" vs ")
            
            # NEW: Prefer video over image for radar charts
            media = None
            if v_type == "Radar":
                media = self.find_video(f1, f2, "Matchup") or self.find_image(f1, f2, v_type)
            else:
                media = self.find_image(f1, f2, v_type)
            
            if text and self.post_tweet(text, media):
                self.save_history(uid)
                count += 1
                time.sleep(60)

    def run_agenda(self):
        # (Önceki kodun aynısı)
        try:
            with open(FILES["card"]) as f: c = json.load(f); status = c.get("status", "IDLE"); ename = c.get("event", "UFC")
        except: status="IDLE"; ename="UFC"
        day = datetime.today().weekday()
        print(f"📅 Agenda: {status} | Day: {day}")
        
        if status == "LIVE":
            if day == 0: 
                uid = f"KICK_{datetime.today().strftime('%Y_%W')}"
                if uid not in self.history: self.post_tweet(f"🚨 FIGHT WEEK: {ename} 🚨\n\nAI Analysis Incoming.\n#UFC"); self.save_history(uid)
            elif day == 1: self.post_live_content("analysis_tweet", "Radar", 3)
            elif day == 2: self.post_live_content("spotlight", "Card", 2)
            elif day == 3: self.post_live_content("violence_tweet", "Radar", 3)
            elif day == 4: self.post_parlays()
            elif day == 5: self.post_live_content("betting_tweet", "Radar", 15)
        else:
            self.post_spotlight_file()

if __name__ == "__main__":
    SocialDirector().run_agenda()