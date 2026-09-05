from playwright.sync_api import sync_playwright
import time, json

errors = []
base = "/Users/ryoseiworld/dev/2026-09-06-one-image-pachi"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(
        viewport={"width":720,"height":1080},
        device_scale_factor=1,
        record_video_dir=f"{base}/video_tmp2",
        record_video_size={"width":720,"height":1080},
    )
    page = ctx.new_page()
    page.on("console", lambda msg: errors.append(f"[{msg.type}] {msg.text}") if msg.type == "error" else None)
    page.on("pageerror", lambda exc: errors.append(f"[pageerror] {exc}"))
    page.goto("http://localhost:8767/real.html?record=1", wait_until="load")
    t0 = time.time()
    while time.time() - t0 < 0.2:
        time.sleep(0.02)
    page.screenshot(path=f"{base}/shots/real_00s_take02.png")
    while time.time() - t0 < 2:
        time.sleep(0.05)
    page.screenshot(path=f"{base}/shots/real_02s_take02.png")
    while time.time() - t0 < 5:
        time.sleep(0.05)
    page.screenshot(path=f"{base}/shots/real_05s_take02.png")
    while time.time() - t0 < 11:
        time.sleep(0.05)
    page.close()
    ctx.close()
    browser.close()

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width":720,"height":1080}, device_scale_factor=1)
    page.on("console", lambda msg: errors.append(f"[{msg.type}] {msg.text}") if msg.type == "error" else None)
    page.on("pageerror", lambda exc: errors.append(f"[pageerror] {exc}"))
    page.goto("http://localhost:8767/real.html?debug=1", wait_until="load")
    time.sleep(2)
    page.screenshot(path=f"{base}/shots/real_debug02.png")
    browser.close()

print("ERRORS:", json.dumps(errors, ensure_ascii=False))
