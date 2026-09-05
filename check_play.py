from playwright.sync_api import sync_playwright
import time

errors = []
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width":600,"height":1000})
    page.on("console", lambda msg: errors.append(f"[{msg.type}] {msg.text}") if msg.type == "error" else None)
    page.on("pageerror", lambda exc: errors.append(f"[pageerror] {exc}"))
    page.goto("http://localhost:8765/", wait_until="load")
    time.sleep(0.5)
    page.screenshot(path="/Users/ryoseiworld/dev/2026-09-06-one-image-pachi/shots/check_00_initial.png")

    # 発射操作: ArrowRight押しっぱなし
    page.keyboard.down("ArrowRight")
    for i in range(1,6):
        time.sleep(1)
        page.screenshot(path=f"/Users/ryoseiworld/dev/2026-09-06-one-image-pachi/shots/check_0{i}.png")
    page.keyboard.up("ArrowRight")

    browser.close()

print("ERRORS:", errors)
