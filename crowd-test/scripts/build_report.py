#!/usr/bin/env python3
"""聚合众测结果并渲染 Markdown 报告。

用法:
    python3 build_report.py --users users.json --findings findings.json \
        --base 3.4 --product "产品名" --seed 42 --out report.md \
        [--previous prev.summary.json]

findings.json 结构（由测试 agent 基于真实体验填写）:
{
  "bugs": [
    {"severity": "P0"|"P1"|"P2"|"P3"|"P4",
     "title": "一句话标题", "feature": "所属功能模块",
     "steps": "复现步骤", "expected": "预期行为", "actual": "实际行为",
     "suggestion": "修复建议", "reporter": "U010"}
  ],
  "quotes": [{"user": "U010", "text": "用户原声"}]
}

评分公式（确定性，同 seed 可复现）:
    score = clamp(round(base + rating_bias*0.5 + noise, 1), 1.0, 5.0)
    noise ~ N(0, 0.35)，按 seed+用户ID 派生

同时输出 <out去掉.md>.summary.json，供 --previous 回归对比使用。
"""
import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from datetime import date

SEVERITY_ORDER = ["P0", "P1", "P2", "P3", "P4"]
SEVERITY_NAMES = {"P0": "致命", "P1": "严重", "P2": "一般", "P3": "轻微", "P4": "建议"}


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def compute_ratings(users, base, seed):
    for u in users:
        rng = random.Random(f"{seed}:{u['id']}")
        noise = rng.gauss(0, 0.35)
        u["score"] = clamp(round(base + u["rating_bias"] * 0.5 + noise, 1), 1.0, 5.0)
    return users


def star_bucket(score):
    if score >= 4.5: return 5
    if score >= 3.5: return 4
    if score >= 2.5: return 3
    if score >= 1.5: return 2
    return 1


def bar(pct, width=20):
    n = round(pct / 100 * width)
    return "█" * n + "░" * (width - n)


def validate_findings(findings, user_by_id):
    bugs = findings.get("bugs", [])
    for i, b in enumerate(bugs, 1):
        b.setdefault("id", f"T-{i:04d}")
        assert b.get("severity") in SEVERITY_ORDER, f"Bug {b.get('title')}: severity 必须是 P0-P4"
        for field in ("title", "feature", "steps", "expected", "actual", "suggestion", "reporter"):
            assert b.get(field), f"Bug {b['id']} 缺少字段: {field}"
        assert b["reporter"] in user_by_id, f"Bug {b['id']}: reporter {b['reporter']} 不存在"
    quotes = findings.get("quotes", [])
    for q in quotes:
        assert q.get("user") in user_by_id, f"原声引用了不存在的用户: {q.get('user')}"
        assert q.get("text"), "原声缺少 text"
    bugs.sort(key=lambda b: (SEVERITY_ORDER.index(b["severity"]), b["id"]))
    return bugs, quotes


def render(product, users, bugs, quotes, base, seed, previous):
    n = len(users)
    avg = sum(u["score"] for u in users) / n
    dist = Counter(star_bucket(u["score"]) for u in users)
    sev_c = Counter(b["severity"] for b in bugs)
    user_by_id = {u["id"]: u for u in users}

    L = []
    L.append(f"# 🏆 {product} · 300 人众测报告")
    L.append("")
    L.append(f"> 生成日期：{date.today().isoformat()} ｜ 用户种子 seed={seed} ｜ "
             f"客观质量基准分 {base} ｜ 样本量 {n} 人")
    L.append("")
    L.append("---")
    L.append("")
    # ---- 总览 ----
    L.append("## 一、总览")
    L.append("")
    L.append(f"### ⭐ 综合评分：{avg:.2f} / 5.0")
    L.append("")
    L.append("| 星级 | 分布 | 占比 | 人数 |")
    L.append("|------|------|------|------|")
    for s in (5, 4, 3, 2, 1):
        c = dist.get(s, 0)
        pct = c / n * 100
        L.append(f"| {'⭐' * s} {s} 分 | {bar(pct)} | {pct:.1f}% | {c} |")
    L.append("")
    L.append(f"**🐛 Bug 总数：{len(bugs)}**　"
             + "　".join(f"{s} {SEVERITY_NAMES[s]}: {sev_c.get(s, 0)}" for s in SEVERITY_ORDER))
    L.append("")
    if previous:
        L.append("### 📈 回归对比（与上一轮）")
        L.append("")
        prev_score = previous["avg_score"]
        delta = avg - prev_score
        arrow = "⬆️" if delta > 0 else ("⬇️" if delta < 0 else "➡️")
        L.append(f"- 综合评分：{prev_score:.2f} → **{avg:.2f}**（{arrow} {delta:+.2f}）")
        prev_bugs = previous.get("bug_total", 0)
        L.append(f"- Bug 总数：{prev_bugs} → **{len(bugs)}**（{len(bugs) - prev_bugs:+d}）")
        prev_sev = previous.get("bug_by_severity", {})
        L.append(f"- P0/P1：{prev_sev.get('P0', 0) + prev_sev.get('P1', 0)} → "
                 f"**{sev_c.get('P0', 0) + sev_c.get('P1', 0)}**")
        L.append("")
    L.append("---")
    L.append("")
    # ---- 性格分群 ----
    L.append("## 二、按性格类型的评分分群")
    L.append("")
    groups = defaultdict(list)
    for u in users:
        groups[(u["personality"], u["codename"])].append(u["score"])
    L.append("| 性格类型 | 代号 | 平均分 | 最高 | 最低 | 人数 |")
    L.append("|---------|------|--------|------|------|------|")
    for (pname, code), scores in sorted(groups.items(), key=lambda kv: -sum(kv[1]) / len(kv[1])):
        L.append(f"| {pname} | {code} | ⭐{sum(scores)/len(scores):.2f} | "
                 f"{max(scores):.1f} | {min(scores):.1f} | {len(scores)} |")
    L.append("")
    L.append("---")
    L.append("")
    # ---- Bug 清单 ----
    L.append(f"## 三、Bug 清单（{len(bugs)} 个，按严重等级排序）")
    L.append("")
    for b in bugs:
        r = user_by_id[b["reporter"]]
        env = f"{r['device']} / {r['os']} / {r['browser']} / {r['network']}"
        L.append(f"### [{b['severity']}] {b['id']} · {b['title']}")
        L.append("")
        L.append(f"- **功能模块**：{b['feature']}")
        L.append(f"- **发现用户**：{r['name']}（{r['personality']}/{r['codename']}，{r['id']}）")
        L.append(f"- **复现步骤**：{b['steps']}")
        L.append(f"- **预期行为**：{b['expected']}")
        L.append(f"- **实际行为**：{b['actual']}")
        L.append(f"- **环境信息**：{env}")
        L.append(f"- **修复建议**：{b['suggestion']}")
        L.append("")
    L.append("---")
    L.append("")
    # ---- 用户原声 ----
    L.append(f"## 四、精选用户原声（{len(quotes)} 条）")
    L.append("")
    for q in quotes:
        u = user_by_id[q["user"]]
        L.append(f"> 💬 “{q['text']}”  ")
        L.append(f"> —— {u['name']}（{u['personality']}/{u['codename']}）⭐{u['score']:.1f}")
        L.append("")
    L.append("---")
    L.append("")
    L.append("## 五、附录：300 名用户评分明细")
    L.append("")
    L.append("| ID | 姓名 | 性格 | 评分 | 设备/OS | 口头禅 |")
    L.append("|----|------|------|------|---------|--------|")
    for u in users:
        L.append(f"| {u['id']} | {u['name']} | {u['personality']}/{u['codename']} | "
                 f"⭐{u['score']:.1f} | {u['device']}/{u['os']} | {u['motto']} |")
    L.append("")
    return "\n".join(L), avg, sev_c


def print_chat_summary(product, avg, dist, n, sev_c, bugs, user_by_id):
    print(f"\n╔══════════════════════════════════════════╗")
    print(f"║   🏆 {product} · 300 人众测结果")
    print(f"╠══════════════════════════════════════════╣")
    print(f"║   综合评分  ⭐ {avg:.2f} / 5.0")
    for s in (5, 4, 3, 2, 1):
        c = dist.get(s, 0)
        pct = c / n * 100
        print(f"║   {s}分 {bar(pct, 14)} {pct:5.1f}% ({c}人)")
    print(f"║   🐛 Bug {sum(sev_c.values())} 个：" +
          "  ".join(f"{s}:{sev_c.get(s, 0)}" for s in SEVERITY_ORDER))
    print(f"╚══════════════════════════════════════════╝")
    urgent = [b for b in bugs if b["severity"] in ("P0", "P1")]
    if urgent:
        print("\n🔴 紧急修复清单（P0/P1）：")
        for b in urgent:
            r = user_by_id[b["reporter"]]
            print(f"  [{b['severity']}] {b['id']} {b['title']} —— 发现人 {r['name']}({r['personality']})")


def main():
    ap = argparse.ArgumentParser(description="聚合众测结果并渲染报告")
    ap.add_argument("--users", required=True)
    ap.add_argument("--findings", required=True)
    ap.add_argument("--base", type=float, required=True, help="客观质量基准分 1.0-5.0（基于真实体验评估）")
    ap.add_argument("--product", required=True)
    ap.add_argument("--seed", type=int, required=True, help="必须与生成用户时一致")
    ap.add_argument("--out", required=True)
    ap.add_argument("--previous", help="上一轮 summary.json，用于回归对比")
    args = ap.parse_args()

    assert 1.0 <= args.base <= 5.0, "--base 必须在 1.0-5.0 之间"
    data = json.load(open(args.users, encoding="utf-8"))
    assert data["seed"] == args.seed, f"seed 不一致：users.json 是 {data['seed']}，传入 {args.seed}"
    findings = json.load(open(args.findings, encoding="utf-8"))
    previous = json.load(open(args.previous, encoding="utf-8")) if args.previous else None

    users = compute_ratings(data["users"], args.base, args.seed)
    user_by_id = {u["id"]: u for u in users}
    bugs, quotes = validate_findings(findings, user_by_id)

    md, avg, sev_c = render(args.product, users, bugs, quotes, args.base, args.seed, previous)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(md)

    summary = {
        "product": args.product, "seed": args.seed, "date": date.today().isoformat(),
        "base_quality": args.base, "avg_score": round(avg, 3),
        "bug_total": len(bugs), "bug_by_severity": dict(sev_c),
    }
    summary_path = args.out[:-3] + ".summary.json" if args.out.endswith(".md") else args.out + ".summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    dist = Counter(star_bucket(u["score"]) for u in users)
    print_chat_summary(args.product, avg, dist, len(users), sev_c, bugs, user_by_id)
    print(f"\n报告已写入: {args.out}", file=sys.stderr)
    print(f"回归基线已写入: {summary_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
