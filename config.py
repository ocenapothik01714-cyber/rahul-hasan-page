import os
from dotenv import load_dotenv

load_dotenv()

APP_ID = os.getenv("APP_ID")
APP_SECRET = os.getenv("APP_SECRET")
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN")
PAGE_ID = os.getenv("PAGE_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_API_KEY2 = os.getenv("GROQ_API_KEY2")
GROQ_API_KEY3 = os.getenv("GROQ_API_KEY3")
GROQ_API_KEY4 = os.getenv("GROQ_API_KEY4")
GROQ_API_KEY5 = os.getenv("GROQ_API_KEY5")

# ─── Auto Reply Messages ───────────────────────────────────────────────────────

# Replies for post COMMENTS — picked randomly
COMMENT_REPLIES = [
    "ধন্যবাদ আপনার মন্তব্যের জন্য! 😊 আরও সুন্দর কন্টেন্টের জন্য পেজটি ফলো করুন।",
    "আপনার ভালোবাসার জন্য অসংখ্য ধন্যবাদ! ❤️",
    "Thank you for your comment! Stay connected for more updates. 🌍",
    "আপনার মতামত আমাদের অনুপ্রাণিত করে! 🙏 পেজে লাইক দিয়ে সাথে থাকুন।",
    "ধন্যবাদ! আপনার সাপোর্টই আমাদের এগিয়ে চলার শক্তি। 💪",
]

# Replies for Messenger INBOX — picked randomly
INBOX_REPLIES = [
    "আস-সালামু আলাইকুম! 👋 আপনার মেসেজের জন্য ধন্যবাদ। আমরা শীঘ্রই আপনার সাথে যোগাযোগ করব।",
    "Hello! Thank you for reaching out to Endless Wanderer. We'll get back to you soon! 😊",
    "ধন্যবাদ মেসেজ করার জন্য! আমাদের পেজ ভিজিট করুন আরও তথ্যের জন্য। 🌏",
    "আপনার বার্তা পেয়েছি। আমরা যত দ্রুত সম্ভব উত্তর দেব। 🙏",
]
