"""
LinkedIn Profile Scraper — ColdReach
======================================
Fetches LinkedIn public profiles via the Voyager API using a session cookie.

Setup:
  1. Log into LinkedIn in Chrome
  2. F12 → Application → Cookies → linkedin.com → copy 'li_at' value
  3. Set LINKEDIN_COOKIE=your_li_at_value in .env

Note: li_at cookies expire periodically and must be refreshed.
"""

import json
import logging
import os
import re
from typing import Dict, Optional

import httpx

from app.scrapers.stealth import random_user_agent, get_httpx_proxy
from app.scrapers.utils import extract_email

logger = logging.getLogger(__name__)

_session_cache = {'client': None, 'csrf': None}


def _get_li_cookie() -> Optional[str]:
    cookie = os.environ.get('LINKEDIN_COOKIE', '').strip()
    if not cookie:
        return None
    if len(cookie) < 50:
        logger.warning("LinkedIn cookie seems too short — may be invalid")
    return cookie


def _get_session():
    if _session_cache['client'] and _session_cache['csrf']:
        return _session_cache['client'], _session_cache['csrf']

    cookie = _get_li_cookie()
    if not cookie:
        return None, None

    client = httpx.Client(follow_redirects=True, timeout=20)
    client.cookies.set('li_at', cookie, domain='.linkedin.com')
    client.get('https://www.linkedin.com/feed/')

    csrf = None
    for c in client.cookies.jar:
        if c.name == 'JSESSIONID':
            csrf = c.value.strip('"')
            break

    if not csrf:
        logger.error("Could not extract CSRF token from LinkedIn")
        return None, None

    _session_cache['client'] = client
    _session_cache['csrf']   = csrf
    return client, csrf


def scrape_linkedin_profile(username: str) -> Optional[Dict]:
    """Scrape a LinkedIn profile. Returns a profile dict or None."""
    cookie = _get_li_cookie()
    if not cookie:
        logger.error("LINKEDIN_COOKIE not set in .env")
        return None

    client, csrf = _get_session()
    if not client or not csrf:
        logger.error("Failed to init LinkedIn session — cookie may be expired.")
        return None

    headers = {
        'csrf-token':                  csrf,
        'Accept':                      'application/vnd.linkedin.normalized+json+2.1',
        'x-li-lang':                   'en_US',
        'x-restli-protocol-version':   '2.0.0',
    }

    url = (
        f'https://www.linkedin.com/voyager/api/identity/dash/profiles'
        f'?q=memberIdentity&memberIdentity={username}'
    )

    try:
        resp = client.get(url, headers=headers)
    except httpx.RequestError as e:
        logger.error(f"Request error for {username}: {e}")
        return None

    if resp.status_code == 403:
        logger.error(f"Profile {username} is restricted")
        return None
    if resp.status_code == 401:
        _session_cache.update({'client': None, 'csrf': None})
        logger.error("LinkedIn cookie expired — re-export your li_at cookie.")
        return None
    if resp.status_code != 200:
        logger.error(f"HTTP {resp.status_code} for {username}")
        return None

    try:
        data = resp.json()
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON response for {username}")
        return None

    profile_data = None
    for item in data.get('included', []):
        if 'firstName' in item and 'lastName' in item:
            profile_data = item
            break

    if not profile_data:
        logger.error(f"No profile data found for {username}")
        return None

    summary = profile_data.get('summary', '')
    if not summary:
        multi = profile_data.get('multiLocaleSummary', {})
        summary = multi.get('en_US', '') if isinstance(multi, dict) else ''

    websites = [
        w['url'] for w in (profile_data.get('websites') or [])
        if isinstance(w, dict) and w.get('url')
    ]

    return {
        'platform':      'linkedin',
        'username':      profile_data.get('publicIdentifier', username),
        'full_name':     f"{profile_data.get('firstName', '')} {profile_data.get('lastName', '')}".strip(),
        'headline':      profile_data.get('headline', ''),
        'bio':           summary,
        'profile_url':   f"https://www.linkedin.com/in/{profile_data.get('publicIdentifier', username)}/",
        'is_verified':   profile_data.get('showVerificationBadge', False),
        'is_premium':    profile_data.get('premium', False),
        'is_influencer': profile_data.get('influencer', False),
        'website':       websites[0] if websites else '',
        'email':         extract_email(summary),
    }
