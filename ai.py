"""
AI reply generator using Groq (llama-3.3-70b-versatile).
Package list is fetched live from Google Sheet (Column A = operator, Column B = packages).
"""
import csv
import io
import logging
import time
import requests
from groq import Groq
from config import GROQ_API_KEY, GROQ_API_KEY2, GROQ_API_KEY3, GROQ_API_KEY4, GROQ_API_KEY5

logger = logging.getLogger(__name__)

# 5 API keys, same model — 100k tokens/day each = 500k/day total
# max_retries=0 → disable Groq SDK auto-retry so we control fallback ourselves
_CLIENTS = [
    (Groq(api_key=k, max_retries=0), "llama-3.3-70b-versatile")
    for k in [GROQ_API_KEY, GROQ_API_KEY2, GROQ_API_KEY3, GROQ_API_KEY4, GROQ_API_KEY5]
    if k
]
# Cooldown: if a key hits 429, skip it for this many seconds
_COOLDOWN_SECS = 60
_rate_limited_until: dict[int, float] = {}  # index → timestamp
_next_client_index = 0  # round-robin pointer

SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/1yVTWR1iPQG9Ub43449Be8oVIbldr0F3oGcxGWwN6q44/export?format=csv&gid=0"

_cache = {"packages": {}, "fetched_at": 0}

# Operator keyword mapping → sheet key
OPERATOR_ALIASES = {
    # Robi
    "robi":             "Robi",
    "রবি":              "Robi",
    "rbi":              "Robi",
    "roby":             "Robi",

    # Airtel
    "airtel":           "Airtel",
    "এয়ারটেল":         "Airtel",
    "artl":             "Airtel",
    "aitel":            "Airtel",
    "airtle":           "Airtel",

    # Banglalink
    "banglalink":       "Banglalink",
    "বাংলালিংক":        "Banglalink",
    "bl":               "Banglalink",
    "বি এল":            "Banglalink",
    "বিএল":             "Banglalink",
    "banlalink":        "Banglalink",
    "bangla link":      "Banglalink",
    "banglalik":        "Banglalink",

    # Skitto
    "skitto":           "Skitto",
    "স্কিটো":           "Skitto",
    "স্কিটু":           "Skitto",
    "skito":            "Skitto",
    "skiito":           "Skitto",
    "skitoo":           "Skitto",

    # Ryze
    "ryze":             "Ryze",
    "rise":             "Ryze",
    "rize":             "Ryze",
    "রাইজ":             "Ryze",
    "রাইয":             "Ryze",
    "raiz":             "Ryze",
    "rais":             "Ryze",

    # Grameenphone
    "gp":               "Gramenphone",
    "grameenphone":     "Gramenphone",
    "grameen":          "Gramenphone",
    "gramin":           "Gramenphone",
    "geramin":          "Gramenphone",
    "gramenphone":      "Gramenphone",
    "gramienphone":     "Gramenphone",
    "graminphone":      "Gramenphone",
    "grameenphon":      "Gramenphone",
    "graminephone":     "Gramenphone",
    "জিপি":             "Gramenphone",
    "গ্রামীণ":          "Gramenphone",
    "গ্রামীণফোন":       "Gramenphone",
    "গ্রামিনফোন":       "Gramenphone",
    "গেরামিন":          "Gramenphone",
    "গ্রামিন":          "Gramenphone",
}


def fetch_packages() -> dict:
    """Fetch and parse packages from Google Sheet. Cached 10 min."""
    now = time.time()
    if now - _cache["fetched_at"] < 600 and _cache["packages"]:
        return _cache["packages"]
    try:
        resp = requests.get(SHEET_CSV_URL, timeout=10)
        resp.encoding = "utf-8"
        reader = csv.reader(io.StringIO(resp.text))
        packages = {}
        for row in reader:
            if len(row) >= 2 and row[0].strip():
                packages[row[0].strip()] = row[1].strip()
        _cache["packages"] = packages
        _cache["fetched_at"] = now
        logger.info("Packages refreshed: %s", list(packages.keys()))
        return packages
    except Exception as e:
        logger.error("Sheet fetch failed: %s", e)
        return _cache["packages"]


def detect_operator(text: str):
    """Return sheet key if user mentioned a specific operator, else None."""
    text_lower = text.lower()
    for alias, key in OPERATOR_ALIASES.items():
        if alias in text_lower:
            return key
    return None



# ─── System prompt ─────────────────────────────────────────────────────────────

BASE_PROMPT = """\
তুমি Rahul Hasan Offer Point-এর কাস্টমার সার্ভিস। মোবাইল ডেটা/মিনিট/কম্বো প্যাক বিক্রি করি। রাজশাহী, বাংলাদেশ।

পেমেন্ট: 01931112866 — সেন্ড মানি/ক্যাশ ইন (রিচার্জ নয়)। বিকাশ/নগদ/রকেট/উপায়/সেলফিন।
অর্ডার: পেমেন্টের পর → শেষ ৪ ডিজিট + স্ক্রিনশট + অফার নম্বর পাঠাও।
নোট: "চেক"=নম্বর চেক আগে | "অল"=সব নম্বরে | "গিফট"=গিফট নম্বর থেকে।

নিয়ম:
- সবসময় বাংলায় উত্তর দাও।
- উত্তর ২-৩ লাইনের বেশি নয়।
- কেউ নির্দিষ্ট প্যাকেজের দাম জিজ্ঞেস করলে (যেমন "60 GB কত?") → কথোপকথনের আগের তালিকা থেকে খুঁজে সঠিক দাম বলো।
- তালিকায় না থাকলে বলো: "এই প্যাকেজটি এখন নেই।"
- পেমেন্ট নম্বর শুধু কিনতে চাইলে দাও।
- পেমেন্ট করেছে বললে: শেষ ৪ ডিজিট না থাকলে চাও → অফার নম্বর না থাকলে চাও → দুটো পেলে বলো "অপেক্ষা করুন, চালু করে দিব 🙏"
- সমস্যা বা জোরাজুরি হলে বলো: "কল করুন: 01931112866"
- AI বা বট পরিচয় দেবে না। কোনো markdown ব্যবহার করবে না।"""


COMMENT_PROMPT = """\
তুমি Rahul Hasan Offer Point-এর কাস্টমার সার্ভিস। মোবাইল ডেটা/মিনিট/কম্বো প্যাক বিক্রি করি। রাজশাহী, বাংলাদেশ।
নিয়ম:
- কমেন্টের উত্তর ১-২ লাইনে দাও, বন্ধুত্বপূর্ণভাবে।
- বিস্তারিত দাম বা অফার বলবে না — ইনবক্সে মেসেজ করতে বলো।
- সবসময় বাংলায় উত্তর দাও।
- AI বা বট পরিচয় দেবে না। কোনো markdown ব্যবহার করবে না।"""


def build_prompt() -> str:
    return BASE_PROMPT


# ─── Shared chat with key/model rotation ──────────────────────────────────────

def _chat(messages: list, max_tokens: int, temperature: float) -> str:
    """Round-robin across clients; skip ones in cooldown. On 429, mark cooldown and try next."""
    global _next_client_index
    now = time.time()
    n = len(_CLIENTS)
    for attempt in range(n):
        i = (_next_client_index + attempt) % n
        client, model = _CLIENTS[i]
        if now < _rate_limited_until.get(i, 0):
            logger.info("Skipping key %d (rate-limited, %.0fs left)", i,
                        _rate_limited_until[i] - now)
            continue
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            _next_client_index = (i + 1) % n  # advance pointer on success
            return resp.choices[0].message.content.strip()
        except Exception as e:
            err = str(e)
            if "429" in err or "rate_limit" in err.lower():
                _rate_limited_until[i] = time.time() + _COOLDOWN_SECS
                logger.warning("Rate limit on key %d — cooldown %ds", i, _COOLDOWN_SECS)
                continue
            if "413" in err or "too large" in err.lower():
                logger.warning("Payload too large for %s, trying next client...", model)
                continue
            raise
    raise RuntimeError("All Groq clients exhausted")


# ─── Reply generators ──────────────────────────────────────────────────────────

def generate_comment_reply(comment_text: str, post_text: str = "") -> str:
    context = f'Post: "{post_text[:150]}"\n' if post_text else ""
    try:
        return _chat(
            messages=[
                {"role": "system", "content": COMMENT_PROMPT},
                {"role": "user", "content": f"{context}Comment: \"{comment_text}\""},
            ],
            max_tokens=120,
            temperature=0.7,
        )
    except Exception as e:
        logger.error("Groq comment reply failed: %s", e)
        return "ধন্যবাদ! বিস্তারিত জানতে ইনবক্সে মেসেজ করুন। 😊"




def generate_inbox_reply(user_message: str, history: list = None) -> str:
    messages = [{"role": "system", "content": build_prompt()}]
    if history:
        messages.extend(history[-4:])
    messages.append({"role": "user", "content": user_message})
    try:
        return _chat(messages=messages, max_tokens=500, temperature=0.7)
    except Exception as e:
        logger.error("Groq inbox reply failed: %s", e)
        return "আপনার বার্তার জন্য ধন্যবাদ! আমরা শীঘ্রই উত্তর দেব। 🙏"


def get_operator_package_list(operator_key: str) -> str:
    pkgs = fetch_packages()
    if operator_key in pkgs:
        return pkgs[operator_key]
    return "এই অপারেটরের প্যাকেজ পাওয়া যায়নি।"
