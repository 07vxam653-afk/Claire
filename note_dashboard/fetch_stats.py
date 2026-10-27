#!/usr/bin/env python3
"""
note ダッシュボード（アクセス状況）の全記事データを取得し、日次スナップショットとして保存する。

使い方:
  NOTE_COOKIE="_note_session_v5=xxxx" python3 note_dashboard/fetch_stats.py

出力:
  data/snapshots/YYYY-MM-DD.csv  その日の全記事データ
  data/history.csv               全スナップショットの縦持ち履歴（定点観測用）
"""

import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
STATS_URL = "https://note.com/api/v1/stats/pv"
CONTENTS_URL = "https://note.com/api/v2/creators/{username}/contents"

FIELDS = [
    "date", "key", "title", "url", "published_at",
    "pv", "like", "comment",
]


class AuthError(Exception):
    pass


def http_get_json(url: str, params: dict, cookie: str = "") -> dict:
    query = urllib.parse.urlencode(params)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
        "Referer": "https://note.com/sitesettings/stats",
    }
    if cookie:
        headers["Cookie"] = cookie
    req = urllib.request.Request(f"{url}?{query}", headers=headers)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise AuthError(f"HTTP {e.code}: ログインCookieが無効または期限切れです") from e
            if e.code < 500 or attempt == 3:
                raise
        except urllib.error.URLError:
            if attempt == 3:
                raise
        time.sleep(2 ** (attempt + 1))
    raise RuntimeError("unreachable")


def fetch_dashboard(cookie: str) -> tuple[list, dict]:
    """ダッシュボードの「全期間」統計を全ページ取得する。"""
    items, summary, page = [], {}, 1
    while True:
        data = http_get_json(
            STATS_URL, {"filter": "all", "page": page, "sort": "pv"}, cookie
        ).get("data") or {}
        stats = data.get("note_stats") or []
        if page == 1:
            summary = {
                "total_pv": data.get("total_pv"),
                "total_like": data.get("total_like"),
                "total_comment": data.get("total_comment"),
                "last_calculate_at": data.get("last_calculate_at"),
            }
            # Cookie が無効だとエラーにならず空データが返ることがある
            if not stats and not data.get("total_pv"):
                raise AuthError("統計データが空です。ログインCookieを確認してください")
        items.extend(stats)
        print(f"  page {page}: {len(stats)} 件 (累計 {len(items)})")
        if not stats or data.get("last_page", True) is True or page >= 500:
            break
        page += 1
        time.sleep(0.5)
    return items, summary


def fetch_publish_dates(username: str, cookie: str) -> dict:
    """公開記事一覧から key -> 公開日時 を取得する（失敗しても続行）。"""
    dates, page = {}, 1
    try:
        while page <= 200:
            data = http_get_json(
                CONTENTS_URL.format(username=username), {"kind": "note", "page": page}, cookie
            ).get("data") or {}
            for c in data.get("contents") or []:
                if c.get("key"):
                    dates[c["key"]] = c.get("publishAt") or ""
            if data.get("isLastPage", True):
                break
            page += 1
            time.sleep(0.5)
    except Exception as e:  # 公開日は補助情報なので取得失敗は警告に留める
        print(f"  ⚠ 公開日の取得に失敗: {e}")
    return dates


def to_rows(items: list, publish_dates: dict, username: str, date: str) -> list:
    rows = []
    for it in items:
        key = it.get("key") or str(it.get("id", ""))
        user = (it.get("user") or {}).get("urlname") or username
        rows.append({
            "date": date,
            "key": key,
            "title": (it.get("name") or "").replace("\n", " ").strip(),
            "url": f"https://note.com/{user}/n/{key}" if key else "",
            "published_at": (publish_dates.get(key) or "")[:10],
            "pv": int(it.get("read_count") or 0),
            "like": int(it.get("like_count") or 0),
            "comment": int(it.get("comment_count") or 0),
        })
    return rows


def write_csv(path: str, rows: list, append: bool = False) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    exists = os.path.exists(path)
    with open(path, "a" if append else "w", encoding="utf-8", newline="") as fp:
        w = csv.DictWriter(fp, fieldnames=FIELDS)
        if not (append and exists):
            w.writeheader()
        w.writerows(rows)


def main():
    p = argparse.ArgumentParser(description="note ダッシュボード全記事データ取得")
    p.add_argument("--username", default=os.environ.get("NOTE_USERNAME", "bright_lotus8230"))
    p.add_argument("--data-dir", default="data")
    p.add_argument("--date", default=datetime.now(JST).strftime("%Y-%m-%d"))
    args = p.parse_args()

    cookie = os.environ.get("NOTE_COOKIE", "")
    if not cookie:
        print("NOTE_COOKIE が未設定です（例: _note_session_v5=xxxx）")
        sys.exit(2)

    print("ダッシュボード統計を取得中...")
    try:
        items, summary = fetch_dashboard(cookie)
    except AuthError as e:
        print(f"❌ {e}")
        sys.exit(3)
    print("公開日を取得中...")
    publish_dates = fetch_publish_dates(args.username, cookie)

    rows = to_rows(items, publish_dates, args.username, args.date)
    snap = os.path.join(args.data_dir, "snapshots", f"{args.date}.csv")
    write_csv(snap, rows)

    # 同じ日付で再実行した場合は履歴から既存行を除いてから追記する
    hist = os.path.join(args.data_dir, "history.csv")
    if os.path.exists(hist):
        with open(hist, encoding="utf-8", newline="") as fp:
            kept = [r for r in csv.DictReader(fp) if r["date"] != args.date]
        write_csv(hist, kept)
    write_csv(hist, rows, append=True)

    with open(os.path.join(args.data_dir, "summary.json"), "w", encoding="utf-8") as fp:
        json.dump({"date": args.date, **summary}, fp, ensure_ascii=False, indent=2)

    print(f"✅ {len(rows)} 記事を保存: {snap}")


if __name__ == "__main__":
    main()
