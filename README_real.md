# real.html の音付きMP4を作る

別ターミナルで `python3 -m http.server 8767` を起動してから、次の順に実行する。

```bash
python3 record_real.py
python3 build_audio.py events.json real_audio.wav
ffmpeg -i real_recording.webm -i real_audio.wav \
  -c:v libx264 -pix_fmt yuv420p -c:a aac -shortest -movflags +faststart real_with_audio.mp4
```

`record_real.py` は `real.html?record=1` を12秒強録画し、consoleの `EVENTS ` 行を `events.json` に保存する。最後の `ERRORS: []` が空であることを確認する。
