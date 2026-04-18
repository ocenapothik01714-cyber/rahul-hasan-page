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

SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/1yVTWR1iPQG9Ub43449Be8oVIbldr0F3oGcxGWwN6q44/export?format=csv&gid=0"

_cache = {"packages": {}, "fetched_at": 0}

# Operator keyword mapping → sheet key
OPERATOR_ALIASES = {
    "robi":        "Robi",
    "রবি":         "Robi",
    "airtel":      "Airtel",
    "এয়ারটেল":    "Airtel",
    "banglalink":  "Banglalink",
    "বাংলালিংক":  "Banglalink",
    "bl":          "Banglalink",
    "ryze":        "Ryze",
    "রাইজ":        "Ryze",
    "rise":        "Ryze",
    "gp":          "Gramenphone",
    "grameenphone":"Gramenphone",
    "grameen":     "Gramenphone",
    "জিপি":        "Gramenphone",
    "গ্রামীণ":    "Gramenphone",
    "skitto":      "Skitto",
    "স্কিটো":     "Skitto",
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


def is_list_request(text: str) -> bool:
    keywords = ["লিস্ট", "list", "প্যাকেজ দেন", "প্যাকেজ দেখান", "সব অফার",
                "অফার লিস্ট", "কি কি আছে", "কী কী আছে", "দাম লিস্ট",
                "প্যাকেজ কি কি", "সব প্যাকেজ", "অফার দেখান"]
    text_lower = text.lower()
    return any(kw in text_lower for kw in keywords)


def get_packages_text(operator_key=None) -> str:
    """Return raw package text. If operator given, return only that one."""
    pkgs = fetch_packages()
    if operator_key and operator_key in pkgs:
        return pkgs[operator_key]
    # All operators
    return "\n\n".join(f"{pkgs[k]}" for k in pkgs)


# ─── System prompt ─────────────────────────────────────────────────────────────

BASE_PROMPT = """\
তুমি Rahul Hasan Offer Point-এর কাস্টমার সার্ভিস। মোবাইল ডেটা/মিনিট/কম্বো প্যাক বিক্রি করি। রাজশাহী, বাংলাদেশ।

পেমেন্ট: 01931112866 — সেন্ড মানি/ক্যাশ ইন (রিচার্জ নয়)। বিকাশ/নগদ/রকেট/উপায়/সেলফিন।
অর্ডার: পেমেন্টের পর শেষ ৪ ডিজিট + স্ক্রিনশট + অফার নম্বর পাঠাতে হবে।
নোট: "চেক"=নম্বর চেক আগে, "অল"=সব নম্বরে, "গিফট"=গিফট নম্বর থেকে।

নিয়ম:
- বাংলায় লিখলে বাংলায়, ইংরেজিতে লিখলে ইংরেজিতে উত্তর দাও। Banglish বুঝতে না পারলে বলো বাংলা বা ইংরেজিতে লিখতে।
- উত্তর ২-৩ লাইনের মধ্যে রাখো।
- প্যাকেজের তথ্য শুধু দেওয়া তালিকা থেকে নাও, বানাবে না।
- পেমেন্ট নম্বর শুধু কিনতে চাইলে দাও।
- পেমেন্ট করেছে বললে: শেষ ৪ ডিজিট না থাকলে চাও → অফার নম্বর না থাকলে চাও → দুটো পেলে বলো "অপেক্ষা করুন, আমরা চালু করে দিব 🙏"
- সমস্যা বা জোরাজুরি হলে বলো: "কল করুন: 01931112866"
- AI বা বট পরিচয় দেবে না। কোনো markdown ব্যবহার করবে না।"""


def build_prompt(operator_key=None) -> str:
    packages = get_packages_text(operator_key)
    label = f"{operator_key} প্যাকেজ" if operator_key else "সব প্যাকেজ"
    return BASE_PROMPT + f"\n\n== {label} ==\n{packages}"


# ─── Shared chat with key/model rotation ──────────────────────────────────────

def _chat(messages: list, max_tokens: int, temperature: float) -> str:
    """Try clients in order; skip ones still in cooldown. On 429, mark cooldown and try next."""
    now = time.time()
    for i, (client, model) in enumerate(_CLIENTS):
        if now < _rate_limited_until.get(i, 0):
            logger.info("Skipping %s (rate-limited, %.0fs left)", model,
                        _rate_limited_until[i] - now)
            continue
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            err = str(e)
            if "429" in err or "rate_limit" in err.lower():
                _rate_limited_until[i] = time.time() + _COOLDOWN_SECS
                logger.warning("Rate limit on %s — cooldown %ds", model, _COOLDOWN_SECS)
                continue
            if "413" in err or "too large" in err.lower():
                logger.warning("Payload too large for %s, trying next client...", model)
                continue
            raise
    raise RuntimeError("All Groq clients exhausted")


# ─── Reply generators ──────────────────────────────────────────────────────────

def generate_comment_reply(comment_text: str, post_text: str = "") -> str:
    operator = detect_operator(comment_text)
    context = f'Post: "{post_text[:200]}"\n' if post_text else ""
    try:
        return _chat(
            messages=[
                {"role": "system", "content": build_prompt(operator)},
                {"role": "user", "content": f"এই কমেন্টের উত্তর দাও।\n{context}Comment: \"{comment_text}\""},
            ],
            max_tokens=250,
            temperature=0.8,
        )
    except Exception as e:
        logger.error("Groq comment reply failed: %s", e)
        return "ধন্যবাদ আপনার মন্তব্যের জন্য! 😊"


def _is_english(text: str) -> bool:
    english_chars = sum(1 for c in text if ord(c) < 128 and c.isalpha())
    total_chars = sum(1 for c in text if c.isalpha())
    return total_chars > 0 and english_chars / total_chars > 0.8


def generate_inbox_reply(user_message: str, history: list = None) -> str:
    operator = detect_operator(user_message)
    lang_instruction = "You MUST reply in English only." if _is_english(user_message) else "অবশ্যই বিশুদ্ধ বাংলায় উত্তর দাও।"
    messages = [{"role": "system", "content": build_prompt(operator) + f"\n\nIMPORTANT: {lang_instruction}"}]
    if history:
        messages.extend(history[-4:])
    messages.append({"role": "user", "content": user_message})
    try:
        return _chat(messages=messages, max_tokens=500, temperature=0.7)
    except Exception as e:
        logger.error("Groq inbox reply failed: %s", e)
        return "আপনার বার্তার জন্য ধন্যবাদ! আমরা শীঘ্রই উত্তর দেব। 🙏"


def get_full_package_list() -> str:
    return "আমাদের সর্বশেষ প্যাকেজ তালিকা:\n\n" + get_packages_text()


def get_operator_package_list(operator_key: str) -> str:
    pkgs = fetch_packages()
    if operator_key in pkgs:
        return pkgs[operator_key]
    return "এই অপারেটরের প্যাকেজ পাওয়া যায়নি।"
