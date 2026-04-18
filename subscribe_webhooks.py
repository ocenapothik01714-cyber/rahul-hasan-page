"""
Run this ONCE to subscribe your page to the required webhook fields.
Usage:
    source venv/bin/activate
    python subscribe_webhooks.py
"""
import requests
from config import PAGE_ACCESS_TOKEN, PAGE_ID, APP_ID, APP_SECRET

GRAPH = "https://graph.facebook.com/v25.0"


def get_app_token():
    resp = requests.get(
        f"{GRAPH}/oauth/access_token",
        params={
            "client_id": APP_ID,
            "client_secret": APP_SECRET,
            "grant_type": "client_credentials",
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def subscribe_page():
    """Subscribe the page to feed + messages webhook fields."""
    resp = requests.post(
        f"{GRAPH}/{PAGE_ID}/subscribed_apps",
        data={
            "subscribed_fields": "feed,messages,messaging_postbacks",
            "access_token": PAGE_ACCESS_TOKEN,
        },
        timeout=10,
    )
    print("Page subscription:", resp.status_code, resp.text)


if __name__ == "__main__":
    subscribe_page()
