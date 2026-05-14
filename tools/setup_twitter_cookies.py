"""
One-time setup: saves Twitter cookies for twikit.
Run this once on the VPS before starting the bot.

Usage:
    python3 tools/setup_twitter_cookies.py
"""
import json, os, sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

COOKIES_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "twitter_cookies.json")

print("=== FightIQ Twitter Cookie Setup ===")
print("Get these values from Chrome DevTools (F12 → Application → Cookies → x.com / twitter.com):\n")

auth_token = input("auth_token: ").strip()
ct0       = input("ct0       : ").strip()
twid      = input("twid (press Enter to skip): ").strip()

if not auth_token or not ct0:
    print("❌ auth_token and ct0 are required.")
    sys.exit(1)

cookies = [
    {"name": "auth_token", "value": auth_token, "domain": ".x.com", "path": "/", "secure": True, "httpOnly": True, "sameSite": "None"},
    {"name": "ct0",        "value": ct0,        "domain": ".x.com", "path": "/", "secure": True, "httpOnly": False, "sameSite": "Lax"},
]
if twid:
    cookies.append({"name": "twid", "value": twid, "domain": ".x.com", "path": "/", "secure": True, "httpOnly": True, "sameSite": "None"})

os.makedirs(os.path.dirname(COOKIES_FILE), exist_ok=True)
with open(COOKIES_FILE, "w") as f:
    json.dump(cookies, f, indent=2)

print(f"\n✅ Cookies saved to: {COOKIES_FILE}")

# Quick test
print("\nTesting connection...")
try:
    import asyncio
    from twikit import Client

    async def test():
        c = Client("en-US")
        c.load_cookies(COOKIES_FILE)
        me = await c.get_user_by_screen_name("FightIQBot")
        return me

    user = asyncio.run(test())
    print(f"✅ Connected as: @{user.screen_name} ({user.name})")
except Exception as e:
    print(f"⚠️  Connection test failed: {e}")
    print("   Cookies saved but login might need verification.")
