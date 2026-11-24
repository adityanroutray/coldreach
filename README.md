# ColdReach ⚡

Cold outreach intelligence engine for modern growth teams and agency workflows. Extracts public creator and business profiles across 7 primary platforms, enriches contacts with MX-verified email discovery, and exports clean CSV datasets.

Author: **[Adityan Routray](https://adityanroutray.online/)**  
Deployed & Maintained by [ScaleWeb.in](https://scaleweb.in)

---

## ⚡ Channels Supported

- **Instagram**: Public bio, follower counts, external links, public contact numbers
- **LinkedIn**: Member headlines, bio summaries, contact links (via `li_at` cookie)
- **GitHub**: Public profile metadata, bio, location, developer website
- **YouTube**: Channel metadata, subscriber stats, business contact links
- **Twitch**: Public streamer profiles, partner status, channel links
- **Link-in-Bio**: Aggregated social endpoints (Linktree, Stan Store, Bio.link)
- **Pinterest**: Creator profile metadata, follower metrics, merchant links


---

## 🚀 Quickstart

```bash
# Clone repository
git clone https://github.com/adityanroutray/coldreach.git
cd coldreach

# Install dependencies
pip install -r requirements.txt

# Launch interactive CLI
python coldreach.py
```

---

## ⚙️ Configuration (`.env`)

Copy `.env.example` to `.env`:
```ini
# LinkedIn Voyager session
LINKEDIN_COOKIE=your_li_at_cookie_value

# Optional Proxy routing
CR_PROXY=http://user:pass@host:port
CR_FREE_PROXY=true
```

---

## 📬 Contact & Support

Have questions, custom engine requests, or feedback? Get in touch directly:
- **Contact:** [adityanroutray.online/#contact](https://adityanroutray.online/#contact)
- **Author:** [Adityan Routray](https://adityanroutray.online/)
- **Email:** [adityanroutray@gmail.com](mailto:adityanroutray@gmail.com)

---

## 📄 License
MIT License © 2026 Adityan Routray
