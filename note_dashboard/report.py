#!/usr/bin/env python3
"""
data/history.csv を元に、全記事一覧表と「特筆すべき変化」をまとめたレポートを生成する。

使い方:
  python3 note_dashboard/report.py            # 最新日付のレポート
  python3 note_dashboard/report.py --date 2026-10-27

出力:
  reports/YYYY-MM-DD.md と reports/latest.md
"""

import argparse
import csv
import json
import os
from collections import defaultdict

PV_MILESTONES = [100, 500, 1000, 3000, 5000, 10000, 30000, 50000, 100000]
LIKE_MILESTONES = [10, 30, 50, 100, 300, 500, 1000]
SURGE_MIN_DELTA = 20      # 急増判定の最低PV増分
SURGE_RATIO = 3.0         # 過去7日平均の何倍で「急増」とみなすか
LIKE_RATE_MIN_PV = 50     # スキ率ランキング対象の最低PV
STALL_DAYS = 7            # この日数PVが増えていなければ「停滞」


def load_history(path: str) -> dict:
    """date -> key -> row"""
    hist = defaultdict(dict)
    with open(path, encoding="utf-8", newline="") as fp:
        for r in csv.DictReader(fp):
            for k in ("pv", "like", "comment"):
                r[k] = int(r[k] or 0)
            hist[r["date"]][r["key"]] = r
    return hist


def esc(s: str) -> str:
    return (s or "").replace("|", "｜")


def link(r: dict, width: int = 40) -> str:
    title = esc(r["title"]) or r["key"]
    if len(title) > width:
        title = title[:width] + "…"
    return f"[{title}]({r['url']})" if r.get("url") else title


def signed(n: int) -> str:
    return f"+{n:,}" if n > 0 else f"{n:,}"


def crossed(prev: int, cur: int, marks: list) -> list:
    return [m for m in marks if prev < m <= cur]


def highlights(hist: dict, dates: list, today: str) -> list:
    cur = hist[today]
    idx = dates.index(today)
    if idx == 0:
        return ["- 初回取得のため比較対象がありません。明日以降、前日比での変化を報告します。"]
    prev = hist[dates[idx - 1]]
    window = dates[max(0, idx - 7):idx]  # 前日までの最大7スナップショット
    out = []

    def delta(key, field, a, b):
        return hist[b].get(key, {}).get(field, 0) - hist[a].get(key, {}).get(field, 0)

    # 新規記事
    new = [r for k, r in cur.items() if k not in prev]
    if new:
        out.append(f"### 🆕 新しく計測対象になった記事（{len(new)}件）")
        out += [f"- {link(r)} — PV {r['pv']:,} / スキ {r['like']:,}" for r in new]
        out.append("")

    # 消えた記事（削除・非公開化）
    gone = [r for k, r in prev.items() if k not in cur]
    if gone:
        out.append(f"### 🗑 前回あって今回なくなった記事（{len(gone)}件）")
        out += [f"- {link(r)}" for r in gone]
        out.append("")

    # PV急増
    surges = []
    for k, r in cur.items():
        if k not in prev:
            continue
        d = r["pv"] - prev[k]["pv"]
        past = [delta(k, "pv", a, b) for a, b in zip(window, window[1:])]
        avg = sum(past) / len(past) if past else 0
        if d >= SURGE_MIN_DELTA and (not past or d >= SURGE_RATIO * max(avg, 1)):
            surges.append((d, avg, r))
    if surges:
        out.append("### 🚀 PVが急増した記事")
        for d, avg, r in sorted(surges, key=lambda x: -x[0]):
            ratio = f"（直近平均 {avg:.1f}/日 の {d / avg:.1f}倍）" if avg >= 1 else ""
            out.append(f"- {link(r)} — 前日比 {signed(d)} PV{ratio}")
        out.append("")

    # マイルストーン到達
    ms = []
    for k, r in cur.items():
        p = prev.get(k)
        if not p:
            continue
        for m in crossed(p["pv"], r["pv"], PV_MILESTONES):
            ms.append(f"- {link(r)} が **{m:,} PV** を突破")
        for m in crossed(p["like"], r["like"], LIKE_MILESTONES):
            ms.append(f"- {link(r)} が **スキ {m:,}** を突破")
    if ms:
        out.append("### 🏅 マイルストーン到達")
        out += ms
        out.append("")

    # コメント増加
    cm = [(r["comment"] - prev[k]["comment"], r) for k, r in cur.items()
          if k in prev and r["comment"] > prev[k]["comment"]]
    if cm:
        out.append("### 💬 コメントが増えた記事")
        out += [f"- {link(r)} — {signed(d)}（計 {r['comment']}）" for d, r in sorted(cm, key=lambda x: -x[0])]
        out.append("")

    # 前日比ランキング
    ranking = sorted(
        ((r["pv"] - prev[k]["pv"], r["like"] - prev[k]["like"], r) for k, r in cur.items() if k in prev),
        key=lambda x: -x[0],
    )
    top = [x for x in ranking if x[0] > 0][:5]
    if top:
        out.append("### 📈 前日比PV増加 TOP5")
        out.append("| 順位 | 記事 | PV増 | スキ増 | 累計PV |")
        out.append("|---:|---|---:|---:|---:|")
        for i, (dp, dl, r) in enumerate(top, 1):
            out.append(f"| {i} | {link(r)} | {signed(dp)} | {signed(dl)} | {r['pv']:,} |")
        out.append("")

    # スキ率
    rated = [(r["like"] / r["pv"], r) for r in cur.values() if r["pv"] >= LIKE_RATE_MIN_PV]
    if rated:
        out.append(f"### ❤️ スキ率が高い記事 TOP3（PV {LIKE_RATE_MIN_PV}以上）")
        for rate, r in sorted(rated, key=lambda x: -x[0])[:3]:
            out.append(f"- {link(r)} — {rate:.1%}（スキ {r['like']:,} / PV {r['pv']:,}）")
        out.append("")

    # 停滞（STALL_DAYS 日前から PV が増えていない記事）
    if idx >= STALL_DAYS:
        base = hist[dates[idx - STALL_DAYS]]
        stalled = [r for k, r in cur.items() if k in base and r["pv"] == base[k]["pv"]]
        if stalled:
            out.append(f"### 💤 {STALL_DAYS}日間PVが増えていない記事（{len(stalled)}件）")
            out += [f"- {link(r)}（累計 {r['pv']:,}）" for r in stalled[:10]]
            if len(stalled) > 10:
                out.append(f"- ほか {len(stalled) - 10} 件")
            out.append("")

    if not out:
        out = ["- 前日から目立った変化はありませんでした。"]
    return out


def build_report(hist: dict, today: str, summary: dict) -> str:
    dates = sorted(hist)
    cur = hist[today]
    idx = dates.index(today)
    prev = hist[dates[idx - 1]] if idx > 0 else {}

    tot = {f: sum(r[f] for r in cur.values()) for f in ("pv", "like", "comment")}
    ptot = {f: sum(r[f] for r in prev.values()) for f in ("pv", "like", "comment")}

    def tline(label, f):
        s = f"{tot[f]:,}"
        return f"| {label} | {s} | {signed(tot[f] - ptot[f]) if prev else '—'} |"

    lines = [
        f"# note ダッシュボード定点観測 {today}",
        "",
        f"- 記事数: {len(cur)}",
        f"- 比較対象: {dates[idx - 1] if prev else 'なし（初回）'}",
    ]
    if summary.get("last_calculate_at"):
        lines.append(f"- note側の集計時刻: {summary['last_calculate_at']}")
    lines += [
        "",
        "| 指標 | 累計 | 前日比 |",
        "|---|---:|---:|",
        tline("PV", "pv"),
        tline("スキ", "like"),
        tline("コメント", "comment"),
        "",
        "## 特筆事項",
        "",
        *highlights(hist, dates, today),
        "",
        "## 全記事一覧（PV順）",
        "",
        "| # | 記事 | 公開日 | PV | 前日比 | スキ | 前日比 | コメント | スキ率 |",
        "|---:|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for i, r in enumerate(sorted(cur.values(), key=lambda r: -r["pv"]), 1):
        p = prev.get(r["key"])
        dpv = signed(r["pv"] - p["pv"]) if p else "new"
        dlk = signed(r["like"] - p["like"]) if p else "new"
        rate = f"{r['like'] / r['pv']:.1%}" if r["pv"] else "—"
        lines.append(
            f"| {i} | {link(r, 60)} | {r['published_at']} | {r['pv']:,} | {dpv} "
            f"| {r['like']:,} | {dlk} | {r['comment']:,} | {rate} |"
        )
    return "\n".join(lines) + "\n"


def main():
    p = argparse.ArgumentParser(description="note 定点観測レポート生成")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--out-dir", default="reports")
    p.add_argument("--date", default="")
    args = p.parse_args()

    hist = load_history(os.path.join(args.data_dir, "history.csv"))
    today = args.date or max(hist)
    summary = {}
    sp = os.path.join(args.data_dir, "summary.json")
    if os.path.exists(sp):
        with open(sp, encoding="utf-8") as fp:
            summary = json.load(fp)
        if summary.get("date") != today:
            summary = {}

    md = build_report(hist, today, summary)
    os.makedirs(args.out_dir, exist_ok=True)
    for name in (f"{today}.md", "latest.md"):
        with open(os.path.join(args.out_dir, name), "w", encoding="utf-8") as fp:
            fp.write(md)
    # Issue 本文は文字数上限があるため、全記事一覧を除いた要約版を別に出す
    summary_md = md.split("## 全記事一覧")[0]
    summary_md += f"\n全記事一覧は `{args.out_dir}/{today}.md` を参照してください。\n"
    with open(os.path.join(args.out_dir, "issue_body.md"), "w", encoding="utf-8") as fp:
        fp.write(summary_md)
    print(f"✅ レポート出力: {args.out_dir}/{today}.md")


if __name__ == "__main__":
    main()
