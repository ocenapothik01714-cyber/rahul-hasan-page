"""
Post today's offer for a specific operator to the Facebook page.

Usage:
    python post_offer.py banglalink
    python post_offer.py gp
    python post_offer.py robi
"""
import sys
import requests
from datetime import datetime
from dotenv import load_dotenv
from config import PAGE_ACCESS_TOKEN, PAGE_ID
from ai import fetch_packages, OPERATOR_ALIASES

load_dotenv()

GRAPH = "https://graph.facebook.com/v25.0"


def post_to_page(message: str) -> bool:
    resp = requests.post(
        f"{GRAPH}/{PAGE_ID}/feed",
        data={"message": message, "access_token": PAGE_ACCESS_TOKEN},
        timeout=10,
    )
    if resp.ok:
        print("Posted successfully! Post ID:", resp.json().get("id"))
        return True
    print("Failed to post:", resp.text)
    return False


def main():
    operator_input = sys.argv[1].lower() if len(sys.argv) > 1 else "banglalink"
    operator_key = OPERATOR_ALIASES.get(operator_input)
    if not operator_key:
        print(f"Unknown operator '{operator_input}'.")
        print("Available:", ", ".join(OPERATOR_ALIASES.keys()))
        sys.exit(1)

    pkgs = fetch_packages()
    if operator_key not in pkgs:
        print(f"No packages found for {operator_key} in the sheet.")
        sys.exit(1)

    today = datetime.now().strftime("%d %B %Y")
    message = f"আজকের {operator_key} অফার ({today})\n\n{pkgs[operator_key]}\n\nঅর্ডার করতে মেসেজ করুন 👉 m.me/{PAGE_ID}"

    print("--- Preview ---")
    print(message)
    print("---------------")
    confirm = input("Post this to the page? (y/n): ").strip().lower()
    if confirm == "y":
        post_to_page(message)
    else:
        print("Cancelled.")


if __name__ == "__main__":
    main()
