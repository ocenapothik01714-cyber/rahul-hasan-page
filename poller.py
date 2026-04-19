"""
Polling-based Facebook auto-reply bot.
No webhook, no ngrok, no app review needed.

Usage:
    source venv/bin/activate
    python poller.py
"""
import time
import logging
import requests
from datetime import datetime, timezone, timedelta

BD_TZ = timedelta(hours=6)  # Bangladesh = UTC+6
from config import PAGE_ACCESS_TOKEN, PAGE_ID
from ai import (generate_comment_reply, generate_inbox_reply,
                detect_operator, get_operator_package_list)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

GRAPH = "https://graph.facebook.com/v25.0"
POLL_INTERVAL = 15  # seconds between each check

# ── Daily auto-post schedule ───────────────────────────────────────────────────
AUTO_POSTS = [
    ("14:20", "Robi"),
    ("14:30", "Airtel"),
    ("14:40", "Banglalink"),
    ("14:50", "Gramenphone"),
    ("15:00", "Skitto"),
]

_posted_today: set = set()  # tracks "HH:MM" already posted today
_last_post_date = None

# Remember what we already replied to (in-memory, resets on restart)
replied_comments: set = set()
replied_messages: set = set()


# ─── Comment polling ───────────────────────────────────────────────────────────

def get_recent_posts():
    resp = requests.get(
        f"{GRAPH}/{PAGE_ID}/posts",
        params={
            "access_token": PAGE_ACCESS_TOKEN,
            "limit": 5,
            "fields": "id,message,story,created_time",
        },
        timeout=10,
    )
    if not resp.ok:
        logger.error("Failed to fetch posts: %s", resp.text)
        return []
    return resp.json().get("data", [])


def get_comments(post_id):
    resp = requests.get(
        f"{GRAPH}/{post_id}/comments",
        params={
            "access_token": PAGE_ACCESS_TOKEN,
            "filter": "stream",
            "limit": 25,
            "fields": "id,from,message,created_time,can_reply_privately",
        },
        timeout=10,
    )
    if not resp.ok:
        logger.error("Failed to fetch comments for %s: %s", post_id, resp.text)
        return []
    return resp.json().get("data", [])


def reply_to_comment(comment_id, message):
    resp = requests.post(
        f"{GRAPH}/{comment_id}/comments",
        data={"message": message, "access_token": PAGE_ACCESS_TOKEN},
        timeout=10,
    )
    if resp.ok:
        logger.info("Replied to comment %s", comment_id)
    else:
        logger.error("Failed comment reply %s: %s", comment_id, resp.text)


def check_comments(reply=True):
    posts = get_recent_posts()
    for post in posts:
        comments = get_comments(post["id"])
        for comment in comments:
            cid = comment["id"]
            from_id = comment.get("from", {}).get("id", "")
            if from_id == PAGE_ID:
                continue
            if cid in replied_comments:
                continue
            replied_comments.add(cid)
            if reply:
                post_text = post.get("message") or post.get("story") or ""
                comment_text = comment.get("message", "")
                ai_reply = generate_comment_reply(comment_text, post_text)
                full_reply = ai_reply + "\n\n📩 বিস্তারিত জানতে আমাদের ইনবক্সে মেসেজ করুন।"
                reply_to_comment(cid, full_reply)


# ─── Messenger send ────────────────────────────────────────────────────────────

def send_message(recipient_id, message):
    resp = requests.post(
        f"{GRAPH}/me/messages",
        json={
            "recipient": {"id": recipient_id},
            "message": {"text": message},
        },
        params={"access_token": PAGE_ACCESS_TOKEN},
        timeout=10,
    )
    if resp.ok:
        logger.info("Sent DM to user %s", recipient_id)
    else:
        logger.error("Failed DM to %s: %s", recipient_id, resp.text)


# ─── Inbox / Messenger polling ─────────────────────────────────────────────────

def get_conversations():
    resp = requests.get(
        f"{GRAPH}/{PAGE_ID}/conversations",
        params={"access_token": PAGE_ACCESS_TOKEN, "limit": 10},
        timeout=10,
    )
    if not resp.ok:
        logger.warning("Cannot fetch conversations (may need pages_messaging permission): %s", resp.text)
        return []
    return resp.json().get("data", [])


def get_messages_in_conversation(conv_id):
    resp = requests.get(
        f"{GRAPH}/{conv_id}/messages",
        params={
            "access_token": PAGE_ACCESS_TOKEN,
            "fields": "id,from,message,created_time,attachments",
            "limit": 10,  # fetch last 10 for history context
        },
        timeout=10,
    )
    if not resp.ok:
        return []
    # API returns newest first — reverse so oldest is first
    return list(reversed(resp.json().get("data", [])))


def check_inbox(reply=True):
    conversations = get_conversations()

    # Seeding mode: mark ALL existing user messages as seen so we never reply to old ones
    if not reply:
        for conv in conversations:
            for msg in get_messages_in_conversation(conv["id"]):
                mid = msg.get("id")
                sender_id = msg.get("from", {}).get("id", "")
                if mid and sender_id != PAGE_ID:
                    replied_messages.add(mid)
        return

    # Collect latest unreplied message from each conversation
    candidates = []
    conv_messages_map = {}
    for conv in conversations:
        messages = get_messages_in_conversation(conv["id"])
        conv_messages_map[conv["id"]] = messages
        for msg in reversed(messages):  # newest first
            mid = msg.get("id")
            sender_id = msg.get("from", {}).get("id", "")
            if not mid or sender_id == PAGE_ID:
                continue
            if mid in replied_messages:
                continue
            text = msg.get("message", "")
            attachments = msg.get("attachments", {}).get("data", [])
            if not text and not attachments:
                continue
            candidates.append((msg, conv["id"]))
            break  # one per conversation

    if not candidates:
        return

    # Sort by created_time descending — process the most recent message first
    candidates.sort(key=lambda x: x[0].get("created_time", ""), reverse=True)
    latest_user_msg, conv_id = candidates[0]
    messages = conv_messages_map[conv_id]

    mid = latest_user_msg["id"]
    sender_id = latest_user_msg.get("from", {}).get("id", "")
    replied_messages.add(mid)

    user_text = latest_user_msg.get("message", "")
    attachments = latest_user_msg.get("attachments", {}).get("data", [])
    attach_types = {a.get("type", "") for a in attachments}

    # Voice → ask for text
    if "audio" in attach_types:
        send_message(sender_id, "ভয়েস মেসেজ পড়তে পারি না। টেক্সটে লিখে পাঠান। 🙏")
        return

    # Image only → ignore
    if "image" in attach_types and not user_text:
        return

    operator = detect_operator(user_text)

    if operator:
        send_message(sender_id, get_operator_package_list(operator))
    else:
        history = []
        for m in messages:
            if m["id"] == mid:
                break
            role = "assistant" if m.get("from", {}).get("id") == PAGE_ID else "user"
            if m.get("message"):
                history.append({"role": role, "content": m["message"]})
        ai_reply = generate_inbox_reply(user_text, history)
        send_message(sender_id, ai_reply)


# ─── Daily scheduled post ─────────────────────────────────────────────────────

def post_to_page(message: str):
    resp = requests.post(
        f"{GRAPH}/{PAGE_ID}/feed",
        data={"message": message, "access_token": PAGE_ACCESS_TOKEN},
        timeout=10,
    )
    if resp.ok:
        logger.info("Auto-post published. ID: %s", resp.json().get("id"))
    else:
        logger.error("Auto-post failed: %s", resp.text)


def check_scheduled_post():
    global _last_post_date, _posted_today
    now = datetime.now(timezone.utc) + BD_TZ  # Bangladesh time
    today = now.date()

    # Reset tracker each new day
    if _last_post_date != today:
        _posted_today = set()
        _last_post_date = today

    current_time = now.strftime("%H:%M")

    from ai import fetch_packages
    for post_time, operator in AUTO_POSTS:
        if post_time in _posted_today:
            continue
        if current_time < post_time:
            continue

        pkgs = fetch_packages()
        if operator not in pkgs:
            logger.warning("Scheduled post: operator %s not in sheet", operator)
            _posted_today.add(post_time)
            continue

        date_str = now.strftime("%d %B %Y")
        message = (
            f"আজকের {operator} অফার ({date_str})\n\n"
            f"{pkgs[operator]}\n\n"
            f"অর্ডার করতে ইনবক্সে মেসেজ করুন 📩"
        )
        post_to_page(message)
        _posted_today.add(post_time)
        logger.info("Auto-posted %s offer.", operator)


# ─── Main loop ─────────────────────────────────────────────────────────────────

def main():
    # ── Seed existing IDs so we don't reply to old comments/messages ──
    logger.info("Loading existing comments and messages (will not reply to these)...")
    try:
        check_comments(reply=False)
        check_inbox(reply=False)
    except Exception as e:
        logger.error("Error during seeding: %s", e)
    logger.info(
        "Seeded %d comment(s) and %d message(s). Now watching for NEW ones...",
        len(replied_comments),
        len(replied_messages),
    )

    logger.info("Polling every %ds. Press Ctrl+C to stop.", POLL_INTERVAL)
    for t, op in AUTO_POSTS:
        logger.info("Auto-post scheduled: %s at %s daily.", op, t)
    while True:
        time.sleep(POLL_INTERVAL)
        try:
            check_scheduled_post()
            check_comments()
            check_inbox()
        except Exception as e:
            logger.error("Unexpected error: %s", e)


if __name__ == "__main__":
    main()
