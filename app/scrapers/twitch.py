"""
Twitch Profile Scraper — ColdReach
=====================================
Fetches public Twitch user profiles via the Twitch GQL API.
No authentication required.
"""

import re
import logging
import requests
from typing import Dict, Optional

from app.scrapers.stealth import random_user_agent, get_requests_proxies
from app.scrapers.utils import extract_email

logger = logging.getLogger(__name__)

_TWITCH_CLIENT_ID = 'kimne78kx3ncx6brgo4mv6wki5h1ko'


def scrape_profile(username: str) -> Optional[Dict]:
    """Fetch Twitch channel data using the public GQL API."""
    username = username.lower().strip()

    headers = {
        'Client-ID':   _TWITCH_CLIENT_ID,
        'User-Agent':  random_user_agent(),
        'Accept':      'application/json',
    }

    query = """
    query {
        user(login: "%s") {
            id login displayName description
            followers { totalCount }
            roles { isPartner isAffiliate }
            channel { socialMedias { name url } }
        }
    }
    """ % username

    try:
        proxies = get_requests_proxies()
        try:
            r = requests.post('https://gql.twitch.tv/gql', headers=headers,
                              json={'query': query}, timeout=20, proxies=proxies)
        except (requests.exceptions.ProxyError, requests.exceptions.ConnectionError) as e:
            if proxies:
                logger.warning(f"Proxy failed for Twitch, retrying direct: {e}")
                r = requests.post('https://gql.twitch.tv/gql', headers=headers,
                                  json={'query': query}, timeout=20)
            else:
                raise

        if r.status_code != 200:
            return None

        data = r.json()
        if 'errors' in data:
            return None

        user_data = data.get('data', {}).get('user')
        if not user_data:
            return None

        return _format_profile(user_data, username)

    except (requests.exceptions.Timeout, requests.exceptions.RequestException, Exception) as e:
        logger.error(f"Error fetching Twitch profile {username}: {e}")
        return None


def _format_profile(data: dict, username: str) -> Dict:
    bio          = data.get('description', '') or ''
    followers    = data.get('followers', {}) or {}
    follower_cnt = followers.get('totalCount', 0)
    roles        = data.get('roles', {}) or {}

    links = [
        s['url'] for s in ((data.get('channel', {}) or {}).get('socialMedias', []) or [])
        if s.get('url')
    ]

    return {
        'username':      data.get('login', username),
        'full_name':     data.get('displayName', ''),
        'bio':           bio,
        'email':         extract_email(bio),
        'follower_count':follower_cnt,
        'is_partner':    roles.get('isPartner', False),
        'is_affiliate':  roles.get('isAffiliate', False),
        'links':         links[:5],
        'website':       links[0] if links else '',
        'platform':      'twitch',
        'profile_url':   f'https://twitch.tv/{data.get("login", username)}',
    }
