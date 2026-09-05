from playwright.sync_api import sync_playwright
import time, os

BASE = "/Users/ryoseiworld/dev/2026-09-06-one-image-pachi"

targets = [
    ("fish", "http://localhost:8770/?skin=neko&fever=1&reach=fish"),
    ("punch", "http://localhost:8770/?skin=neko&fever=1&reach=punch"),
    ("zenkaiten", "http://localhost:8770/?skin=neko&fever=1&reach=zenkaiten"),
]

results = {}

with sync_playwright() as p:
    for name, url in targets:
        errors = []
        video_dir = f"{BASE}/video_tmp_codex_check/{name}"
        os.makedirs(video_dir, exist_ok=True)
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width":600,"height":1000},
            record_video_dir=video_dir,
            record_video_size={"width":720,"height":1200},
        )
        page = context.new_page()
        page.on("console", lambda msg: errors.append(f"[{msg.type}] {msg.text}") if msg.type == "error" else None)
        page.on("pageerror", lambda exc: errors.append(f"[pageerror] {exc}"))
        page.goto(url, wait_until="load")
        time.sleep(0.3)
        try:
            page.click("canvas")
        except Exception as e:
            errors.append(f"[clickerror] {e}")
        time.sleep(0.3)
        page.keyboard.down("ArrowRight")
        for i in range(45):
            time.sleep(1)
            if i % 2 == 0:
                page.keyboard.press("Space")
        page.keyboard.up("ArrowRight")
        video_path = page.video.path() if page.video else None
        context.close()
        browser.close()
        results[name] = {"video": video_path, "errors": errors}
        print(name, "video:", video_path, "errors:", errors)

print("DONE", results)
