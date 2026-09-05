import argparse
import json
from pathlib import Path
import re
import tempfile
import time

from playwright.sync_api import sync_playwright


parser = argparse.ArgumentParser(description="real.htmlをスキン別に録画する")
parser.add_argument("--skin", choices=("kaeru", "neko", "inu"), default="kaeru")
args = parser.parse_args()

errors = []
events = None
base = Path(__file__).resolve().parent
shots = base / "shots"
shots.mkdir(exist_ok=True)

take_pattern = re.compile(rf"real_{re.escape(args.skin)}_take(\d+)\.webm$")
used_takes = [
    int(match.group(1))
    for path in base.glob(f"real_{args.skin}_take*.webm")
    if (match := take_pattern.fullmatch(path.name))
]
take_number = max(used_takes, default=0) + 1
take_label = f"take{take_number:02d}"
video_path = base / f"real_{args.skin}_{take_label}.webm"
events_path = base / f"events_{args.skin}.json"


def handle_console(msg):
    global events
    if msg.type == "error":
        errors.append(f"[{msg.type}] {msg.text}")
    if msg.text.startswith("EVENTS "):
        try:
            events = json.loads(msg.text[len("EVENTS "):])
        except json.JSONDecodeError as exc:
            errors.append(f"[events] {exc}")

with tempfile.TemporaryDirectory(prefix=f"video_{args.skin}_", dir=base) as video_tmp:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            viewport={"width": 720, "height": 1080},
            device_scale_factor=1,
            record_video_dir=video_tmp,
            record_video_size={"width": 720, "height": 1080},
        )
        page = ctx.new_page()
        page.on("console", handle_console)
        page.on("pageerror", lambda exc: errors.append(f"[pageerror] {exc}"))
        page.goto(
            f"http://localhost:8767/real.html?record=1&skin={args.skin}",
            wait_until="load",
        )
        page.wait_for_function("document.querySelector('#machine').dataset.ready === '1'")
        t0 = time.time()
        screenshots = {
            2: shots / f"real_{args.skin}_02s_{take_label}.png",
            5: shots / f"real_{args.skin}_05s_{take_label}.png",
        }
        captured = set()
        deadline = t0 + 30
        while events is None and time.time() < deadline:
            elapsed = time.time() - t0
            for second, screenshot_path in screenshots.items():
                if elapsed >= second and second not in captured:
                    page.screenshot(path=screenshot_path)
                    captured.add(second)
            time.sleep(0.5)
            # Chromiumがconsoleイベントを配送し続けるよう、同期APIへ定期的に制御を戻す。
            page.evaluate("1")

        if events is None:
            errors.append("[events] EVENTS console line was not received")
        else:
            with events_path.open("w", encoding="utf-8") as file:
                json.dump(events, file, ensure_ascii=False, indent=2)
            print(f"EVENTS: {events_path} ({len(events)} events)")

        video = page.video
        page.close()
        ctx.close()
        video.save_as(video_path)

        debug_page = browser.new_page(viewport={"width": 720, "height": 1080})
        debug_page.on(
            "console",
            lambda msg: errors.append(f"[{msg.type}] {msg.text}") if msg.type == "error" else None,
        )
        debug_page.on("pageerror", lambda exc: errors.append(f"[pageerror] {exc}"))
        debug_page.goto(
            f"http://localhost:8767/real.html?debug=1&skin={args.skin}",
            wait_until="load",
        )
        debug_page.wait_for_function("document.querySelector('#machine').dataset.ready === '1'")
        debug_page.screenshot(path=shots / f"real_{args.skin}_debug.png")
        browser.close()

print("VIDEO:", video_path)

print("ERRORS:", json.dumps(errors, ensure_ascii=False))
if errors:
    raise SystemExit(1)
