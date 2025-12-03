import json
import os
import time
import tweepy
from dotenv import load_dotenv

# .env dosyasını yükle (API Keyler buradan gelecek)
load_dotenv()

# --- AYARLAR ---
INPUT_FILE = "3_results.json"
HISTORY_FILE = "posted_history.json"

# Twitter API Kimlik Doğrulama
API_KEY = os.getenv("X_API_KEY")
API_SECRET = os.getenv("X_API_SECRET")
ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN")
ACCESS_SECRET = os.getenv("X_ACCESS_SECRET")

def get_twitter_client():
    """Twitter API Bağlantısını Kurar"""
    if not all([API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_SECRET]):
        print("⚠️ Twitter API Keys missing in .env file. Skipping post.")
        return None

    try:
        client = tweepy.Client(
            consumer_key=API_KEY,
            consumer_secret=API_SECRET,
            access_token=ACCESS_TOKEN,
            access_token_secret=ACCESS_SECRET
        )
        print("✅ Connected to Twitter API.")
        return client
    except Exception as e:
        print(f"❌ Twitter Connection Error: {e}")
        return None

def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    except: return []

def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=4)

def post_tweet_thread(client, content):
    """Zincirleme Tweet Atar (Thread)"""
    tweets = content.get('tweets', [])
    if not tweets: return False
    
    if client:
        try:
            # 1. Tweeti at
            response = client.create_tweet(text=tweets[0])
            first_tweet_id = response.data['id']
            print(f"   🐦 Tweet 1 sent! ID: {first_tweet_id}")
            
            # Varsa 2. Tweeti (Reply olarak) at
            if len(tweets) > 1:
                response = client.create_tweet(text=tweets[1], in_reply_to_tweet_id=first_tweet_id)
                second_tweet_id = response.data['id']
                print(f"   🐦 Tweet 2 sent! ID: {second_tweet_id}")
                
                # Varsa 3. Tweeti at
                if len(tweets) > 2:
                    client.create_tweet(text=tweets[2], in_reply_to_tweet_id=second_tweet_id)
                    print(f"   🐦 Tweet 3 sent!")
            
            return True
        except Exception as e:
            print(f"❌ Tweet Error: {e}")
            return False
    else:
        # Client yoksa (Local test veya key eksik) simülasyon yap
        print("\n[SIMULATION MODE] Tweets to be posted:")
        for t in tweets:
            print(f"   -> {t}")
        return True

def main():
    print("--- 📢 SOCIAL MANAGER: FIGHTIQ ---")
    
    try:
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            results = json.load(f)
    except:
        print("❌ No results found to post.")
        return

    history = load_history()
    client = get_twitter_client()
    new_posts_count = 0
    
    for item in results:
        # Eşsiz ID: Maç ismi + FightBrain'in analiz tarihi (veya sadece maç ismi)
        # Sadece maç ismi kullanırsak o maçı bir daha asla paylaşmaz.
        # Tarihi de ekleyelim ki, analiz güncellenirse (örneğin oranlar değişince) tekrar atabilsin.
        # Şimdilik basit tutalım: Sadece Maç İsmi (Haftada 1 analiz)
        matchup = item['matchup']
        
        if matchup in history:
            print(f"   zzz Skipping (Already posted): {matchup}")
            continue
            
        print(f"\n🚀 Posting: {matchup}")
        output = item.get('fight_brain_output', {})
        
        if post_tweet_thread(client, output):
            history.append(matchup)
            new_posts_count += 1
            # Twitter spam korumasına takılmamak için bekle
            print("   ⏳ Waiting 60s before next tweet...")
            time.sleep(60) 

    save_history(history)
    print(f"\n📈 Session Finished. {new_posts_count} new threads posted.")

if __name__ == "__main__":
    main()