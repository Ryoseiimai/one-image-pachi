from playwright.sync_api import sync_playwright
import json, time

errors = []
events = None
base = "/Users/ryoseiworld/dev/2026-09-06-one-image-pachi"

def handle_console(msg):
    global events
    if msg.type == "error":
        errors.append(f"[{msg.type}] {msg.text}")
    if msg.text.startswith("EVENTS "):
        try:
            events = json.loads(msg.text[len("EVENTS "):])
        except json.JSONDecodeError as exc:
            errors.append(f"[events] {exc}")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(
        viewport={"width":720,"height":1080},
        device_scale_factor=1,
        record_video_dir=f"{base}/video_tmp3",
        record_video_size={"width":720,"height":1080},
    )
    page = ctx.new_page()
    page.on("console", handle_console)
    page.on("pageerror", lambda exc: errors.append(f"[pageerror] {exc}"))
    page.goto("http://localhost:8767/real.html?record=1", wait_until="load")
    t0 = time.time()
    while time.time() - t0 < 2:
        time.sleep(0.05)
    page.screenshot(path=f"{base}/shots/real_02s_take03.png")
    while time.time() - t0 < 5:
        time.sleep(0.05)
    page.screenshot(path=f"{base}/shots/real_05s_take03.png")
    deadline = t0 + 30
    while events is None and time.time() < deadline:
        time.sleep(0.5)
        page.evaluate("() => window.__events ? window.__events.length : -1")
    if events is None:
        errors.append("[events] EVENTS console line was not received")
    else:
        with open(f"{base}/events.json", "w", encoding="utf-8") as f:
            json.dump(events, f, ensure_ascii=False, indent=2)
        print(f"EVENTS: {base}/events.json ({len(events)} events)")
    video = page.video
    page.close()
    ctx.close()
    video.save_as(f"{base}/real_recording.webm")
    browser.close()
    print("VIDEO:", f"{base}/real_recording.webm")

print("ERRORS:", json.dumps(errors, ensure_ascii=False))
