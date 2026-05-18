"""
Twitter / X posting — cookie/twikit by default (free). Official tweepy API is opt-in.

Default: data/twitter_cookies.json via twikit (TWITTER_BACKEND=cookies).
Opt-in paid API: set TWITTER_BACKEND=official and X_API_* keys in .env.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Optional

from dotenv import load_dotenv

from core.paths import PROJECT_ROOT, get_data_path
import core.config as config

load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

COOKIES_FILE = get_data_path("twitter_cookies.json")


def _env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def has_official_api_credentials() -> bool:
    return all(
        _env(k)
        for k in (
            "X_API_KEY",
            "X_API_SECRET",
            "X_ACCESS_TOKEN",
            "X_ACCESS_SECRET",
        )
    )


def has_cookie_auth() -> bool:
    return os.path.exists(COOKIES_FILE)


def twitter_credentials_status() -> dict:
    """Summary for healthcheck / logs."""
    backend = resolve_backend()
    return {
        "official_api": has_official_api_credentials(),
        "cookies": has_cookie_auth(),
        "backend": backend,
        "ready": backend != "none",
    }


def resolve_backend() -> str:
    # Default: cookies (free). Official API only when explicitly requested.
    forced = (_env("TWITTER_BACKEND") or "cookies").lower()
    if forced == "official":
        return "official" if has_official_api_credentials() else "none"
    if has_cookie_auth():
        return "cookies"
    if forced == "auto" and has_official_api_credentials():
        return "official"
    return "none"


def _is_error_226(exc: Exception) -> bool:
    msg = str(exc)
    return "226" in msg or "automated" in msg.lower()


class TwitterClient:
    """Unified poster: tweepy (official) or twikit (cookies)."""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.backend = "dry_run" if dry_run else resolve_backend()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._twikit = None
        self._tweepy_client = None
        self._tweepy_api = None

        if dry_run:
            print("[DRY-RUN] Twitter connection skipped.")
            return

        if self.backend == "none":
            raise RuntimeError(
                "No Twitter credentials. Set X_API_* in .env (recommended) "
                f"or run tools/setup_twitter_cookies.py → {COOKIES_FILE}"
            )

        if self.backend == "official":
            self._init_official()
            print("✅ Twitter (official API v2 / tweepy) ready.")
        else:
            self._init_twikit()
            print("✅ Twitter (twikit / cookies) ready.")

    def _init_official(self):
        import tweepy

        auth = tweepy.OAuth1UserHandler(
            _env("X_API_KEY"),
            _env("X_API_SECRET"),
            _env("X_ACCESS_TOKEN"),
            _env("X_ACCESS_SECRET"),
        )
        self._tweepy_api = tweepy.API(auth, wait_on_rate_limit=True)
        self._tweepy_client = tweepy.Client(
            consumer_key=_env("X_API_KEY"),
            consumer_secret=_env("X_API_SECRET"),
            access_token=_env("X_ACCESS_TOKEN"),
            access_token_secret=_env("X_ACCESS_SECRET"),
            wait_on_rate_limit=True,
        )

    def _init_twikit(self):
        if not has_cookie_auth():
            raise RuntimeError(f"Twitter cookies not found: {COOKIES_FILE}")
        from twikit import Client

        self._loop = asyncio.new_event_loop()
        client = Client("en-US")
        client.load_cookies(COOKIES_FILE)
        self._twikit = client

    def thread_delay(self, is_reply: bool) -> int:
        if is_reply:
            return config.TWITTER_THREAD_DELAY_SECONDS
        return config.TWITTER_POST_DELAY_SECONDS

    def post(
        self,
        text: str,
        media_path: Optional[str] = None,
        reply_to_id: Optional[str] = None,
    ) -> Optional[str]:
        if self.dry_run:
            print(f"\n[DRY-RUN] TWEET (reply_to={reply_to_id}):\n  {text[:120]}...")
            if media_path:
                print(f"  MEDIA: {media_path}")
            return "DRY_RUN_FAKE_ID"

        if self.backend == "official":
            return self._post_official(text, media_path, reply_to_id)
        return self._post_twikit_with_retry(text, media_path, reply_to_id)

    def _post_official(
        self,
        text: str,
        media_path: Optional[str],
        reply_to_id: Optional[str],
    ) -> Optional[str]:
        media_ids = []
        if media_path and os.path.exists(str(media_path)):
            print(f"   🖼️ Uploading: {os.path.basename(str(media_path))}")
            try:
                uploaded = self._tweepy_api.media_upload(filename=str(media_path))
                media_ids = [uploaded.media_id]
            except Exception as e:
                print(f"   ⚠️ Media upload failed: {e}")

        kwargs = {"text": text}
        if media_ids:
            kwargs["media_ids"] = media_ids
        if reply_to_id and str(reply_to_id).isdigit():
            kwargs["in_reply_to_tweet_id"] = int(reply_to_id)

        try:
            resp = self._tweepy_client.create_tweet(**kwargs)
            tweet_id = str(resp.data["id"])
            print(f"   ✅ Posted! ID: {tweet_id}")
            return tweet_id
        except Exception as e:
            print(f"   ❌ Official API error: {e}")
            return None

    def _post_twikit_with_retry(
        self,
        text: str,
        media_path: Optional[str],
        reply_to_id: Optional[str],
    ) -> Optional[str]:
        delays = [
            0,
            config.TWITTER_226_BASE_DELAY,
            config.TWITTER_226_BASE_DELAY * 2,
        ][: config.TWITTER_226_MAX_RETRIES]

        last_err = None
        for attempt, wait in enumerate(delays):
            if wait > 0:
                print(f"   ⏳ Error 226 — retry {attempt}/{len(delays) - 1} in {wait}s...")
                time.sleep(wait)
            try:
                tweet_id = self._post_twikit_once(text, media_path, reply_to_id)
                if tweet_id:
                    return tweet_id
            except Exception as e:
                last_err = e
                if _is_error_226(e) and attempt < len(delays) - 1:
                    continue
                print(f"   ❌ twikit error: {e}")
                return None

        if last_err:
            print(f"   ❌ twikit error: {last_err}")
        return None

    def _post_twikit_once(
        self,
        text: str,
        media_path: Optional[str],
        reply_to_id: Optional[str],
    ) -> Optional[str]:
        async def _async_post():
            media_ids = []
            if media_path and os.path.exists(str(media_path)):
                print(f"   🖼️ Uploading: {os.path.basename(str(media_path))}")
                media_id_result = await self._twikit.upload_media(str(media_path))
                if hasattr(media_id_result, "media_id"):
                    media_ids = [media_id_result.media_id]
                elif isinstance(media_id_result, (str, int)):
                    media_ids = [str(media_id_result)]

            reply_to_param = (
                str(reply_to_id)
                if reply_to_id and str(reply_to_id).isdigit()
                else None
            )
            media_entities = [{"media_id": mid, "tagged_users": []} for mid in media_ids]

            response, _ = await self._twikit.gql.create_tweet(
                False,
                text,
                media_entities,
                None,
                reply_to_param,
                None,
                None,
                False,
                None,
                None,
                None,
            )

            if isinstance(response, dict) and response.get("errors"):
                raise Exception(f"Twitter API errors: {response['errors']}")

            return response["data"]["create_tweet"]["tweet_results"]["result"]["rest_id"]

        tweet_id = self._loop.run_until_complete(_async_post())
        if not tweet_id:
            return None
        print(f"   ✅ Posted! ID: {tweet_id}")
        return str(tweet_id)
