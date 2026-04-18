import logging
import random
from flask import Flask, request, jsonify

from config import VERIFY_TOKEN, COMMENT_REPLIES, INBOX_REPLIES, PAGE_ID
from fb_api import reply_to_comment, reply_to_message

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Track replied IDs to avoid double-replies on duplicate webhook deliveries
_replied_comments: set = set()
_replied_messages: set = set()


# ─── Webhook Verification ──────────────────────────────────────────────────────

@app.get("/webhook")
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        logger.info("Webhook verified successfully.")
        return challenge, 200
    logger.warning("Webhook verification failed.")
    return "Forbidden", 403


# ─── Webhook Events ────────────────────────────────────────────────────────────

@app.post("/webhook")
def handle_webhook():
    data = request.get_json(silent=True) or {}
    logger.debug("Received webhook: %s", data)

    object_type = data.get("object")

    if object_type == "page":
        for entry in data.get("entry", []):
            # ── Comment events ────────────────────────────────────────────────
            for change in entry.get("changes", []):
                if change.get("field") == "feed":
                    value = change.get("value", {})
                    item = value.get("item")
                    verb = value.get("verb")

                    if item == "comment" and verb == "add":
                        comment_id = value.get("comment_id")
                        from_id = value.get("from", {}).get("id")

                        # Don't reply to our own page's comments
                        if comment_id and from_id != PAGE_ID and comment_id not in _replied_comments:
                            _replied_comments.add(comment_id)
                            msg = random.choice(COMMENT_REPLIES)
                            reply_to_comment(comment_id, msg)

            # ── Messenger events ──────────────────────────────────────────────
            for messaging in entry.get("messaging", []):
                sender_id = messaging.get("sender", {}).get("id")
                message = messaging.get("message", {})
                msg_id = message.get("mid")

                # Skip echo (messages sent by the page itself)
                if message.get("is_echo"):
                    continue

                if sender_id and msg_id and msg_id not in _replied_messages:
                    _replied_messages.add(msg_id)
                    reply = random.choice(INBOX_REPLIES)
                    reply_to_message(sender_id, reply)

    return jsonify({"status": "ok"}), 200


# ─── Health check ──────────────────────────────────────────────────────────────

@app.get("/")
def health():
    return jsonify({"status": "running", "page_id": PAGE_ID}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
