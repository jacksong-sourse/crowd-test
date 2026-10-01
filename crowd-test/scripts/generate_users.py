#!/usr/bin/env python3
"""确定性生成 300 名虚拟众测用户画像。

用法:
    python3 generate_users.py --seed 42 --out users.json
    python3 generate_users.py --seed 42 --out users.json --quiet   # 不打印样本表

输出 users.json 结构:
    {"seed": int, "count": 300, "users": [ {用户画像}, ... ]}

同一 seed 生成结果完全一致，可用于修复后的回归对比。
"""
import argparse
import json
import random
import sys

# ---------------------------------------------------------------------------
# 30 种性格类型: (性格, 代号, tech范围, patience范围, pickiness范围,
#               rating_bias范围, bug_sensitivity范围, 年龄段池, 口头禅池)
# ---------------------------------------------------------------------------
PERSONALITIES = [
    ("完美主义者", "细节控", (6, 9), (3, 6), (8, 10), (-2, -1), (0.8, 1.2),
     ["26-35", "36-45"],
     ["差 1px 也敢上线？", "细节见人品。", "这个圆角不统一我看了一晚上。"]),
    ("暴躁老哥", "急性子", (3, 6), (1, 2), (6, 9), (-2, -1), (0.6, 1.0),
     ["26-35", "36-45"],
     ["三秒打不开我就卸载。", "别跟我扯什么加载动画。", "点两下没反应就是垃圾。"]),
    ("技术宅", "极客", (8, 10), (5, 8), (6, 8), (-1, 0), (1.0, 1.5),
     ["18-25", "26-35"],
     ["让我看看你的源码。", "这个边界条件测过吗？", "API 文档呢？"]),
    ("小白用户", "小白", (1, 3), (4, 7), (3, 6), (0, 1), (0.3, 0.6),
     ["18-25", "26-35", "36-45"],
     ["这个按钮是干嘛的？", "我点哪？", "说明书在哪？"]),
    ("商务精英", "效率党", (5, 7), (3, 5), (4, 6), (0, 1), (0.2, 0.5),
     ["26-35", "36-45"],
     ["时间就是金钱。", "能一键完成别让我点三下。", "界面丑没关系，快就行。"]),
    ("学生党", "预算有限", (4, 6), (5, 8), (5, 7), (0, 1), (0.3, 0.6),
     ["18-25"],
     ["免费版够用吗？", "学生优惠有吗？", "白嫖使我快乐。"]),
    ("设计师", "审美癌", (5, 8), (4, 6), (8, 10), (-1, 0), (0.4, 0.7),
     ["26-35"],
     ["这个配色我要瞎了。", "字体行距都不对。", "交互一点都不丝滑。"]),
    ("产品经理", "逻辑怪", (6, 8), (5, 7), (7, 9), (-1, 0), (0.6, 0.9),
     ["26-35", "36-45"],
     ["这个流程不符合用户心智。", "需求闭环了吗？", "我为什么要先填这个？"]),
    ("老年用户", "慢节奏", (1, 3), (6, 9), (4, 6), (0, 1), (0.3, 0.6),
     ["56-65", "65+"],
     ["字能调大点吗？", "这个图标是什么意思？", "慢慢来，不着急。"]),
    ("安全专家", "白帽", (9, 10), (5, 7), (7, 9), (-1, 0), (1.0, 1.5),
     ["26-35", "36-45"],
     ["这个接口鉴权了吗？", "让我试试注入。", "数据是明文传的？"]),
    ("性能狂魔", "测速人", (8, 10), (2, 4), (6, 8), (-1, 0), (0.7, 1.0),
     ["18-25", "26-35"],
     ["超过 1 秒就是慢。", "让我压测一下。", "首屏多少毫秒？"]),
    ("苹果用户", "生态党", (5, 8), (4, 6), (7, 9), (-1, 0), (0.3, 0.6),
     ["26-35"],
     ["为什么不像 iOS 那样顺滑？", "动画掉帧了。", "一致性呢？"]),
    ("开源爱好者", "自由派", (7, 10), (5, 8), (5, 7), (0, 1), (0.2, 0.5),
     ["26-35", "36-45"],
     ["支持插件吗？", "能自定义吗？", "开源我就给五星。"]),
    ("打工人", "工具人", (3, 6), (4, 6), (3, 5), (0, 2), (0.1, 0.4),
     ["26-35", "36-45"],
     ["能用就行，我要下班。", "别整花活。", "赶紧干完活。"]),
    ("自媒体博主", "内容人", (4, 7), (4, 7), (5, 7), (0, 1), (0.3, 0.6),
     ["18-25", "26-35"],
     ["导出功能在哪？", "能一键分享吗？", "水印能去掉吗？"]),
    ("游戏玩家", "体验派", (5, 8), (3, 6), (5, 8), (0, 1), (0.3, 0.6),
     ["18-25", "26-35"],
     ["反馈不够爽快。", "延迟高得离谱。", "操作手感很重要。"]),
    ("数据控", "分析型", (6, 9), (5, 8), (5, 7), (0, 0), (0.2, 0.5),
     ["26-35", "36-45"],
     ["有统计面板吗？", "数据能导出 CSV 吗？", "给我看看趋势图。"]),
    ("夜间党", "夜猫子", (4, 7), (5, 8), (5, 7), (-1, 0), (0.3, 0.6),
     ["18-25", "26-35"],
     ["深色模式呢？", "大晚上亮瞎我。", "凌晨两点我还在用。"]),
    ("多设备用户", "同步控", (6, 8), (4, 6), (6, 8), (-1, 0), (0.6, 0.9),
     ["26-35", "36-45"],
     ["手机电脑同步了吗？", "我平板上怎么没有？", "跨端体验是刚需。"]),
    ("隐私卫士", "隐身人", (6, 9), (4, 7), (7, 9), (-1, 0), (0.6, 0.9),
     ["26-35", "36-45"],
     ["为什么要我的通讯录权限？", "数据存在哪？", "能注销账号吗？"]),
    ("新手妈妈", "忙碌型", (2, 5), (3, 6), (4, 6), (0, 1), (0.1, 0.4),
     ["26-35", "36-45"],
     ["一只手能操作吗？", "娃在哭，我没耐心。", "越简单越好。"]),
    ("自由职业者", "独狼", (5, 8), (5, 8), (5, 7), (0, 1), (0.3, 0.6),
     ["26-35", "36-45"],
     ["没网能用吗？", "离线模式对我很重要。", "别强制我登录。"]),
    ("996程序员", "疲惫码农", (8, 10), (3, 5), (6, 8), (-1, 0), (0.6, 0.9),
     ["26-35"],
     ["这个我自己写都比它强。", "和 XX 比差远了。", "快捷键都没有？"]),
    ("考研党", "专注型", (3, 6), (6, 9), (5, 7), (0, 1), (0.3, 0.6),
     ["18-25"],
     ["别给我推广告。", "界面越干净越好。", "我要专注。"]),
    ("外籍用户", "语言敏感", (4, 7), (4, 7), (6, 8), (-1, 0), (0.3, 0.6),
     ["26-35", "36-45"],
     ["Where is the English version?", "日期格式看不懂。", "翻译是机翻的吧？"]),
    ("残障用户", "无障碍", (3, 6), (5, 8), (6, 8), (0, 0), (0.6, 0.9),
     ["26-35", "36-45", "46-55"],
     ["读屏软件读不出来。", "能全键盘操作吗？", "这个对比度看不清。"]),
    ("数码小白领", "中庸派", (4, 6), (4, 7), (4, 6), (0, 0), (0.3, 0.6),
     ["26-35", "36-45"],
     ["还行吧。", "用着没什么感觉。", "中规中矩。"]),
    ("竞品用户", "对比党", (5, 8), (4, 6), (6, 8), (-1, 0), (0.3, 0.6),
     ["26-35"],
     ["XX 家早就有了。", "和竞品比差在哪？", "给我一个换过来的理由。"]),
    ("佛系用户", "无所谓", (2, 5), (8, 10), (1, 3), (1, 2), (0.1, 0.3),
     ["26-35", "36-45", "46-55"],
     ["挺好的。", "能用就行。", "都行，随便。"]),
    ("二刺猿", "二次元", (4, 7), (5, 8), (4, 6), (0, 1), (0.2, 0.5),
     ["18-25"],
     ["能换主题皮肤吗？", "二次元浓度不足。", "有表情包功能吗？"]),
]

SURNAMES = list("张李王刘陈杨赵黄周吴徐孙胡朱高林何郭马罗") + list("梁宋郑谢韩唐冯于董萧程曹袁邓许傅沈曾彭吕")

# 单字名池 + 双字名池，组合出 300 个不重复姓名
GIVEN_SINGLE = list("伟芳娜敏静丽强磊军洋勇艳杰娟涛明超秀霞平") + list("刚桂英华飞波建鑫云玲宇浩志洁文辉涵子璇宁")
GIVEN_DOUBLE = [
    "明远", "大力", "志强", "雪梅", "建国", "晓东", "雨桐", "子轩", "思远", "嘉怡",
    "浩然", "欣怡", "俊杰", "雅静", "天佑", "梦琪", "博文", "梓萱", "晨曦", "若曦",
    "宇航", "一鸣", "可欣", "沐阳", "之瑶", "景行", "乐康", "书瑶", "承宇", "向晚",
]

DEVICE_WEIGHTS = [("桌面端", 0.45), ("移动端", 0.45), ("平板", 0.10)]
# 性格特定的设备倾向（索引 -> (设备, 概率)）
DEVICE_OVERRIDE = {
    1: ("移动端", 0.85),    # 暴躁老哥
    8: ("移动端", 0.90),    # 老年用户
    # 11 苹果用户已在主逻辑中特殊处理
    20: ("移动端", 0.85),   # 新手妈妈
    10: ("桌面端", 0.90),   # 性能狂魔
    2: ("桌面端", 0.80),    # 技术宅
    9: ("桌面端", 0.85),    # 安全专家
    22: ("桌面端", 0.85),   # 996程序员
}

DESKTOP_OS = [("Windows", 0.70), ("macOS", 0.25), ("Linux", 0.05)]
MOBILE_OS = [("Android", 0.65), ("iOS", 0.35)]
BROWSERS_WIN = [("Chrome", 0.55), ("Edge", 0.25), ("Firefox", 0.10), ("360浏览器", 0.10)]
BROWSERS_MAC = [("Safari", 0.45), ("Chrome", 0.45), ("Edge", 0.10)]
NETWORKS = [("光纤", 0.35), ("家庭宽带", 0.25), ("5G", 0.20), ("4G", 0.10),
            ("校园网", 0.05), ("公司内网", 0.05)]
FREQS = [("每日", 0.35), ("每周", 0.30), ("偶尔", 0.25), ("首次", 0.10)]


def _weighted(rng, pairs):
    r = rng.random()
    acc = 0.0
    for val, w in pairs:
        acc += w
        if r <= acc:
            return val
    return pairs[-1][0]


def generate(seed: int) -> dict:
    rng = random.Random(seed)

    # --- 生成 300 个不重复姓名 ---
    combos = [f"{s}{g}" for s in SURNAMES for g in GIVEN_SINGLE] + \
             [f"{s}{g}" for s in SURNAMES for g in GIVEN_DOUBLE]
    rng.shuffle(combos)
    names = combos[:300]
    assert len(set(names)) == 300

    users = []
    idx = 0
    for p_idx, (pname, code, tech_r, pat_r, pick_r, bias_r, sens_r, ages, mottos) in enumerate(PERSONALITIES):
        for k in range(10):
            idx += 1
            uid = f"U{idx:03d}"
            # --- 设备 / 系统 / 浏览器 ---
            if p_idx == 11:  # 苹果用户
                device = _weighted(rng, [("桌面端", 0.4), ("移动端", 0.5), ("平板", 0.1)])
                os_name = {"桌面端": "macOS", "移动端": "iOS", "平板": "iPadOS"}[device]
                browser = "Safari" if device != "移动端" else "Safari(App内)"
            elif p_idx in DEVICE_OVERRIDE:
                dev, prob = DEVICE_OVERRIDE[p_idx]
                device = dev if rng.random() < prob else _weighted(rng, DEVICE_WEIGHTS)
                if device == "桌面端":
                    os_name = _weighted(rng, DESKTOP_OS)
                    browser = _weighted(rng, BROWSERS_MAC if os_name == "macOS" else BROWSERS_WIN)
                elif device == "移动端":
                    os_name = _weighted(rng, MOBILE_OS)
                    browser = {"Android": "Chrome(App内)", "iOS": "Safari(App内)"}[os_name]
                else:
                    os_name = _weighted(rng, [("iPadOS", 0.6), ("Android", 0.4)])
                    browser = "Safari(App内)" if os_name == "iPadOS" else "Chrome(App内)"
            else:
                device = _weighted(rng, DEVICE_WEIGHTS)
                if device == "桌面端":
                    os_name = _weighted(rng, DESKTOP_OS)
                    browser = _weighted(rng, BROWSERS_MAC if os_name == "macOS" else BROWSERS_WIN)
                elif device == "移动端":
                    os_name = _weighted(rng, MOBILE_OS)
                    browser = {"Android": "Chrome(App内)", "iOS": "Safari(App内)"}[os_name]
                else:
                    os_name = _weighted(rng, [("iPadOS", 0.6), ("Android", 0.4)])
                    browser = "Safari(App内)" if os_name == "iPadOS" else "Chrome(App内)"

            users.append({
                "id": uid,
                "name": names[idx - 1],
                "personality": pname,
                "codename": code,
                "tech_level": rng.randint(*tech_r),
                "patience": rng.randint(*pat_r),
                "pickiness": rng.randint(*pick_r),
                "device": device,
                "os": os_name,
                "browser": browser,
                "network": _weighted(rng, NETWORKS),
                "age_group": rng.choice(ages),
                "usage_frequency": _weighted(rng, FREQS),
                "motto": rng.choice(mottos),
                "rating_bias": rng.randint(*bias_r),
                "bug_sensitivity": round(rng.uniform(*sens_r), 2),
            })
    return {"seed": seed, "count": len(users), "users": users}


def print_summary(data: dict):
    users = data["users"]
    print(f"\n✅ 已生成 {len(users)} 名虚拟用户 (seed={data['seed']})\n")
    print("样本（前 15 + 后 15）：\n")
    print("| ID | 姓名 | 性格类型 | 代号 | 技术 | 耐心 | 挑剔 | 设备 | OS | 评分偏移 | Bug敏感 |")
    print("|----|------|---------|------|------|------|------|------|----|---------|--------|")
    for u in users[:15] + users[-15:]:
        print(f"| {u['id']} | {u['name']} | {u['personality']} | {u['codename']} | "
              f"{u['tech_level']} | {u['patience']} | {u['pickiness']} | {u['device']} | "
              f"{u['os']} | {('%+d' % u['rating_bias']) if u['rating_bias'] != 0 else '0'} | {u['bug_sensitivity']} |")
    # 统计
    from collections import Counter
    bias_c = Counter()
    for u in users:
        b = u["rating_bias"]
        bias_c["严苛(-2/-1)" if b < 0 else ("中性(0)" if b == 0 else "宽容(+1/+2)")] += 1
    sens_c = Counter()
    for u in users:
        s = u["bug_sensitivity"]
        sens_c["极高(≥0.8)" if s >= 0.8 else ("高(0.6-0.8)" if s >= 0.6 else
               ("中(0.3-0.6)" if s >= 0.3 else "低(<0.3)"))] += 1
    dev_c = Counter(u["device"] for u in users)
    pers_c = Counter(u["personality"] for u in users)
    print("\n📊 统计摘要：")
    print(f"- 性格类型：{len(pers_c)} 种 × {len(users)//len(pers_c)} 人")
    print(f"- 评分倾向：{' | '.join(f'{k} {v}人' for k, v in bias_c.items())}")
    print(f"- Bug敏感度：{' | '.join(f'{k} {v}人' for k, v in sens_c.items())}")
    print(f"- 设备分布：{' | '.join(f'{k} {v}人' for k, v in dev_c.items())}")


def main():
    ap = argparse.ArgumentParser(description="生成 300 名虚拟众测用户")
    ap.add_argument("--seed", type=int, required=True, help="随机种子（回归测试需记录复用）")
    ap.add_argument("--out", required=True, help="输出 JSON 路径")
    ap.add_argument("--quiet", action="store_true", help="不打印样本与统计")
    args = ap.parse_args()

    data = generate(args.seed)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"已写入: {args.out}", file=sys.stderr)
    if not args.quiet:
        print_summary(data)


if __name__ == "__main__":
    main()
