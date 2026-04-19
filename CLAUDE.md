# Rahul Hasan Offer Point — Facebook Bot

## What This Is
A polling-based Facebook auto-reply bot for the "Rahul Hasan Offer Point" page.
Replies to post comments and Messenger inbox using Groq AI (llama-3.3-70b-versatile).
Package prices are fetched live from a Google Sheet — update the sheet, bot picks it up automatically.

## Business Info
- **Page:** Rahul Hasan Offer Point
- **Page ID:** 1048617111672572
- **Location:** Rajshahi, Bangladesh
- **Service:** Mobile data, minute, and combo packages
- **Operators:** Grameenphone (GP), Banglalink, Ryze, Robi, Airtel, Skitto
- **Payment number:** 01931112866 (bKash / Nagad / Rocket / Upay / Selfin — send money only, no recharge)

## Files
| File | Purpose |
|---|---|
| `poller.py` | Main bot — polls comments and inbox every 15s |
| `ai.py` | Groq AI reply generator + package sheet fetcher |
| `config.py` | Loads env vars from `.env` |
| `fb_api.py` | Facebook Graph API helpers |
| `server.py` | Flask entry point for Render deployment |
| `post_offer.py` | Manual script to post an operator's offer to the page |
| `render.yaml` | Render deployment config |
| `requirements.txt` | Python dependencies |
| `.env` | Secrets — never commit this |

## Running Locally
```bash
source venv/bin/activate
python poller.py
```

## Deploying to Render
- Hosted at: https://rahul-hasan-page.onrender.com
- Start command: `gunicorn server:app --bind 0.0.0.0:$PORT --timeout 120`
- UptimeRobot pings `/health` every 5 minutes to keep it awake
- Push to GitHub → Render auto-deploys

## GitHub Repo
https://github.com/ocenapothik01714-cyber/rahul-hasan-page

## Google Sheet (Package Prices)
- URL: https://docs.google.com/spreadsheets/d/1yVTWR1iPQG9Ub43449Be8oVIbldr0F3oGcxGWwN6q44
- Column A = operator name, Column B = package list
- Cached for 10 minutes, refreshed automatically
- Operators in sheet: Robi, Airtel, Banglalink, Ryze, Gramenphone, Skitto

## Groq AI
- Model: `llama-3.3-70b-versatile`
- 5 API keys rotating (round-robin) — 100k tokens/day each = 500k/day total
- On 429 rate limit: marks key in 60s cooldown, moves to next key
- Keys stored as GROQ_API_KEY through GROQ_API_KEY5 in `.env`

## Bot Behavior

### Comments
- Short 1-2 line AI reply using `COMMENT_PROMPT` (no package data in prompt)
- Appends: "বিস্তারিত জানতে ইনবক্সে মেসেজ করুন 📩"

### Inbox (Messenger)
- If message matches `is_list_request()` → serve raw sheet data (no AI, no hallucination)
- If operator detected → inject only that operator's packages into AI context
- Otherwise → AI reply with last 4 turns of conversation history
- Only ONE reply per poll cycle (prevents double-reply across conversations)

### Special Cases
| Trigger | Bot Response |
|---|---|
| Voice message | Asks to send text |
| Image only | Silently ignored |
| Banglish | Asks to write in Bangla or English |
| Payment claimed | Asks for last 4 digits → offer number → "অপেক্ষা করুন" |
| Insisting / problem | "কল করুন: 01931112866" |
| Language | Pure Bangla or pure English, never mixed |

## Daily Auto-Posts
Configured in `poller.py` under `AUTO_POSTS`:
```python
AUTO_POSTS = [
    ("12:00", "Robi"),
    ("12:10", "Airtel"),
    ("12:20", "Banglalink"),
    ("12:30", "Gramenphone"),
    ("12:40", "Skitto"),
]
```
Posts each operator's package list once per day at the set time.

## Manual Post
```bash
python post_offer.py banglalink
python post_offer.py gp
```

## Facebook App
- **App ID:** 3361382464031104
- **App Mode:** Live
- **Permissions:** pages_read_engagement, pages_manage_engagement, pages_messaging, pages_manage_posts
- Page Access Token: never-expiring (stored in `.env`)
