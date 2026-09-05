#!/usr/bin/env python3
"""スレッド(会話ID)への他人の返信・引用・いいね・メンションを検索し、新着だけ1行ずつ出す。
既読は seen_replies.json / seen_likes.json / seen_mention_since.json に保存。"""
import json, sys, time, os, re
sys.path.insert(0, os.path.expanduser("~/dev/2026-08-25-x-taiken-post"))
import taiken_post as tp

CONV = "2096313113067065399"
BASE_DIR = os.path.expanduser("~/dev/2026-09-06-one-image-pachi")
SEEN = os.path.join(BASE_DIR, "seen_replies.json")
SEEN_LIKES = os.path.join(BASE_DIR, "seen_likes.json")
SEEN_MENTION_SINCE = os.path.join(BASE_DIR, "seen_mention_since.json")
NOTES = os.path.join(BASE_DIR, "NOTES.md")
MY_USER_ID = "1372999611242008582"
SLEEP_BETWEEN_CALLS = 0.5
MAX_TWEET_IDS = 40

s = tp.oauth_session()


def load_json(path, default):
    if os.path.exists(path):
        return json.load(open(path))
    return default


def save_json(path, data):
    json.dump(data, open(path, "w"))


def get_notes_tweet_ids():
    """NOTES.md の「返信N ... : <id>」行から自分の投稿ID一覧を拾い、元IDも含める。"""
    ids = [CONV]
    if os.path.exists(NOTES):
        text = open(NOTES).read()
        for m in re.finditer(r"返信\d+[^\n]*?[:：]\s*(\d{10,})", text):
            ids.append(m.group(1))
    return ids


def api_get(url, params=None):
    r = s.get(url, params=params, timeout=30)
    if r.status_code == 429:
        print(f"[api 429] {url}", file=sys.stderr)
        return None
    if r.status_code != 200:
        print(f"[api {r.status_code}] {url}", file=sys.stderr)
        return None
    return r.json()


# ---- 対象ID一覧: NOTES.md由来 + 自分の直近投稿30件を合算・重複除去・最大40件 ----
notes_ids = get_notes_tweet_ids()
recent_j = api_get(
    f"https://api.x.com/2/users/{MY_USER_ID}/tweets",
    params={"max_results": 30, "exclude": "retweets", "tweet.fields": "created_at"},
)
recent_ids = [t["id"] for t in (recent_j.get("data", []) if recent_j else [])]

all_ids = []
for i in notes_ids + recent_ids:
    if i not in all_ids:
        all_ids.append(i)
all_ids = all_ids[:MAX_TWEET_IDS]
# 引用・いいねはレート制限内に収めるため直近15件に絞る
quote_like_ids = all_ids[:15]

# ---- 1. 返信 ----
# conversation_id 個別検索の代わりに to:ryoseichan3160 の受信リプライを1回のsearch_recentで拾う
seen_replies = set(load_json(SEEN, []))
j = api_get(
    "https://api.x.com/2/tweets/search/recent",
    params={"query": "to:ryoseichan3160 -from:ryoseichan3160",
            "tweet.fields": "author_id,created_at", "expansions": "author_id",
            "user.fields": "username", "max_results": 50},
)
if j is not None:
    users = {u["id"]: u["username"] for u in j.get("includes", {}).get("users", [])}
    for t in j.get("data", []):
        if t["id"] in seen_replies:
            continue
        seen_replies.add(t["id"])
        print(f"REPLY @{users.get(t['author_id'], '?')} ({t['id']}): {t['text'].replace(chr(10), ' ')[:200]}", flush=True)
    save_json(SEEN, sorted(seen_replies))

# ---- 2. 引用 ----
for tid in quote_like_ids:
    time.sleep(SLEEP_BETWEEN_CALLS)
    j = api_get(
        f"https://api.x.com/2/tweets/{tid}/quote_tweets",
        params={"tweet.fields": "author_id,created_at", "expansions": "author_id",
                "user.fields": "username", "max_results": 50},
    )
    if j is None:
        continue
    users = {u["id"]: u["username"] for u in j.get("includes", {}).get("users", [])}
    for t in j.get("data", []):
        if t["id"] in seen_replies:
            continue
        seen_replies.add(t["id"])
        print(f"QUOTE @{users.get(t['author_id'], '?')} ({t['id']}): {t['text'].replace(chr(10), ' ')[:200]}", flush=True)
save_json(SEEN, sorted(seen_replies))

# ---- 3. いいね ----
seen_likes = set(load_json(SEEN_LIKES, []))
for tid in quote_like_ids:
    time.sleep(SLEEP_BETWEEN_CALLS)
    j = api_get(
        f"https://api.x.com/2/tweets/{tid}/liking_users",
        params={"user.fields": "username", "max_results": 100},
    )
    if j is None:
        continue
    for u in j.get("data", []):
        key = f"{u['id']}:{tid}"
        if key in seen_likes:
            continue
        seen_likes.add(key)
        print(f"LIKE @{u.get('username', '?')} ({u['id']}) on {tid}", flush=True)
save_json(SEEN_LIKES, sorted(seen_likes))

# ---- 4. メンション ----
mention_state = load_json(SEEN_MENTION_SINCE, {"since_id": CONV})
params = {"tweet.fields": "author_id,created_at", "expansions": "author_id",
          "user.fields": "username", "max_results": 50,
          "since_id": mention_state.get("since_id", CONV)}
time.sleep(SLEEP_BETWEEN_CALLS)
j = api_get(f"https://api.x.com/2/users/{MY_USER_ID}/mentions", params=params)
if j is not None:
    users = {u["id"]: u["username"] for u in j.get("includes", {}).get("users", [])}
    data = j.get("data", [])
    for t in data:
        print(f"MENTION @{users.get(t['author_id'], '?')} ({t['id']}): {t['text'].replace(chr(10), ' ')[:200]}", flush=True)
    meta = j.get("meta", {})
    newest_from_meta = meta.get("newest_id")
    if data:
        # since_id 用に最大のIDを保存(APIは新しい順で返る想定なのでmaxを取る)
        newest = newest_from_meta or max(data, key=lambda t: int(t["id"]))["id"]
        mention_state["since_id"] = newest
    save_json(SEEN_MENTION_SINCE, mention_state)
