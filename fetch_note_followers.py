#!/usr/bin/env python3
"""
note.com フォロワー一覧取得・職業別分類スクリプト
対象ユーザー: bright_lotus8230 (佐藤永治)

使い方:
  1. pip install requests
  2. python3 fetch_note_followers.py
     ※ログインが必要な場合は --cookie オプションを使用してください
        python3 fetch_note_followers.py --cookie "your_session_cookie"
"""

import argparse
import json
import time
import sys
from datetime import datetime

try:
    import requests
except ImportError:
    print("requests ライブラリが必要です: pip install requests")
    sys.exit(1)

# ===================== 職業分類キーワード =====================
OCCUPATION_KEYWORDS = {
    "エンジニア・開発者": [
        "エンジニア", "engineer", "developer", "開発者", "プログラマ", "プログラマー",
        "SE", "システム", "ソフトウェア", "フロントエンド", "バックエンド", "フルスタック",
        "インフラ", "DevOps", "CTO", "tech", "テック", "コーダー", "coder",
    ],
    "デザイナー": [
        "デザイナー", "designer", "UI", "UX", "グラフィック", "クリエイター", "creator",
        "イラスト", "イラストレーター", "illustrator", "アート", "art", "デザイン",
        "ブランディング", "フォトグラファー", "photographer", "映像",
    ],
    "ライター・編集者": [
        "ライター", "writer", "編集", "editor", "記者", "journalist", "コピー",
        "ブロガー", "blogger", "コンテンツ", "content", "文筆", "作家", "小説",
        "翻訳", "translator",
    ],
    "ビジネス・経営": [
        "CEO", "COO", "CFO", "代表", "社長", "起業", "経営", "マネージャー",
        "manager", "コンサル", "consultant", "事業", "ビジネス", "business",
        "MBA", "戦略", "マーケティング", "marketing", "営業", "sales",
        "投資", "investor", "VC", "スタートアップ", "startup",
    ],
    "医療・福祉": [
        "医師", "医者", "doctor", "看護", "nurse", "薬剤師", "歯科", "理学療法",
        "作業療法", "心理", "カウンセラー", "counselor", "福祉", "介護",
        "保育", "保育士", "栄養士",
    ],
    "教育・研究": [
        "教師", "先生", "teacher", "教員", "講師", "professor", "教授", "研究",
        "researcher", "学者", "博士", "大学", "university", "学校", "塾",
        "コーチ", "coach", "トレーナー", "trainer",
    ],
    "クリエイター・アーティスト": [
        "音楽", "musician", "ミュージシャン", "歌手", "singer", "俳優", "actor",
        "声優", "モデル", "model", "YouTuber", "ユーチューバー", "インフルエンサー",
        "influencer", "TikTok", "配信", "streamer",
    ],
    "金融・会計": [
        "会計", "accountant", "税理士", "公認会計士", "CPA", "FP", "ファイナンシャル",
        "金融", "finance", "銀行", "bank", "保険", "証券", "アナリスト", "analyst",
    ],
    "法律・行政": [
        "弁護士", "lawyer", "attorney", "行政書士", "司法書士", "公務員",
        "行政", "政治", "politician", "議員", "法律", "legal",
    ],
    "フリーランス・副業": [
        "フリーランス", "freelance", "freelancer", "副業", "複業", "独立",
        "フリー", "個人事業",
    ],
    "学生": [
        "学生", "student", "大学生", "高校生", "大学院生",
    ],
}

DEFAULT_CATEGORY = "その他・未分類"

# ==============================================================


def classify_occupation(bio: str) -> str:
    if not bio:
        return DEFAULT_CATEGORY
    bio_lower = bio.lower()
    for category, keywords in OCCUPATION_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in bio_lower:
                return category
    return DEFAULT_CATEGORY


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


def fetch_followers(username: str, headers: dict, max_pages: int = 50) -> list:
    followers = []
    page = 1
    print(f"フォロワーを取得中: {username}")

    while page <= max_pages:
        url = f"https://note.com/api/v2/creators/{username}/followers"
        params = {"page": page, "per": 25}
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=10)
        except requests.RequestException as e:
            print(f"  エラー (page {page}): {e}")
            break

        if resp.status_code == 401:
            print("  ⚠ 認証エラー: ログインが必要です (--cookie オプションを使用してください)")
            break
        if resp.status_code != 200:
            print(f"  エラー: HTTP {resp.status_code}")
            break

        data = resp.json()
        items = data.get("data", {}).get("items", [])
        if not items:
            break

        followers.extend(items)
        total = data.get("data", {}).get("totalCount", "?")
        print(f"  page {page}: {len(items)} 件取得 (累計 {len(followers)} / {total})")

        last_page = data.get("data", {}).get("lastPage", page)
        if page >= last_page:
            break
        page += 1
        time.sleep(0.5)

    return followers


def fetch_profile(urlname: str, headers: dict) -> dict:
    url = f"https://note.com/api/v2/creators/{urlname}"
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            return resp.json().get("data", {})
    except requests.RequestException:
        pass
    return {}


def build_markdown(classified: dict, username: str) -> str:
    total = sum(len(v) for v in classified.values())
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = [
        f"# note フォロワー一覧（職業別分類）",
        f"",
        f"- 対象アカウント: [@{username}](https://note.com/{username})",
        f"- 取得日時: {now}",
        f"- 総フォロワー数: {total} 人",
        f"",
        f"---",
        f"",
        f"## 目次",
        f"",
    ]

    categories = sorted(classified.keys(), key=lambda c: -len(classified[c]))
    for cat in categories:
        count = len(classified[cat])
        anchor = cat.replace(" ", "-").replace("・", "").replace("　", "")
        lines.append(f"- [{cat}（{count}人）](#{anchor})")

    lines.append("")
    lines.append("---")
    lines.append("")

    for cat in categories:
        members = classified[cat]
        lines.append(f"## {cat}")
        lines.append(f"")
        lines.append(f"| # | ユーザー名 | 表示名 | プロフィール |")
        lines.append(f"|---|-----------|--------|------------|")
        for i, m in enumerate(members, 1):
            display = m.get("nickname") or m.get("name") or m.get("urlname", "")
            urlname = m.get("urlname", "")
            bio = (m.get("bio") or "").replace("\n", " ").replace("|", "｜")[:80]
            note_url = f"https://note.com/{urlname}" if urlname else ""
            name_cell = f"[{display}]({note_url})" if note_url else display
            lines.append(f"| {i} | @{urlname} | {name_cell} | {bio} |")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="note.com フォロワー一覧・職業別分類ツール")
    parser.add_argument("--username", default="bright_lotus8230", help="note.com ユーザー名")
    parser.add_argument("--cookie", default="", help="ログイン済みセッションCookie文字列")
    parser.add_argument("--output", default="followers.md", help="出力ファイル名")
    parser.add_argument("--enrich", action="store_true", help="各フォロワーの詳細プロフを取得（時間がかかります）")
    args = parser.parse_args()

    headers = build_headers(args.cookie)

    # フォロワー一覧取得
    followers = fetch_followers(args.username, headers)

    if not followers:
        print("フォロワーが取得できませんでした。")
        print("ヒント: ログインCookieが必要な場合は --cookie オプションを使用してください。")
        print("  ブラウザのDevToolsで note.com にログイン後、")
        print("  Application > Cookies から '_note_session' などの値をコピーしてください。")
        sys.exit(1)

    # 詳細プロフ取得（オプション）
    if args.enrich:
        print(f"\n詳細プロフ取得中 ({len(followers)} 件)...")
        for i, f in enumerate(followers):
            urlname = f.get("urlname", "")
            if urlname:
                profile = fetch_profile(urlname, headers)
                if profile:
                    followers[i].update(profile)
            if (i + 1) % 10 == 0:
                print(f"  {i + 1}/{len(followers)} 件完了")
            time.sleep(0.3)

    # 職業別分類
    classified: dict[str, list] = {}
    for f in followers:
        bio = f.get("bio") or f.get("profile") or ""
        cat = classify_occupation(bio)
        classified.setdefault(cat, []).append(f)

    # Markdown 生成
    md = build_markdown(classified, args.username)

    with open(args.output, "w", encoding="utf-8") as fp:
        fp.write(md)

    print(f"\n✅ 完了: {args.output} に出力しました")
    print(f"   総フォロワー数: {len(followers)} 人")
    for cat, members in sorted(classified.items(), key=lambda x: -len(x[1])):
        print(f"   {cat}: {len(members)} 人")


if __name__ == "__main__":
    main()
