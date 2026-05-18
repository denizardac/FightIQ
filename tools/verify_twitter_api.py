#!/usr/bin/env python3
"""Verify X API credentials (read-only). Does not post a tweet."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.twitter_client import twitter_credentials_status, has_official_api_credentials


def main():
    status = twitter_credentials_status()
    print("Twitter credentials status:")
    print(f"  Official API keys: {'yes' if status['official_api'] else 'no'}")
    print(f"  Cookie file:       {'yes' if status['cookies'] else 'no'}")
    print(f"  Active backend:    {status['backend']}")

    if not has_official_api_credentials():
        print("\nTo use official API, set X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET in .env")
        return 1

    import tweepy
    from dotenv import load_dotenv
    from core.paths import PROJECT_ROOT

    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

    client = tweepy.Client(
        consumer_key=os.getenv("X_API_KEY"),
        consumer_secret=os.getenv("X_API_SECRET"),
        access_token=os.getenv("X_ACCESS_TOKEN"),
        access_token_secret=os.getenv("X_ACCESS_SECRET"),
    )
    me = client.get_me()
    if me.data:
        print(f"\n✅ API OK — authenticated as @{me.data.username} (id {me.data.id})")
        return 0
    print("\n❌ get_me() returned no user — check app permissions (Read + Write)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
