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
from datetime import datetime, timezone
from config import PAGE_ACCESS_TOKEN, PAGE_ID
from ai import (generate_comment_reply, generate_inbox_reply,
                is_list_request, detect_operator,
                get_full_package_list, get_operator_package_list)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

GRAPH = "https://graph.facebook.com/v25.0"
POLL_INTERVAL = 15  # seconds between each check

# ── Daily auto-post config ─────────────────────────────────────────────────────
AUTO_POST_TIME = "17:39"       # HH:MM — time to post every day
AUTO_POST_OPERATOR = "Banglalink"  # operator key from sheet

_last_post_date = None  # tracks which date we already posted

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


def format_comment_time(iso_str):
    """Convert Facebook ISO timestamp to a readable local string."""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%d %b %Y at %I:%M %p UTC")
    except Exception:
        return iso_str


def build_inbox_dm(post, comment):
    """Build the DM text sent to a commenter via Messenger."""
    post_text = post.get("message") or post.get("story") or "(no text)"
    # Trim long posts
    if len(post_text) > 200:
        post_text = post_text[:200] + "..."

    comment_text = comment.get("message", "")
    comment_time = format_comment_time(comment.get("created_time", ""))
    commenter_name = comment.get("from", {}).get("name", "আপনি")
    post_id = post.get("id", "")

    return (
        f"হ্যালো {commenter_name}! 👋\n\n"
        f"আপনি আমাদের একটি পোস্টে মন্তব্য করেছেন। এখানে বিস্তারিত:\n\n"
        f"📌 পোস্ট ID: {post_id}\n"
        f"📝 পোস্টের বিষয়বস্তু:\n{post_text}\n\n"
        f"💬 আপনার মন্তব্য: \"{comment_text}\"\n"
        f"🕒 মন্তব্যের সময়: {comment_time}\n\n"
        f"আপনার মতামতের জন্য অসংখ্য ধন্যবাদ! আমাদের পেজে সাথে থাকুন। ❤️"
    )


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
                full_reply = ai_reply + "\n\n💬 বিস্তারিত জানতে আমাদের মেসেজ করুন 👉 m.me/" + PAGE_ID
                reply_to_comment(cid, full_reply)


# ─── Messenger send (shared by comment DM + inbox reply) ──────────────────────

def send_private_reply(comment_id, message):
    """Send a Messenger private reply to a commenter via the Private Reply API.
    Uses comment_id (not user ID) — works without a prior PSID."""
    resp = requests.post(
        f"{GRAPH}/{comment_id}/private_replies",
        data={"message": message, "access_token": PAGE_ACCESS_TOKEN},
        timeout=10,
    )
    if resp.ok:
        logger.info("Sent private reply to comment %s", comment_id)
    else:
        logger.error("Failed private reply to comment %s: %s", comment_id, resp.text)


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
    replied_this_cycle = False  # only one reply per poll cycle
    for conv in conversations:
        messages = get_messages_in_conversation(conv["id"])

        # Find the latest unread user message; mark ALL older unreplied ones as seen
        latest_user_msg = None
        for msg in reversed(messages):
            mid = msg.get("id")
            sender_id = msg.get("from", {}).get("id", "")
            if not mid or sender_id == PAGE_ID:
                continue
            if mid in replied_messages:
                continue
            attachments = msg.get("attachments", {}).get("data", [])
            text = msg.get("message", "")
            if not text and not attachments:
                continue
            if latest_user_msg is None:
                latest_user_msg = msg  # newest unreplied
            else:
                replied_messages.add(mid)  # skip older ones silently

        if not latest_user_msg:
            continue

        mid = latest_user_msg["id"]
        sender_id = latest_user_msg.get("from", {}).get("id", "")
        replied_messages.add(mid)

        if reply and not replied_this_cycle:
            user_text = latest_user_msg.get("message", "")
            attachments = latest_user_msg.get("attachments", {}).get("data", [])
            attach_types = {a.get("type", "") for a in attachments}

            # Voice message → ask for text
            if "audio" in attach_types:
                send_message(sender_id,
                    "আপনার ভয়েস মেসেজ পাওয়া গেছে, কিন্তু আমরা ভয়েস পড়তে পারি না। "
                    "দয়া করে আপনার প্রশ্নটি টেক্সটে (বাংলা বা ইংরেজিতে) লিখে পাঠান। 🙏")
                replied_this_cycle = True
                continue

            # Image → silently ignore
            if "image" in attach_types and not user_text:
                continue

            if is_list_request(user_text):
                operator = detect_operator(user_text)
                if operator:
                    send_message(sender_id, get_operator_package_list(operator))
                else:
                    send_message(sender_id, get_full_package_list())
            else:
                # Build conversation history for context
                history = []
                for m in messages:
                    if m["id"] == mid:
                        break
                    role = "assistant" if m.get("from", {}).get("id") == PAGE_ID else "user"
                    if m.get("message"):
                        history.append({"role": role, "content": m["message"]})
                ai_reply = generate_inbox_reply(user_text, history)
                send_message(sender_id, ai_reply)
            replied_this_cycle = True


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
    global _last_post_date
    now = datetime.now()
    today = now.date()
    if _last_post_date == today:
        return  # already posted today
    if now.strftime("%H:%M") < AUTO_POST_TIME:
        return  # not time yet

    from ai import fetch_packages
    pkgs = fetch_packages()
    if AUTO_POST_OPERATOR not in pkgs:
        logger.warning("Scheduled post: operator %s not in sheet", AUTO_POST_OPERATOR)
        return

    date_str = now.strftime("%d %B %Y")
    message = (
        f"আজকের {AUTO_POST_OPERATOR} অফার ({date_str})\n\n"
        f"{pkgs[AUTO_POST_OPERATOR]}\n\n"
        f"অর্ডার করতে মেসেজ করুন 👉 m.me/{PAGE_ID}"
    )
    post_to_page(message)
    _last_post_date = today


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
    logger.info("Auto-post scheduled: %s at %s daily.", AUTO_POST_OPERATOR, AUTO_POST_TIME)
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
