"""
ColdReach — Platform Scrapers
==============================
Supported platforms (7 primary channels):
    - Instagram  (no auth)
    - LinkedIn   (requires li_at session cookie)
    - GitHub     (no auth — GitHub REST API)
    - YouTube    (no auth)
    - Twitch     (no auth — public GQL)
    - Linktree   (no auth — covers Linktree, Stan, Bio.link)
    - Pinterest  (no auth)
"""

from .instagram import scrape_profile_no_login as scrape_instagram
from .linkedin   import scrape_linkedin_profile  as scrape_linkedin
from .github     import scrape_profile           as scrape_github
from .youtube    import scrape_channel           as scrape_youtube
from .twitch     import scrape_profile           as scrape_twitch
from .linktree   import scrape_linktree, scrape_all as scrape_linkbio
from .pinterest  import scrape_profile           as scrape_pinterest

__all__ = [
    "scrape_instagram",
    "scrape_linkedin",
    "scrape_github",
    "scrape_youtube",
    "scrape_twitch",
    "scrape_linktree",
    "scrape_linkbio",
    "scrape_pinterest",
]
