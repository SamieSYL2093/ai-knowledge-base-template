#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""知识库六维体检——按《知识库瘦身审查》（kb-slim-audit）§十七 的标准打分。

设计原则（判定式 15 单一源）：**不重复实现规则**，只 import `kb_slim_scan.py` 的检出力，
本脚本负责归类到六维 + 打分。规则新增改 `kb_slim_scan.py`，这里跟着生效。

六维：单一源 / 放对层 / 可找到 / 不过期 / 不冗余 / **可执行**
总分取**短板**（min），不取平均——平均值会掩盖致命项。

用法：
    python scripts/kb_audit.py <知识库目录>
    python scripts/kb_audit.py . --center 1-01_档案.md
    python scripts/kb_audit.py . --json
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kb_slim_scan import scan, read  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 扫描规则 → 维度（放对层与可执行不在此表，单独处理）
RULE_DIM = {
    "S3": 1, "S4": 1,              # 单一源：复述中心文档 / 同名聚类
    "S8": 3,                       # 可找到：孤儿文件
    "S5": 4, "S7": 4, "S9": 4,     # 不过期：头注堆叠 / 死链 / 久挂待办
    "S1": 5, "S2": 5, "S6": 5,     # 不冗余：大文件 / 数据当文档 / 命名笼统
}
DIM_NAMES = {1: "单一源", 2: "放对层", 3: "可找到",
             4: "不过期", 5: "不冗余", 6: "可执行"}
PENALTY = {"高": 20, "中": 8, "低": 3}
# 这两个维度机器判不了/只能粗判，报告里要说明白，别让人以为体检过了就没事
MANUAL_NOTE = {
    2: "机器判不了——内容该在哪一层，得对照第十五节人工过",
    6: "只粗查「宣称即实现」，规范写得对不对管不了",
}


# 提到脚本但同时提到别处仓名/路径 → 是跨仓指针，不是本仓欠缺
OTHER_REPO_HINT = re.compile(r"P\d{2}|见\s|→|→|[/\\][A-Za-z]|仓\b|skill\b")


def check_executable(root: Path, mds) -> list:
    """维度 6 可执行：正文提到的脚本是不是真存在（宣称即实现）。

    排除**跨仓指针**——"去 skill-forge 找 skill_lint.py"不是本仓缺文件。
    不做这层判断，指路牌式的规范会被刷成一片红（实测总仓就这样）。
    """
    miss = []
    for p in mds:
        try:
            text = read(p)
        except Exception:
            continue
        for line in text.splitlines():
            if OTHER_REPO_HINT.search(line):
                continue
            for rel in sorted(set(re.findall(r"(?:scripts|tools)[/\\]([\w.-]+\.(?:py|sh|cmd|ps1))", line))):
                if not (root / "scripts" / rel).exists() and not (root / "tools" / rel).exists():
                    miss.append((p.relative_to(root).as_posix(), rel))
            for rel in sorted(set(re.findall(r"python\s+([\w./\\-]+\.py)", line))):
                if not (root / rel).exists():
                    miss.append((p.relative_to(root).as_posix(), rel))
    return miss


def truly_orphan(root: Path, mds, rel: str) -> bool:
    """S8 的二次确认：文件是否真没人引用。

    扫描器按**完整文件名**匹配，可实际引用常写简写（如 `2-06` 而非 `2-06_文件夹基本规范`）。
    这里补一道：按编号前缀再找一遍，找到了就不算孤儿。
    （简写引用让人读着省事，却让机器追不到——改名时会漏改，属判定式 21 的亲戚）
    """
    p = root / rel
    m = re.match(r"(\d+-\d+)", p.stem)
    if not m:
        return True
    short = m.group(1)
    for q in mds:
        if q == p:
            continue
        try:
            if short in read(q):
                return False
        except Exception:
            pass
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description="知识库六维体检（kb-slim-audit §十七）")
    ap.add_argument("path", help="知识库目录")
    ap.add_argument("--center", default=None, help="中心文档（复述检测基准）")
    ap.add_argument("--big", type=int, default=300, help="大文件行数阈值，默认 300")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    args = ap.parse_args()

    root = Path(args.path).resolve()
    if not root.is_dir():
        print(f"不是目录：{root}")
        return 1

    center = Path(args.center) if args.center else None
    mds, findings, kws, center_doc = scan(root, center, args.big, 10 ** 6)

    scores, detail = {}, {d: [] for d in range(1, 7)}
    for d in range(1, 7):
        scores[d] = 100

    for f in findings:
        dim = RULE_DIM.get(f[0])
        if not dim:
            continue
        # S8 孤儿：先用编号前缀二次确认，排除"简写引用"造成的误报
        if f[0] == "S8" and not truly_orphan(root, mds, f[4]):
            continue
        scores[dim] -= PENALTY.get(f[2], 5)
        detail[dim].append(f"[{f[0]}] {f[4]}：{f[5]}")

    miss = check_executable(root, mds)
    for rel, script in miss:
        scores[6] -= 8
        detail[6].append(f"{rel} 提到 {script}，但文件不存在")

    scores = {d: max(0, v) for d, v in scores.items()}
    total = min(scores.values())
    worst = [d for d, v in scores.items() if v == total]

    if args.json:
        print(json.dumps({
            "root": str(root), "files": len(mds), "total": total,
            "weakest": [DIM_NAMES[d] for d in worst],
            "scores": {DIM_NAMES[d]: v for d, v in scores.items()},
            "detail": {DIM_NAMES[d]: v for d, v in detail.items() if v},
        }, ensure_ascii=False, indent=2))
        return 0

    print(f"知识库六维体检 — {root}")
    print(f"扫描 {len(mds)} 个 MD" + (f"；复述基准：{center_doc}" if center_doc else ""))
    print()
    print(f"{'维度':<8}{'得分':>5}   问题")
    print("-" * 68)
    for d in range(1, 7):
        n = len(detail[d])
        mark = " ← 短板" if d in worst and total < 100 else ""
        print(f"{DIM_NAMES[d]:<8}{scores[d]:>5}   {n} 项{mark}")
    print("-" * 68)
    print(f"{'总分（取短板）':<8}{total:>5}")
    print()
    for d in sorted(worst):
        if total < 100:
            print(f"短板是「{DIM_NAMES[d]}」，下次治理先治它。")
    for d, note in MANUAL_NOTE.items():
        print(f"· 「{DIM_NAMES[d]}」{note}。")
    if detail:
        print()
        print("明细（每维最多 3 条）：")
        for d in range(1, 7):
            if detail[d]:
                print(f"  【{DIM_NAMES[d]}】")
                for line in detail[d][:3]:
                    print(f"    {line[:88]}")
    print("\n（本工具只报不修；评分是筛子不是判决，业务判断仍归人。）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
