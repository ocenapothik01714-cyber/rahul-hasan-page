# Facebook App Permissions

## App Details

| Field | Value |
|---|---|
| App Name | Endless Wanderer |
| App ID | 1360611419500961 |
| Page | Endless Wanderer - নিরন্তর পথিক |
| Page ID | 464246183437112 |
| App Mode | **Live** |

---

## Granted Permissions (OAuth Scopes)

| Permission | Purpose |
|---|---|
| `public_profile` | Basic app access |
| `pages_show_list` | List pages managed by the user |
| `pages_read_engagement` | Read post comments and user interactions on the page |
| `pages_read_user_content` | Read content posted by users on the page |
| `pages_manage_metadata` | Subscribe to webhooks, manage page settings |
| `pages_manage_engagement` | Reply to comments, like/unlike comments |
| `pages_manage_posts` | Create and manage posts on the page |
| `pages_messaging` | Send and receive Messenger messages, send private replies |
| `business_management` | Access business-level management features |

---

## Webhook Configuration

| Field | Value |
|---|---|
| Callback URL | `https://nonfermentative-london-commutative.ngrok-free.dev/webhook` |
| Verify Token | `my_secret_verify_token_2024` |
| Subscribed Fields | `feed`, `messages`, `messaging_postbacks` |

> **Note:** The ngrok URL changes on every restart. Update the Callback URL in the Messenger API Setup page after each restart.

---

## What's Working

| Feature | Status |
|---|---|
| Auto reply to post comments | ✅ Working |
| Auto reply to Messenger inbox | ✅ Working |
| AI-generated replies (Groq / Llama 3.3 70b) | ✅ Working |
| Private reply (comment → inbox DM) | ⏳ Requires `pages_messaging` App Review approval |

---

## Tokens

| Token | Details |
|---|---|
| Page Access Token | Never expires — stored in `.env` |
| User Access Token | Never expires — stored in `.env` |

---

## AI (Groq)

| Field | Value |
|---|---|
| Provider | Groq |
| Model | `llama-3.3-70b-versatile` |
| Used for | Comment replies + Inbox replies |
| Language | Auto-detects Bengali / English |
