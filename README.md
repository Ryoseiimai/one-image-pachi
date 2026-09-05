# かえるぱち

公開URL: https://ryoseiimai.github.io/one-image-pachi/
スキン: https://ryoseiimai.github.io/one-image-pachi/?skin=neko / https://ryoseiimai.github.io/one-image-pachi/?skin=inu
写真の台（実物風）: https://ryoseiimai.github.io/one-image-pachi/real.html

`python3 -m http.server` を実行し、ブラウザで `http://localhost:8000/` を開きます。
スキンはURL末尾の `?skin=kaeru`、`?skin=neko`、`?skin=inu` で切り替えられます（既定は `kaeru`）。
右下のハンドルを左右にドラッグ、または `←` `→` キーで発射の強さを調整します。
玉は1発ずつ消費され、ヘソ入賞で+3発、大当たりの図柄3つ揃いで+200発です。
- ヘソ入賞は最大4個まで保留され、液晶下の保留ランプから順番に消化されます。
- 1〜9の3リールは左・右・中の順に停止し、通常時の大当たり確率は1/60です。
- 左右同図柄のリーチでは赤枠・振動が発生し、30%でスキン別の「激アツ」カットインが入ります。
- 大当たりは10ラウンド進行し、各ラウンド+20発（合計+200発）と合成BGM・効果音を再生します。
- 録画確認用は `?skin=neko&fever=1` のように指定すると当選確率が1/3になり、Mキーまたは画面上部で消音できます。
- 左右一致から2秒のノーマルリーチを経て、55%（FEVER時は100%）で画面幅90%の「にゃんこSPリーチ」へ発展します。
- SPは「魚とり」「猫パンチ」と、当たり時限定の確定演出「全回転」の3種類です。
- 魚とり／猫パンチは結末直前にPUSHが出現し、Space・クリック・タップ、または3秒経過で決着します。
- SP失敗後は8%で「まだ終わらない…」から画面が割れ、図柄が揃い直す復活演出が発生します。
- 演出確認は `?skin=neko&fever=1&reach=fish`（`punch` / `zenkaiten`）で、読み込み直後のSP変動を固定・自動開始できます。
