"""
Pinterest Profile Scraper — ColdReach
========================================
Scrapes public Pinterest user profiles via HTML page parsing.
No authentication required.
"""

import re
import json
import logging
import requests
from typing import Dict, Optional

from app.scrapers.stealth import random_user_agent, get_requests_proxies
from app.scrapers.utils import extract_email

logger = logging.getLogger(__name__)


def scrape_profile(username: str) -> Optional[Dict]:
    username = username.strip().lower()
    url      = f'https://www.pinterest.com/{username}/'

    headers = {
        'User-Agent':      random_user_agent(),
        'Accept':          'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }

    try:
        r = requests.get(url, headers=headers, timeout=20, proxies=get_requests_proxies())
        if r.status_code == 404:
            return None
        if r.status_code != 200:
            return None

        html = r.text
        if 'User not found' in html or "This page isn't available" in html:
            return None

        return _extract_profile_data(html, username)

    except (requests.exceptions.Timeout, requests.exceptions.RequestException) as e:
        logger.error(f"Error fetching Pinterest {username}: {e}")
        return None


def _extract_profile_data(html: str, username: str) -> Optional[Dict]:
    results = {}

    m = re.search(r'<script[^>]*id="__PWS_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if m:
        try:
            pws = json.loads(m.group(1))
            ud  = _find_user_in_pws(pws, username)
            if ud:
                results.update(ud)
        except json.JSONDecodeError:
            pass

    if 'full_name' not in results:
        m = re.search(r'"full_name":"([^"]+)"', html)
        if m:
            results['full_name'] = _decode(m.group(1))

    if 'follower_count' not in results:
        m = re.search(r'"follower_count":(\d+)', html)
        if m:
            results['follower_count'] = int(m.group(1))

    if 'bio' not in results:
        m = re.search(r'"about":"([^"]*)"', html)
        if m:
            results['bio'] = _decode(m.group(1))

    if 'website' not in results:
        m = re.search(r'"website_url":"([^"]+)"', html)
        if m:
            results['website'] = m.group(1).replace('\\/', '/')

    m = re.search(r'"pin_count":(\d+)', html)
    if m:
        results['pin_count'] = int(m.group(1))

    if 'full_name' not in results and 'follower_count' not in results:
        return None

    bio = results.get('bio', '')
    return {
        'username':        username,
        'full_name':       results.get('full_name', ''),
        'bio':             bio,
        'email':           extract_email(bio),
        'website':         results.get('website', ''),
        'follower_count':  results.get('follower_count', 0),
        'following_count': results.get('following_count', 0),
        'pin_count':       results.get('pin_count', 0),
        'board_count':     results.get('board_count', 0),
        'platform':        'pinterest',
        'profile_url':     f'https://pinterest.com/{username}/',
    }


def _find_user_in_pws(data, username: str, depth: int = 0) -> Optional[Dict]:
    if depth > 15:
        return None
    if isinstance(data, dict):
        if data.get('username', '').lower() == username.lower() and 'follower_count' in data:
            return {
                'full_name':       data.get('full_name', ''),
                'bio':             data.get('about', ''),
                'follower_count':  data.get('follower_count', 0),
                'following_count': data.get('following_count', 0),
                'website':         data.get('website_url', ''),
                'pin_count':       data.get('pin_count', 0),
                'board_count':     data.get('board_count', 0),
            }
        for v in data.values():
            r = _find_user_in_pws(v, username, depth + 1)
            if r:
                return r
    elif isinstance(data, list):
        for item in data:
            r = _find_user_in_pws(item, username, depth + 1)
            if r:
                return r
    return None


def _decode(text: str) -> str:
    try:
        return text.encode('utf-8').decode('unicode_escape')
    except (UnicodeDecodeError, UnicodeEncodeError):
        return text
