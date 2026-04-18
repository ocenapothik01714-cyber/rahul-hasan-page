import requests
import logging
from config import PAGE_ACCESS_TOKEN

GRAPH_URL = "https://graph.facebook.com/v25.0"
logger = logging.getLogger(__name__)


def reply_to_comment(comment_id: str, message: str) -> bool:
    """Post a reply to a Facebook post comment."""
    url = f"{GRAPH_URL}/{comment_id}/comments"
    payload = {
        "message": message,
        "access_token": PAGE_ACCESS_TOKEN,
    }
    resp = requests.post(url, data=payload, timeout=10)
    if resp.ok:
        logger.info("Replied to comment %s", comment_id)
        return True
    logger.error("Failed to reply to comment %s: %s", comment_id, resp.text)
    return False


def send_private_reply(comment_id: str, message: str) -> bool:
    """Send a Messenger private reply to a post commenter (no prior PSID needed)."""
    url = f"{GRAPH_URL}/{comment_id}/private_replies"
    payload = {"message": message, "access_token": PAGE_ACCESS_TOKEN}
    resp = requests.post(url, data=payload, timeout=10)
    if resp.ok:
        logger.info("Sent private reply to comment %s", comment_id)
        return True
    logger.error("Failed private reply to comment %s: %s", comment_id, resp.text)
    return False


def reply_to_message(recipient_id: str, message: str) -> bool:
    """Send a Messenger reply to a user (requires prior PSID from user messaging page first)."""
    url = f"{GRAPH_URL}/me/messages"
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": message},
        "access_token": PAGE_ACCESS_TOKEN,
    }
    resp = requests.post(url, json=payload, timeout=10)
    if resp.ok:
        logger.info("Replied to messenger user %s", recipient_id)
        return True
    logger.error("Failed to reply to user %s: %s", recipient_id, resp.text)
    return False
