#!/usr/bin/env python3
"""スレッド(会話ID)への他人の返信を検索し、新着だけ1行ずつ出す。既読IDは seen_replies.json に保存。"""
import json, sys, time, os
sys.path.insert(0, os.path.expanduser("~/dev/2026-08-25-x-taiken-post"))
import taiken_post as tp
CONV = "2096313113067065399"
SEEN = os.path.expanduser("~/dev/2026-09-06-one-image-pachi/seen_replies.json")
seen = set(json.load(open(SEEN))) if os.path.exists(SEEN) else set()
s = tp.oauth_session()
r = s.get("https://api.x.com/2/tweets/search/recent",
          params={"query": f"conversation_id:{CONV} -from:ryoseichan3160",
                  "tweet.fields": "author_id,created_at", "expansions": "author_id",
                  "user.fields": "username", "max_results": 50}, timeout=30)
if r.status_code != 200:
    print(f"[api {r.status_code}]", file=sys.stderr); sys.exit(0)
j = r.json(); users = {u["id"]: u["username"] for u in j.get("includes", {}).get("users", [])}
for t in j.get("data", []):
    if t["id"] in seen: continue
    seen.add(t["id"])
    print(f"REPLY @{users.get(t['author_id'],'?')} ({t['id']}): {t['text'].replace(chr(10),' ')[:200]}", flush=True)
json.dump(sorted(seen), open(SEEN, "w"))
