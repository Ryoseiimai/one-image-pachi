動画化手順: `python3 -m http.server 8000` で起動し、Playwright の viewport を 720×1080 にする。
`http://localhost:8000/real.html?record=1` を開き、開始から10秒間を WebM で録画する。
`ffmpeg -i recording.webm -c:v libx264 -pix_fmt yuv420p -movflags +faststart real.mp4` で MP4 に変換する。
