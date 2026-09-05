`python3 -m http.server 8767` を起動する。
別ターミナルで `python3 record_real.py --skin neko` を実行する（`neko` は `kaeru` / `inu` に変更可）。
`python3 build_audio.py events_neko.json real_neko_audio.wav && ffmpeg -i real_neko_take01.webm -i real_neko_audio.wav -c:v libx264 -pix_fmt yuv420p -c:a aac -shortest -movflags +faststart real_neko_take01.mp4`（スキン名とtake番号を合わせる）。
