#!/usr/bin/env python3
"""
BytePlus ModelArk - Seedance 1.5 Pro image-to-video vertical reel generation.

Uses only the python3 standard library (urllib/base64). The API key is
loaded from ~/.byteplus/env (ARK_API_KEY=...) and is NEVER printed, logged,
or included in any error output.

Reference image: kaeru_pachi_source.png (1024x1536, frog pachinko board
design) is sent as a base64 data URL alongside the text prompt, following
the confirmed working call shape in ~/dev/2026-07-27-seedance-api/tomori_talk.py.

API reference:
  Create task : POST https://ark.ap-southeast.bytepluses.com/api/v3/contents/generations/tasks
  Poll task   : GET  https://ark.ap-southeast.bytepluses.com/api/v3/contents/generations/tasks/{id}
  Model       : seedance-1-5-pro-251215

Duration handling: try DURATION_CANDIDATES in order (8s first) and only
fall back to a shorter value when the failure looks duration-related; any
other kind of error aborts immediately instead of retrying.
"""
import argparse
import base64
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ENV_PATH = os.path.expanduser("~/.byteplus/env")
BASE_URL = "https://ark.ap-southeast.bytepluses.com/api/v3/contents/generations/tasks"
MODEL_ID = "seedance-1-5-pro-251215"
DURATION_CANDIDATES = (8, 5, 4)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

POLL_INTERVAL_SEC = 10
MAX_POLL_SECONDS = 600  # 10 minutes
MAX_LONG_EDGE_PX = 1536  # resize reference images with a longer edge than this

PROMPT_TEMPLATE = (
    "@Image1 is the entire pachinko machine board and must stay fixed as the "
    "background, same colors, same {animal} character, same frame. Subject and "
    "action: dozens of small silver pachinko balls are launched from the "
    "bottom-left, travel up the left outer rail to the top of the board, then "
    "fall down through the board bouncing off small brass pins, some balls "
    "drop into the center pocket below the {animal}. The {animal} keeps smiling "
    "and slightly bobs and blinks; the two paper lanterns on each side glow and "
    "flicker warmly; at the end the whole board flashes gold as a jackpot. "
    "Environment: a real pachinko hall, slight reflection on the glass. "
    "Visual: anime flat style consistent with the reference, vivid, no new "
    "characters, no text, no letters, no logos anywhere. Camera: fixed "
    "frontal shot, vertical 9:16, very slight slow push-in. Audio: <clatter "
    "of pachinko balls hitting pins> <bright jackpot chime at the end> "
    "(upbeat festival taiko loop, low volume). Do not show any hands, "
    "people, or other machines."
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Seedance 1.5 Pro image-to-video generator for pachinko board reels."
    )
    parser.add_argument(
        "image_path",
        nargs="+",
        help="Path(s) to reference image(s), in @Image1/@Image2/... order.",
    )
    parser.add_argument("output_path", help="Path to save the generated mp4.")
    parser.add_argument(
        "--animal",
        default="frog",
        help='Animal name to substitute into the default prompt template (default: "frog"). '
        "Ignored if --prompt is given.",
    )
    parser.add_argument(
        "--prompt",
        default=None,
        help="Full custom prompt text overriding the animal template.",
    )
    return parser.parse_args()


def load_api_key():
    if not os.path.exists(ENV_PATH):
        print(f"ERROR: env file not found: {ENV_PATH}", file=sys.stderr)
        sys.exit(1)
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("ARK_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
                if not key:
                    print("ERROR: ARK_API_KEY is empty in env file", file=sys.stderr)
                    sys.exit(1)
                return key
    print("ERROR: ARK_API_KEY not found in env file", file=sys.stderr)
    sys.exit(1)


def scrub(text, api_key):
    """Defense in depth: strip the key value from any text before printing."""
    if not text or not api_key:
        return text
    return text.replace(api_key, "***REDACTED***")


def api_request(method, url, api_key, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {api_key}")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"raw_body": raw}
        return e.code, parsed
    except urllib.error.URLError as e:
        return None, {"network_error": str(e)}


def resize_if_needed(image_path, tmp_dir):
    """If the image's longer edge exceeds MAX_LONG_EDGE_PX, resize a copy
    with sips (macOS built-in) and return the copy's path; otherwise return
    the original path unchanged."""
    probe = subprocess.run(
        ["sips", "-g", "pixelWidth", "-g", "pixelHeight", image_path],
        capture_output=True, text=True, check=True,
    )
    width = height = None
    for line in probe.stdout.splitlines():
        line = line.strip()
        if line.startswith("pixelWidth:"):
            width = int(line.split(":")[1].strip())
        elif line.startswith("pixelHeight:"):
            height = int(line.split(":")[1].strip())

    if width is None or height is None or max(width, height) <= MAX_LONG_EDGE_PX:
        return image_path

    basename = os.path.basename(image_path)
    resized_path = os.path.join(tmp_dir, f"resized_{basename}")
    with open(image_path, "rb") as src, open(resized_path, "wb") as dst:
        dst.write(src.read())
    subprocess.run(
        ["sips", "-Z", str(MAX_LONG_EDGE_PX), resized_path],
        capture_output=True, text=True, check=True,
    )
    print(f"Resized {image_path} ({width}x{height}) -> {resized_path} (long edge <= {MAX_LONG_EDGE_PX}px)")
    return resized_path


def mime_type_for(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in (".jpg", ".jpeg"):
        return "image/jpeg"
    return "image/png"


def load_image_b64(image_path):
    if not os.path.exists(image_path):
        print(f"ERROR: image not found: {image_path}", file=sys.stderr)
        sys.exit(1)
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def build_image_content_parts(image_paths, tmp_dir):
    """ModelArk requires a `role` field on each image content part when more
    than one image is supplied (single-image calls work without it, per
    tomori_talk.py). All reference images here are used as style/structure
    references rather than a first/last frame, so role=reference_image."""
    parts = []
    multiple = len(image_paths) > 1
    for image_path in image_paths:
        prepared_path = resize_if_needed(image_path, tmp_dir)
        image_b64 = load_image_b64(prepared_path)
        mime = mime_type_for(prepared_path)
        part = {
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{image_b64}"},
        }
        if multiple:
            part["role"] = "reference_image"
        parts.append(part)
    return parts


def create_task(api_key, image_content_parts, duration, prompt):
    body = {
        "model": MODEL_ID,
        "content": [{"type": "text", "text": prompt}] + image_content_parts,
        "resolution": "720p",
        "ratio": "9:16",
        "duration": duration,
        "generate_audio": True,
        "watermark": False,
    }
    return api_request("POST", BASE_URL, api_key, body)


def get_task(api_key, task_id):
    url = f"{BASE_URL}/{task_id}"
    return api_request("GET", url, api_key)


def download_file(url, dest_path):
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=300) as resp, open(dest_path, "wb") as f:
        while True:
            chunk = resp.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)


def print_error_body(status, resp, api_key):
    print(f"HTTP status: {status}", file=sys.stderr)
    dumped = json.dumps(resp, ensure_ascii=False, indent=2)
    print(scrub(dumped, api_key), file=sys.stderr)


def create_task_with_duration_fallback(api_key, image_content_parts, prompt):
    """Try each candidate duration in order. Only move to a shorter duration
    when the failure looks duration-related; any other error type aborts
    immediately so we don't mask a real (non-duration) problem."""
    status, resp = None, None
    for duration in DURATION_CANDIDATES:
        print(f"Creating video generation task (duration={duration}s)...")
        status, resp = create_task(api_key, image_content_parts, duration, prompt)
        if status == 200 and isinstance(resp, dict) and "id" in resp:
            print(f"Task created with duration={duration}s")
            return status, resp, duration

        err_text = json.dumps(resp, ensure_ascii=False) if isinstance(resp, dict) else str(resp)
        duration_related = "duration" in err_text.lower()
        print(f"duration={duration}s failed (status={status}); duration_related={duration_related}")
        if not duration_related:
            break

    return status, resp, None


def main():
    args = parse_args()
    prompt = args.prompt if args.prompt else PROMPT_TEMPLATE.format(animal=args.animal)

    api_key = load_api_key()

    with tempfile.TemporaryDirectory() as tmp_dir:
        image_content_parts = build_image_content_parts(args.image_path, tmp_dir)

        status, resp, used_duration = create_task_with_duration_fallback(
            api_key, image_content_parts, prompt
        )
    if used_duration is None:
        print("ERROR: task creation failed for all attempted durations.", file=sys.stderr)
        print_error_body(status, resp, api_key)
        sys.exit(2)

    task_id = resp["id"]
    print(f"Task created: {task_id}")

    elapsed = 0
    while elapsed <= MAX_POLL_SECONDS:
        time.sleep(POLL_INTERVAL_SEC)
        elapsed += POLL_INTERVAL_SEC

        status, resp = get_task(api_key, task_id)
        if status != 200:
            print("ERROR: polling request failed.", file=sys.stderr)
            print_error_body(status, resp, api_key)
            sys.exit(3)

        task_status = resp.get("status")
        print(f"[{elapsed}s] status={task_status}")

        if task_status == "succeeded":
            video_url = (resp.get("content") or {}).get("video_url")
            if not video_url:
                print("ERROR: task succeeded but no video_url present.", file=sys.stderr)
                print_error_body(status, resp, api_key)
                sys.exit(4)

            print("Downloading video...")
            download_file(video_url, args.output_path)
            print(f"Saved: {args.output_path}")

            usage = resp.get("usage") or {}
            print(
                "usage: completion_tokens={} total_tokens={}".format(
                    usage.get("completion_tokens"), usage.get("total_tokens")
                )
            )
            print(
                "meta: resolution={} ratio={} duration={} fps={} generate_audio={}".format(
                    resp.get("resolution"),
                    resp.get("ratio"),
                    resp.get("duration"),
                    resp.get("framespersecond"),
                    resp.get("generate_audio"),
                )
            )
            sys.exit(0)

        if task_status in ("failed", "cancelled", "expired"):
            print(f"ERROR: task ended with status={task_status}", file=sys.stderr)
            print_error_body(status, resp, api_key)
            sys.exit(5)

    print("ERROR: polling timed out after 10 minutes without a terminal status.", file=sys.stderr)
    sys.exit(6)


if __name__ == "__main__":
    main()
