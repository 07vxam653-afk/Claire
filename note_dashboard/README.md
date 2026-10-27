# note ダッシュボード定点観測

毎日 18:00 (JST) に GitHub Actions が note のダッシュボード（全期間）から全記事の PV・スキ・コメント数を取得し、
履歴を蓄積して「特筆すべき変化」をまとめたレポートを Issue として投稿します。

## セットアップ（初回のみ）

1. ブラウザで note.com にログイン → DevTools → Application → Cookies → `https://note.com`
2. `_note_session_v5` の値をコピー
3. GitHub リポジトリの Settings → Secrets and variables → Actions → New repository secret
   - Name: `NOTE_COOKIE`
   - Value: `_note_session_v5=コピーした値`
4. （任意）Variables に `NOTE_USERNAME` を設定（既定: `bright_lotus8230`）
5. Actions タブ → "note dashboard daily snapshot" → Run workflow で動作確認

Cookie が期限切れになると失敗し、「⚠ note 定点観測に失敗」Issue が立ちます。その場合は手順 1〜3 で更新してください。

## 出力

| パス | 内容 |
|---|---|
| `data/snapshots/YYYY-MM-DD.csv` | その日の全記事一覧（PV・スキ・コメント・公開日） |
| `data/history.csv` | 全日分の履歴（定点観測データ） |
| `reports/YYYY-MM-DD.md` / `reports/latest.md` | 全記事一覧表 + 特筆事項 |
| Issue（ラベル `note-report`） | 特筆事項の要約（通知が届きます） |

## 特筆事項の判定ルール

- 🆕 新規記事 / 🗑 消えた記事
- 🚀 PV急増: 前日比 +20 以上 かつ 直近7日平均の 3 倍以上
- 🏅 マイルストーン: PV 100/500/1,000/3,000/5,000/10,000… 、スキ 10/30/50/100… を突破
- 💬 コメント増加
- 📈 前日比PV増加 TOP5
- ❤️ スキ率 TOP3（PV 50 以上）
- 💤 7日間PVが増えていない記事

閾値は `note_dashboard/report.py` 冒頭の定数で変更できます。

## ローカル実行

```sh
NOTE_COOKIE="_note_session_v5=xxxx" python3 note_dashboard/fetch_stats.py
python3 note_dashboard/report.py
```
