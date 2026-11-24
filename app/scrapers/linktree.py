"""
Link-in-Bio Scraper — ColdReach
==================================
Scrapes public link-in-bio pages across multiple platforms.

Supported:
  - Linktree  (linktr.ee)
  - Stan Store (stan.store)
  - Linkr     (linkr.bio)
  - Bio.link  (bio.link)
"""

import re
import json
import logging
import requests
from typing import Dict, List, Optional

from app.scrapers.stealth import random_user_agent
from app.scrapers.utils import extract_email as _shared_extract_email

logger = logging.getLogger(__name__)

PLATFORMS = {
    'linktree': 'https://linktr.ee/{username}',
    'stan':     'https://stan.store/{username}',
    'linkr':    'https://linkr.bio/{username}',
    'biolink':  'https://bio.link/{username}',
}


def scrape_linktree(username: str) -> Optional[Dict]:
    return _scrape_profile(username, 'linktree')


def scrape_all(username: str) -> Optional[Dict]:
    """Try all link-in-bio platforms and return first match."""
    for platform in PLATFORMS:
        result = _scrape_profile(username, platform)
        if result:
            return result
    return None


def _scrape_profile(username: str, platform: str) -> Optional[Dict]:
    username = username.lstrip('@').strip().lower()
    if platform not in PLATFORMS:
        return None

    url     = PLATFORMS[platform].format(username=username)
    headers = {
        'User-Agent':      random_user_agent(),
        'Accept':          'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }

    try:
        r = requests.get(url, headers=headers, timeout=20)
        if r.status_code == 404:
            return None
        if r.status_code != 200:
            return None

        html = r.text
        if platform == 'linktree':
            return _parse_linktree(html, username)
        if platform == 'stan':
            return _parse_stan(html, username)
        return _parse_generic(html, username, platform)

    except (requests.exceptions.Timeout, requests.exceptions.RequestException) as e:
        logger.error(f"Error fetching {platform}/{username}: {e}")
        return None


def _parse_linktree(html: str, username: str) -> Optional[Dict]:
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if not m:
        return _parse_generic(html, username, 'linktree')

    try:
        data    = json.loads(m.group(1))
        account = data.get('props', {}).get('pageProps', {}).get('account', {})
        if not account:
            return None

        links = [{'title': l.get('title', ''), 'url': l['url']}
                 for l in account.get('links', []) if l.get('url')]
        bio   = account.get('description', '')

        return {
            'username':    username,
            'full_name':   account.get('pageTitle', ''),
            'bio':         bio,
            'email':       _extract_email_from_links(links) or _shared_extract_email(bio),
            'follower_count': 0,
            'website':     _extract_website(links),
            'links':       links,
            'link_count':  len(links),
            'socials':     _extract_socials(links),
            'platform':    'linktree',
            'profile_url': f'https://linktr.ee/{username}',
        }
    except json.JSONDecodeError:
        return _parse_generic(html, username, 'linktree')


def _parse_stan(html: str, username: str) -> Optional[Dict]:
    links = [{'title': '', 'url': u} for u in re.findall(r'href="(https?://[^"]+)"', html)
             if 'stan.store' not in u]
    name_m = re.search(r'"name":"([^"]+)"', html)
    bio_m  = re.search(r'"description":"([^"]*)"', html)
    bio    = bio_m.group(1) if bio_m else ''

    if not (name_m or links):
        return None

    return {
        'username':    username,
        'full_name':   name_m.group(1) if name_m else '',
        'bio':         bio,
        'email':       _extract_email_from_links(links) or _shared_extract_email(bio),
        'follower_count': 0,
        'website':     _extract_website(links),
        'links':       links[:20],
        'link_count':  len(links),
        'socials':     _extract_socials(links),
        'platform':    'stan',
        'profile_url': f'https://stan.store/{username}',
    }


def _parse_generic(html: str, username: str, platform: str) -> Optional[Dict]:
    seen  = set()
    links = []
    for url in re.findall(r'href="(https?://[^"]+)"', html):
        if url not in seen and not any(x in url for x in ['favicon', 'static', 'assets', '.css', '.js']):
            links.append({'title': '', 'url': url})
            seen.add(url)

    title_m = re.search(r'<title>([^<]+)</title>', html)
    meta_m  = re.search(r'<meta[^>]*name="description"[^>]*content="([^"]*)"', html)
    bio     = meta_m.group(1) if meta_m else ''

    if not links:
        return None

    base_url = PLATFORMS.get(platform, '').format(username=username)
    return {
        'username':    username,
        'full_name':   title_m.group(1).strip() if title_m else '',
        'bio':         bio,
        'email':       _extract_email_from_links(links) or _shared_extract_email(bio),
        'follower_count': 0,
        'website':     _extract_website(links),
        'links':       links[:20],
        'link_count':  len(links),
        'socials':     _extract_socials(links),
        'platform':    platform,
        'profile_url': base_url,
    }


def _extract_socials(links: List[Dict]) -> Dict[str, str]:
    patterns = {
        'instagram': r'instagram\.com/([^/?]+)',
        'twitter':   r'(?:twitter|x)\.com/([^/?]+)',
        'youtube':   r'youtube\.com/(?:@|c/|channel/)?([^/?]+)',
        'twitch':    r'twitch\.tv/([^/?]+)',
        'github':    r'github\.com/([^/?]+)',
        'linkedin':  r'linkedin\.com/in/([^/?]+)',
        'discord':   r'discord\.(?:gg|com/invite)/([^/?]+)',
        'spotify':   r'open\.spotify\.com/(?:artist|user)/([^/?]+)',
    }
    socials: Dict[str, str] = {}
    for link in links:
        url = link.get('url', '')
        for platform, pattern in patterns.items():
            if platform not in socials:
                m = re.search(pattern, url, re.IGNORECASE)
                if m:
                    socials[platform] = m.group(1)
    return socials


def _extract_website(links: List[Dict]) -> str:
    social_domains = [
        'instagram.com', 'twitter.com', 'x.com', 'tiktok.com',
        'youtube.com', 'twitch.tv', 'github.com', 'linkedin.com',
        'discord.gg', 'discord.com', 'spotify.com', 'facebook.com',
        'pinterest.com', 'stan.store', 'linktr.ee', 'linkr.bio', 'bio.link',
    ]
    for link in links:
        url = link.get('url', '')
        if url.startswith('http') and not any(d in url.lower() for d in social_domains):
            return url
    return ''


def _extract_email_from_links(links: List[Dict]) -> str:
    for link in links:
        url = link.get('url', '')
        if url.startswith('mailto:'):
            return url.replace('mailto:', '').split('?')[0]
    return ''
