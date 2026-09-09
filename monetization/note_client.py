#!/usr/bin/env python3
"""
note.com 収益化パイプライン: 公開プロフィール情報の取得（成長トラッキング用）

note.com には記事投稿・価格設定を行うための公開ドキュメント付きAPIが無いため、
このスクリプトは「投稿の自動化」は行わない（未公開の内部APIを勝手に叩いて
自動投稿する実装は、note の利用規約違反やアカウント停止のリスクがあるため、
このプロジェクトでは意図的に実装しない）。

代わりに、fetch_note_followers.py と同じ方式で取得できる公開プロフィール情報
（フォロワー数など）を使い、施策の効果（フォロワー数の増減）を時系列で
記録するためのユーティリティを提供する。

記事の投稿・価格設定・有料エリアの確定は、必ず note.com の編集画面から
人が行うこと。
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

try:
    import requests
except ImportError:
    print("requests ライブラリが必要です: pip install requests")
    sys.exit(1)


def build_headers(cookie: str = "") -> dict:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
        "Referer": "https://note.com/",
    }
    if cookie:
        headers["Cookie"] = cookie
    return headers


def fetch_profile_stats(username: str, cookie: str = "") -> dict:
    url = f"https://note.com/api/v2/creators/{username}"
    headers = build_headers(cookie)
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"⚠ プロフィール取得に失敗しました: {e}", file=sys.stderr)
        return {}

    data = resp.json().get("data", {})
    return {
        "urlname": data.get("urlname"),
        "nickname": data.get("nickname"),
        "follower_count": data.get("followerCount"),
        "note_count": data.get("noteCount"),
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
    }


def append_history(stats: dict, history_path: Path) -> None:
    history = []
    if history_path.exists():
        history = json.loads(history_path.read_text(encoding="utf-8"))
    history.append(stats)
    history_path.write_text(
        json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main():
    parser = argparse.ArgumentParser(description="note 公開プロフィールの成長トラッキング")
    parser.add_argument("--username", default="bright_lotus8230")
    parser.add_argument("--cookie", default="", help="必須ではないが、非公開情報を含めたい場合に指定")
    parser.add_argument("--history", default="../growth_history.json")
    args = parser.parse_args()

    stats = fetch_profile_stats(args.username, args.cookie)
    if not stats:
        sys.exit(1)

    print(json.dumps(stats, ensure_ascii=False, indent=2))
    append_history(stats, Path(args.history))
    print(f"✅ {args.history} に記録しました")


if __name__ == "__main__":
    main()
