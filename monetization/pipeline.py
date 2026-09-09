#!/usr/bin/env python3
"""
note.com 収益化パイプライン: 一括実行スクリプト

  1. followers.md（フォロワー職業分類）から売れそうなテーマを提案
  2. 上位テーマについて記事ドラフトを生成
  3. 現在のフォロワー数を記録（施策の効果測定用）

投稿・価格設定・公開は行わない（人が note.com の編集画面で最終確認して行う）。

使い方:
  python3 pipeline.py --username bright_lotus8230 --followers-md ../followers.md
"""

import argparse
import subprocess
import sys
from pathlib import Path

from topic_strategy import load_classification, rank_topics
from generate_draft import build_draft
from note_client import fetch_profile_stats, append_history


def main():
    parser = argparse.ArgumentParser(description="収益化パイプラインを一括実行する")
    parser.add_argument("--username", default="bright_lotus8230")
    parser.add_argument("--cookie", default="", help="note.com のログイン済みセッションCookie")
    parser.add_argument("--followers-md", default="../followers.md")
    parser.add_argument("--drafts-per-run", type=int, default=1)
    parser.add_argument("--output-dir", default="../drafts")
    parser.add_argument("--history", default="../growth_history.json")
    args = parser.parse_args()

    followers_path = Path(args.followers_md)
    if not followers_path.exists():
        print(f"⚠ {followers_path} が見つかりません。先に以下を実行してください:")
        print(f'   python3 ../fetch_note_followers.py --username {args.username} --cookie "$NOTE_COOKIE"')
        sys.exit(1)

    classification = load_classification(followers_path)
    if not classification:
        print("⚠ フォロワー分類データが空です。")
        sys.exit(1)

    ranked = rank_topics(classification, top_n=args.drafts_per_run)

    print("=== ステップ1: テーマ選定 ===")
    generated = []
    for item in ranked:
        category = item["category"]
        theme = item["themes"][0]
        lo, hi = item["price_range_jpy"]
        price = (lo + hi) // 2
        print(f"- カテゴリ: {category} / テーマ: {theme} / 想定価格: ¥{price}")

        draft = build_draft(theme, category, price)
        out_dir = Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        from datetime import datetime

        slug = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = out_dir / f"draft_{slug}_{category}.md"
        out_path.write_text(draft, encoding="utf-8")
        generated.append(out_path)

    print("\n=== ステップ2: ドラフト生成完了 ===")
    for path in generated:
        print(f"  - {path}")

    print("\n=== ステップ3: フォロワー数の記録 ===")
    stats = fetch_profile_stats(args.username, args.cookie)
    if stats:
        append_history(stats, Path(args.history))
        print(f"  フォロワー数: {stats.get('follower_count')} 人 -> {args.history} に記録")

    print("\n次にやること:")
    print("  1. 生成されたドラフトの内容を読んで仕上げる")
    print("  2. note.com にログインし、editor にコピーして貼り付ける")
    print("  3. <!-- ここから有料エリア --> の位置で有料設定をし、価格を確認して公開する")


if __name__ == "__main__":
    main()
