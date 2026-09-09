#!/usr/bin/env python3
"""
note.com 収益化パイプライン: フォロワー分類から売れそうな記事テーマを提案する

fetch_note_followers.py が出力した followers.md（職業別分類）を読み込み、
どの職業カテゴリのフォロワーが多いかをランキングし、
各カテゴリに紐づく記事テーマ・想定価格を提案する。

使い方:
  1. 先に fetch_note_followers.py を実行して followers.md を作っておく
  2. python3 topic_strategy.py
  3. python3 topic_strategy.py --input ../followers.md --top 3
"""

import argparse
import json
import re
import sys
from pathlib import Path

# ===================== カテゴリ別の記事テーマ・価格の提案 =====================
# 職業カテゴリごとに「刺さりそうな有料記事テーマ」と note での想定価格帯を紐づける。
# 価格は note の有料記事レンジ（100円〜）を参考にした目安。
TOPIC_PLAYBOOK = {
    "フリーランス・副業": {
        "themes": [
            "副業で月5万円を安定させるための最初の90日プラン",
            "フリーランス1年目が知らずに損している確定申告の落とし穴",
            "本業を辞めずに副業を育てるタイムマネジメント術",
        ],
        "price_range": (300, 980),
        "format": "有料記事（単発）",
    },
    "ビジネス・経営": {
        "themes": [
            "小さな会社が資金をかけずにできる集客の型",
            "経営者が毎月チェックすべき5つの数字",
            "個人事業から法人化するタイミングの見極め方",
        ],
        "price_range": (500, 1500),
        "format": "有料記事 or メンバーシップ",
    },
    "エンジニア・開発者": {
        "themes": [
            "個人開発したツールをどうやって収益化するか",
            "副業エンジニアが最初に取るべき案件の選び方",
        ],
        "price_range": (300, 800),
        "format": "有料記事（単発）",
    },
    "デザイナー": {
        "themes": [
            "デザイナーが単価を上げるためのポートフォリオの作り方",
            "クライアントに「高い」と言われない見積もりの出し方",
        ],
        "price_range": (300, 800),
        "format": "有料記事（単発）",
    },
    "ライター・編集者": {
        "themes": [
            "文字単価を上げるための実績提示のコツ",
            "note を使って自分の書き手ブランドを作る方法",
        ],
        "price_range": (300, 800),
        "format": "有料記事（単発）",
    },
    "学生": {
        "themes": [
            "学生のうちに始めておくと差がつくお金の勉強",
            "就活で使えるガクチカの作り方",
        ],
        "price_range": (100, 500),
        "format": "有料記事（単発）",
    },
}

DEFAULT_THEME = {
    "themes": ["読者の悩みを深掘りするヒアリング記事（コメント募集）"],
    "price_range": (100, 500),
    "format": "有料記事（単発）",
}


def load_classification(path: Path) -> dict:
    """followers.md の「## カテゴリ名」見出しから、各カテゴリの人数を数える。"""
    if not path.exists():
        return {}

    text = path.read_text(encoding="utf-8")
    counts: dict[str, int] = {}
    current = None
    for line in text.splitlines():
        heading = re.match(r"^## (.+)$", line)
        if heading:
            current = heading.group(1).strip()
            counts[current] = 0
            continue
        if current and line.startswith("| ") and not line.startswith("| # "):
            counts[current] += 1
    return {k: v for k, v in counts.items() if v > 0}


def rank_topics(classification: dict, top_n: int = 3) -> list:
    ranked = sorted(classification.items(), key=lambda kv: -kv[1])
    result = []
    for category, count in ranked[:top_n]:
        playbook = TOPIC_PLAYBOOK.get(category, DEFAULT_THEME)
        result.append(
            {
                "category": category,
                "follower_count": count,
                "themes": playbook["themes"],
                "price_range_jpy": playbook["price_range"],
                "format": playbook["format"],
            }
        )
    return result


def main():
    parser = argparse.ArgumentParser(description="フォロワー分類から記事テーマを提案する")
    parser.add_argument("--input", default="followers.md", help="fetch_note_followers.py の出力ファイル")
    parser.add_argument("--top", type=int, default=3, help="上位いくつのカテゴリを提案するか")
    parser.add_argument("--json", action="store_true", help="JSON で出力する（他スクリプトからの連携用）")
    args = parser.parse_args()

    classification = load_classification(Path(args.input))
    if not classification:
        print(f"⚠ {args.input} が見つからない、またはデータが空です。")
        print("  先に python3 fetch_note_followers.py --cookie \"...\" を実行してください。")
        sys.exit(1)

    ranked = rank_topics(classification, args.top)

    if args.json:
        print(json.dumps(ranked, ensure_ascii=False, indent=2))
        return

    print("=== おすすめ記事テーマ（フォロワー構成に基づく） ===\n")
    for i, item in enumerate(ranked, 1):
        lo, hi = item["price_range_jpy"]
        print(f"{i}. カテゴリ: {item['category']}（フォロワー{item['follower_count']}人）")
        print(f"   形式: {item['format']} / 想定価格: ¥{lo}〜¥{hi}")
        for theme in item["themes"]:
            print(f"   - {theme}")
        print()


if __name__ == "__main__":
    main()
