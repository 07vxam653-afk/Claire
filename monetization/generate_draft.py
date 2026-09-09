#!/usr/bin/env python3
"""
note.com 収益化パイプライン: 記事ドラフト生成

topic_strategy.py が提案したテーマから、note に投稿する記事ドラフトを
Markdown で生成する。

- ANTHROPIC_API_KEY が設定されている場合: Claude API で本文まで自動生成する
- 設定されていない場合: 見出し構成だけのテンプレート（人が書く用の骨組み）を出力する

生成物には「無料で読める部分」と「有料エリア」を分ける目印
（<!-- ここから有料エリア --> コメント）を入れる。note の編集画面で
実際に投稿する際は、このコメントの位置で「ここから先を有料にする」
スライダーを設定する（note はテキスト中のマーカーで自動的に有料化する
機能は無いため、最終的な有料エリアの設定は人が note エディタ上で行う）。

使い方:
  python3 generate_draft.py --title "副業で月5万円を安定させる90日プラン" --price 480
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-sonnet-5"

TEMPLATE_SECTIONS = [
    "はじめに（読者が抱える悩みへの共感）",
    "結論・この記事で得られること",
    "① 本題の要点1（無料で読める部分はここまで）",
    "② 本題の要点2（詳細・具体的な手順）※有料エリア",
    "③ 本題の要点3（実例・チェックリスト）※有料エリア",
    "まとめ・次の一歩",
]


def generate_via_claude(title: str, category: str, api_key: str) -> str:
    """Claude API で本文を生成する。失敗したら例外を投げる（呼び出し側でフォールバック）。"""
    prompt = (
        f"あなたはnote.comで有料記事を書くプロのライターです。\n"
        f"タイトル「{title}」というテーマで、読者層「{category}」向けの記事本文を"
        f"Markdown で書いてください。\n"
        f"構成:\n"
        f"1. 悩みへの共感から始まる導入（無料公開部分、300字程度）\n"
        f"2. 本文中に `<!-- ここから有料エリア -->` という行を1つ入れる\n"
        f"3. 有料エリアには具体的なノウハウ・手順・チェックリストを1500字程度で書く\n"
        f"4. 最後に軽いまとめとCTA（コメントやフォローを促す一文）\n"
        f"誇大広告や断定しすぎた表現、根拠のない収益保証は避けてください。"
    )
    body = json.dumps(
        {
            "model": ANTHROPIC_MODEL,
            "max_tokens": 2000,
            "messages": [{"role": "user", "content": prompt}],
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        ANTHROPIC_API_URL,
        data=body,
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return "".join(block.get("text", "") for block in data.get("content", []))


def generate_template(title: str, category: str) -> str:
    lines = [f"<!-- 対象読者カテゴリ: {category} -->", ""]
    for section in TEMPLATE_SECTIONS:
        lines.append(f"## {section}")
        lines.append("")
        lines.append("[ここに執筆する]")
        lines.append("")
        if "無料で読める部分はここまで" in section:
            lines.append("<!-- ここから有料エリア -->")
            lines.append("")
    return "\n".join(lines)


def build_draft(title: str, category: str, price: int) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if api_key:
        try:
            body = generate_via_claude(title, category, api_key)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as e:
            print(f"⚠ Claude API 呼び出しに失敗したためテンプレートで生成します: {e}", file=sys.stderr)
            body = generate_template(title, category)
    else:
        body = generate_template(title, category)

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    front_matter = (
        f"# {title}\n\n"
        f"<!--\n"
        f"生成日時: {now}\n"
        f"想定価格: ¥{price}\n"
        f"投稿手順:\n"
        f"  1. この内容を note.com の編集画面にコピーする\n"
        f"  2. <!-- ここから有料エリア --> の位置で「ここから先を有料にする」を設定する\n"
        f"  3. 価格を ¥{price} 前後に設定し、内容を見直してから公開する\n"
        f"  4. AI を利用して生成した文章を含む場合は note のガイドラインに従い、\n"
        f"     必要に応じてAI利用の明記を行う\n"
        f"-->\n\n"
    )
    return front_matter + body


def main():
    parser = argparse.ArgumentParser(description="note 記事ドラフトを生成する")
    parser.add_argument("--title", required=True, help="記事タイトル")
    parser.add_argument("--category", default="読者全般", help="想定読者カテゴリ（topic_strategy.py の出力を利用）")
    parser.add_argument("--price", type=int, default=300, help="想定価格（円）")
    parser.add_argument("--output-dir", default="../drafts", help="ドラフトの出力先ディレクトリ")
    args = parser.parse_args()

    draft = build_draft(args.title, args.category, args.price)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"draft_{slug}.md"
    out_path.write_text(draft, encoding="utf-8")

    print(f"✅ ドラフトを生成しました: {out_path}")
    print("   内容を確認・仕上げてから note.com に手動で投稿してください。")


if __name__ == "__main__":
    main()
