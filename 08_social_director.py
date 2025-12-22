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

    def post_tweet(self, text, img_path=None, reply_to_id=None):
        print(f"\n🐦 POSTING (Reply: {reply_to_id}):\n{text[:60]}...")
        try:
            media_id = None
            if img_path and self.api_v1:
                media = self.api_v1.media_upload(filename=img_path)
                media_id = media.media_id
            
            resp = self.client.create_tweet(text=text, media_ids=[media_id] if media_id else None, in_reply_to_tweet_id=reply_to_id)
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
            
            # 1. Tweet (Resimli)
            last_id = self.post_tweet(thread_texts[0], data['visual_path'])
            
            if last_id:
                self.save_history(uid)
                # Diğer tweetleri reply olarak at
                for txt in thread_texts[1:]:
                    time.sleep(5) # Biraz bekle
                    last_id = self.post_tweet(txt, reply_to_id=last_id)
                
                os.remove(FILES["spotlight"]) # Temizlik
                
        except Exception as e: print(f"❌ Spotlight Error: {e}")

    # --- DİĞER FONKSİYONLAR (AYNI KALACAK) ---
    def post_parlays(self):
        # (Önceki kodun aynısı)
        try:
            with open(FILES["parlays"], "r") as f: parlays = json.load(f)
        except: return
        uid = f"PARLAY_{datetime.today().strftime('%Y_%W')}"
        if uid in self.history: return
        tweets = []
        safe = parlays.get('safe_slip', [])
        if safe: tweets.append("💰 FIGHTIQ SAFE SLIP 💰\n\n" + "\n".join([f"✅ {x['pick']}" for x in safe[:4]]) + "\n\n#UFC #Betting")
        viol = parlays.get('violence_slip', [])
        if viol: tweets.append("🩸 VIOLENCE SLIP 🩸\n\n" + "\n".join([f"💥 {x['match']}: {x['pick']}" for x in viol[:3]]) + "\n\n#UFC #Violence")
        val = parlays.get('value_slip', [])
        if val: tweets.append("💎 VALUE SLIP 💎\n\n" + "\n".join([f"🚀 {x['match']}: {x['pick']}" for x in val[:3]]) + "\n\n#UFC #Value")
        
        last_id = None
        if tweets:
            last_id = self.post_tweet(tweets[0])
            self.save_history(uid)
            for t in tweets[1:]:
                time.sleep(5)
                last_id = self.post_tweet(t, reply_to_id=last_id)

    def post_live_content(self, t_type, v_type, limit):
        # (Önceki kodun aynısı)
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
            img = self.find_image(f1, f2, v_type)
            if text and self.post_tweet(text, img):
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