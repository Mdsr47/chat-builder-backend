"""
Instagram Graph API Integration
Handles: OAuth flow, webhook verification, incoming DMs/Comments, auto-replies via AI
"""
import httpx
import os
import json
import uuid
import re
from datetime import datetime
from typing import Optional
from urllib.parse import quote_plus
from dotenv import load_dotenv
load_dotenv()

# ── Config (set these in your environment or .env) ──────────────────────────
IG_APP_ID        = os.getenv("IG_APP_ID", "YOUR_FB_APP_ID")
IG_APP_SECRET    = os.getenv("IG_APP_SECRET", "YOUR_FB_APP_SECRET")
IG_REDIRECT_URI  = os.getenv("IG_REDIRECT_URI", "http://127.0.0.1:8000/instagram/callback")
IG_VERIFY_TOKEN  = os.getenv("IG_VERIFY_TOKEN", "my_verify_token_secret_123")

GRAPH_BASE       = "https://graph.facebook.com/v25.0"


# ── OAuth ────────────────────────────────────────────────────────────────────

def build_oauth_url(state: str) -> str:
    """Returns the Facebook OAuth URL to redirect the user to."""
    scope = "instagram_basic,instagram_manage_messages,instagram_manage_comments,pages_show_list,pages_read_engagement"
    return (
        f"https://www.facebook.com/v25.0/dialog/oauth"
        f"?client_id={IG_APP_ID}"
        f"&redirect_uri={quote_plus(IG_REDIRECT_URI)}"
        f"&scope={quote_plus(scope)}"
        f"&response_type=code"
        f"&state={quote_plus(state)}"
    )


async def exchange_code_for_token(code: str) -> dict:
    """Exchange the short-lived code for a long-lived user access token."""
    async with httpx.AsyncClient() as client:
        # 1. Get short-lived token
        r = await client.get(f"{GRAPH_BASE}/oauth/access_token", params={
            "client_id": IG_APP_ID,
            "client_secret": IG_APP_SECRET,
            "redirect_uri": IG_REDIRECT_URI,
            "code": code,
        })
        r.raise_for_status()
        short = r.json()
        short_token = short["access_token"]

        # 2. Exchange for long-lived token
        r2 = await client.get(f"{GRAPH_BASE}/oauth/access_token", params={
            "grant_type": "fb_exchange_token",
            "client_id": IG_APP_ID,
            "client_secret": IG_APP_SECRET,
            "fb_exchange_token": short_token,
        })
        r2.raise_for_status()
        long_lived = r2.json()
        return long_lived  # {"access_token": ..., "token_type": ..., "expires_in": ...}


async def get_instagram_accounts(user_access_token: str) -> list[dict]:
    """
    Returns a list of Instagram Business accounts connected to the user's FB pages.
    Each item: {"ig_id", "username", "page_id", "page_name", "page_token"}
    """
    async with httpx.AsyncClient() as client:
        # Get pages the user manages
        r = await client.get(f"{GRAPH_BASE}/me/accounts", params={
            "access_token": user_access_token,
            "fields": "id,name,access_token,instagram_business_account{id,username,profile_picture_url}"
        })
        r.raise_for_status()
        pages = r.json().get("data", [])
        print(f"[IG Accounts] FB pages found: {len(pages)}")
        for p in pages:
            ig = p.get("instagram_business_account")
            print(f"  Page: id={p['id']}, name={p['name']}, has_ig={ig is not None}, ig={ig}")

    accounts = []
    for page in pages:
        ig = page.get("instagram_business_account")
        if ig:
            accounts.append({
                "ig_id": ig["id"],
                "username": ig.get("username", ""),
                "profile_pic_url": ig.get("profile_picture_url"),  # optional
                "page_id": page["id"],
                "page_name": page["name"],
                "page_token": page["access_token"],  # page-scoped token for sending
            })
    return accounts


async def subscribe_page_to_webhooks(page_id: str, page_access_token: str):
    """Subscribe the FB Page to the webhook for messages & feed (comments)."""
    async with httpx.AsyncClient() as client:
        r = await client.post(f"{GRAPH_BASE}/{page_id}/subscribed_apps", params={
            "access_token": page_access_token,
            "subscribed_fields": "messages,messaging_postbacks,feed"
        })
        return r.json()


async def send_dm(recipient_ig_id: str, message: str, page_access_token: str) -> dict:
    """Send a DM to an Instagram user via the Messenger Platform."""
    async with httpx.AsyncClient() as client:
        r = await client.post(f"{GRAPH_BASE}/me/messages", params={
            "access_token": page_access_token
        }, json={
            "recipient": {"id": recipient_ig_id},
            "message": {"text": message[:1000]},  # IG DM limit
        })
        return r.json()


async def reply_to_comment(comment_id: str, message: str, page_access_token: str) -> dict:
    """Reply to an Instagram comment."""
    async with httpx.AsyncClient() as client:
        r = await client.post(f"{GRAPH_BASE}/{comment_id}/replies", params={
            "access_token": page_access_token
        }, json={"message": message[:2200]})
        return r.json()
