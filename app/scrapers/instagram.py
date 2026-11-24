"""
Instagram Profile Scraper — ColdReach
======================================
Scrapes public Instagram profiles by parsing the HTML page directly.
Uses mobile user agents and optional proxy rotation to avoid rate limits.

Features:
  - Extracts follower/following counts, bio, verification status, links
  - Multiple regex patterns to handle Instagram's varying HTML structures
  - Automatic retry on extraction failures
  - No authentication required (public profiles only)
"""

import re
import random
import time
import logging
import requests
from typing import Dict, Optional

from app.scrapers.stealth import get_requests_proxies
from app.scrapers.utils import extract_email, extract_phone, parse_abbreviated_number

logger = logging.getLogger(__name__)

MOBILE_USER_AGENTS = [
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36',
    'Mozilla/5.0 (Linux; Android 12; Pixel 6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36',
]


def _is_page_not_found(html: str) -> bool:
    signals = [
        "Page Not Found",
        "Sorry, this page isn",
        "The link you followed may be broken",
        "Profile isn\\'t available",
        "profile may have been removed",
        '"HttpErrorPage"',
    ]
    snippet = html[:10000]
    return any(s in snippet for s in signals)


def scrape_profile_no_login(username: str, max_retries: int = 3) -> Optional[Dict]:
    """Scrape an Instagram public profile via mobile HTML parsing."""
    url = f'https://www.instagram.com/{username}/'

    for attempt in range(max_retries):
        proxies = get_requests_proxies()
        headers = {
            'User-Agent': random.choice(MOBILE_USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        }

        try:
            r = requests.get(url, headers=headers, proxies=proxies, timeout=20)

            if r.status_code == 404:
                return None
            if r.status_code == 429:
                raise RuntimeError("Rate limited by Instagram (429). Wait a few minutes.")
            if r.status_code != 200:
                logger.debug(f"HTTP {r.status_code} for @{username}, attempt {attempt + 1}/{max_retries}")
                if attempt < max_retries - 1:
                    time.sleep(1)
                continue

            html = r.text
            if _is_page_not_found(html):
                return None
            if '/accounts/login' in r.url or ('login' in html[:5000].lower() and 'password' in html[:5000].lower()):
                return None

            data = _extract_profile_from_html(html, username)
            if data:
                return data

            if attempt < max_retries - 1:
                time.sleep(1.0)

        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                time.sleep(1)
        except RuntimeError:
            raise
        except Exception as e:
            err = str(e)
            if '429' in err:
                raise RuntimeError("Rate limited by Instagram (429). Wait a few minutes.")
            logger.debug(f"Error scraping @{username}: {e}")
            if attempt < max_retries - 1:
                time.sleep(1)

    return None


def _extract_profile_from_html(html: str, username: str) -> Optional[Dict]:
    results = {}

    for pattern in [r'"username":"([^"]+)"', r'"owner":\{"username":"([^"]+)"']:
        m = re.search(pattern, html)
        if m and m.group(1).lower() == username.lower():
            results['username'] = m.group(1)
            break

    for pattern in [r'"full_name":"([^"]*)"', r'"name":"([^"]*)"',
                    r'<title>([^(<]+)\s*\(@' + re.escape(username) + r'\)']:
        m = re.search(pattern, html, re.IGNORECASE)
        if m:
            results['full_name'] = m.group(1).strip()
            break

    for pattern in [r'"biography":"([^"]*)"', r'"bio":"([^"]*)"', r'"description":"([^"]*)"']:
        m = re.search(pattern, html)
        if m:
            try:
                results['biography'] = m.group(1).encode('utf-8').decode('unicode_escape')
            except (UnicodeDecodeError, UnicodeEncodeError):
                results['biography'] = m.group(1).replace('\\u', '')
            break

    for pattern in [r'"follower_count":(\d+)', r'"edge_followed_by":\{"count":(\d+)\}']:
        m = re.search(pattern, html)
        if m:
            results['follower_count'] = int(m.group(1))
            break

    for pattern in [r'"following_count":(\d+)', r'"edge_follow":\{"count":(\d+)\}']:
        m = re.search(pattern, html)
        if m:
            results['following_count'] = int(m.group(1))
            break

    for pattern in [r'"media_count":(\d+)', r'"edge_owner_to_timeline_media":\{"count":(\d+)\}']:
        m = re.search(pattern, html)
        if m:
            results['media_count'] = int(m.group(1))
            break

    # Abbreviated counts from meta
    meta_patterns = [
        r'content="([\d.,]+[KMB]?)\s*Followers?,\s*([\d.,]+[KMB]?)\s*Following,\s*([\d.,]+[KMB]?)\s*Posts?',
    ]
    for pattern in meta_patterns:
        m = re.search(pattern, html, re.IGNORECASE)
        if m:
            results.setdefault('follower_count',  parse_abbreviated_number(m.group(1)))
            results.setdefault('following_count', parse_abbreviated_number(m.group(2)))
            results.setdefault('media_count',     parse_abbreviated_number(m.group(3)))

    for pattern in [r'"is_verified":(true|false)', r'"verified":(true|false)']:
        m = re.search(pattern, html)
        if m:
            results['is_verified'] = m.group(1) == 'true'
            break

    m = re.search(r'"is_private":(true|false)', html)
    if m:
        results['is_private'] = m.group(1) == 'true'

    m = re.search(r'"is_business_account":(true|false)', html)
    if m:
        results['is_business'] = m.group(1) == 'true'

    for pattern in [r'"external_url":"([^"]+)"', r'"website":"([^"]+)"']:
        m = re.search(pattern, html)
        if m:
            try:
                results['external_url'] = m.group(1).replace('\\/', '/').encode('utf-8').decode('unicode_escape')
            except (UnicodeDecodeError, UnicodeEncodeError):
                results['external_url'] = m.group(1).replace('\\/', '/')
            break

    if not results.get('follower_count'):
        return None

    bio = results.get('biography', '')
    return {
        'username':        results.get('username', username),
        'full_name':       results.get('full_name', ''),
        'bio':             bio,
        'follower_count':  results.get('follower_count', 0),
        'following_count': results.get('following_count', 0),
        'post_count':      results.get('media_count', 0),
        'is_verified':     results.get('is_verified', False),
        'is_private':      results.get('is_private', False),
        'is_business':     results.get('is_business', False),
        'website':         results.get('external_url', ''),
        'email':           extract_email(bio),
        'phone':           extract_phone(bio),
        'platform':        'instagram',
        'profile_url':     f'https://www.instagram.com/{username}/',
    }
