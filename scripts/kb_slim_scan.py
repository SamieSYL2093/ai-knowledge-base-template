#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
kb_slim_scan.py — 知识库瘦身扫描（kb-slim-audit 配套工具）

只报不修：把「机械可判」的冗余筛出来，语义判断仍交 AI/人。
零依赖，纯标准库，跨平台。

用法：
    python kb_slim_scan.py [目录] [选项]
    python kb_slim_scan.py                 # 扫当前目录
    python kb_slim_scan.py ./docs --top 15 # 指定目录，大文件 Top 15
    python kb_slim_scan.py ./docs --center 1-01_档案.md   # 指定中心文档（复述检测基准）
    python kb_slim_scan.py ./docs --json                  # JSON 输出，供其他工具消费

规则一览：
  S1 大文件         行数超阈值（默认 300）→ 可能需压缩或拆分
  S2 数据当文档     表格行/数据行占比超 60% → 应转 JSON/CSV
  S3 复述中心文档   命中中心文档关键词 ≥2 → 确认是指针还是全文抄写
  S4 同名聚类       文件名前缀相同/行数相近 → 疑似旧版残留，需 diff
  S5 头注堆叠历史   "> 更新" 行堆了多条历史 → 只留最近一次，历史交 git log
  S6 命名笼统       目录名是泛词（工具/资料/案例/其他…）→ 逼出下一层套娃
  S7 死链           md 相对链接指向不存在的文件
  S8 孤儿文件       未被任何 md 引用且不在白名单
  S9 空占位/久挂    文件几乎无内容，或含长期未兑现的待办
  S10 台账流水      台账类文件里日期开头行 ≥10 且占比 >30% → 流水回项目仓
  S11 层级超标      有声明按声明、有引用按全局默认（2-06：层级 <3）→ 超标即报；无标准不判（归 S13）
  S12 命名不可扩展  目录名是 before/after、新旧、final、备份 式——撑不过第三轮 → 改轮次/日期/版本号
  S13 缺标准        第一层目录及其上级都没声明文件夹标准 = 系统缺失（2-06 铁律①的机检）→ 先补标准

findings 结构（对齐 SKILL.md §十四 契约）：
  (规则ID, 严重度, 置信度, 类别, 位置, 证据, 建议动作)
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

# Windows GBK 控制台会炸 emoji — 强制 UTF-8
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

SKIP_DIRS = {
    "node_modules", "dist", "build", "out", ".git", ".workbuddy", ".next",
    "Temp", "temp", "_零散归档",  # 临时区与归档区不参与瘦身审查
    "archive", "_cache", ".venv", "venv", "__pycache__", "public", "assets",
    ".idea", ".vscode", "vendor", "target",
    "publish",  # 待发布副本（从本体生成的分发稿，不是冗余，见判定式 15 单源化）
    "tests",  # 回归测试语料：fixtures 里故意埋着问题样本，扫了只会淹没真实报告
}
# 判定式 9：笼统目录名（逼出下一层套娃）
VAGUE_DIRS = {
    "工具", "资料", "案例", "其他", "其他资料", "文件", "文档", "素材", "资源",
    "tools", "docs", "files", "misc", "other", "temp", "tmp", "stuff",
}
# 2-06 铁律「层级 <3」的全局默认：目录最多 2 层（目录声明可覆盖，见 kbstd）
DEFAULT_MAX_DEPTH = 2
# 文件夹标准声明：目录在自己 AGENTS.md / README.md 里写一行机器可读声明，例如
#   <!-- kbstd: max-depth=none reason=记忆快照原样保留 -->
#   <!-- kbstd: max-depth=4 reason=代码工程 -->
KBSTD_RE = re.compile(r"<!--\s*kbstd:\s*([^>]*?)-->", re.I | re.S)


def dir_declared(d: Path):
    """读目录自己的文件夹标准声明。

    返回 ('kbstd', limit|None, reason)：本目录有显式声明（limit=None 表示不限深度）；
         ('inherit',)：引用了 2-06（按全局默认）；
         None：全链无标准（系统缺失）。
    """
    for fn in ("AGENTS.md", "README.md"):
        f = d / fn
        if not f.is_file():
            continue
        t = read(f)
        m = KBSTD_RE.search(t)
        if m:
            kv = dict(re.findall(r"([\w-]+)\s*=\s*([^\s]+)", m.group(1)))
            md = kv.get("max-depth", "").lower()
            limit = None if md in ("none", "") else (int(md) if md.isdigit() else None)
            return ("kbstd", limit, kv.get("reason", ""))
        if "2-06" in t or "文件夹基本规范" in t:
            return ("inherit",)
    return None
# 不可扩展目录名：before/after、新旧、final 式命名撑不过第三轮（起名问一句「第三轮怎么办」）
NONEXT_DIRS = {
    "before", "after", "old", "new", "final", "backup",
    "新旧", "旧版", "新版", "最终", "最终版", "备份",
}
# 代码工程豁免（S11）：代码项目的目录深度由框架生态决定，不受 2-06「层级 <3」约束。
# 识别代码项目根（满足任一）：依赖/构建清单文件、.sln/.csproj 类工程文件、
# 自带 venv、或同目录 ≥3 个同源代码文件（≥3 是为了不误伤"只带一个脚本"的文档仓）。
CODE_MARKERS = {
    "package.json", "pyproject.toml", "requirements.txt", "pipfile",
    "cargo.toml", "go.mod", "pom.xml", "build.gradle", "composer.json", "gemfile",
}
CODE_EXTS = {".py", ".js", ".ts", ".java", ".cs", ".go", ".rs", ".cpp", ".c"}


def is_code_root(d: Path) -> bool:
    try:
        names = {n.lower() for n in os.listdir(d)}
    except OSError:
        return False
    if names & CODE_MARKERS:
        return True
    if any(n.endswith((".sln", ".csproj", ".vcxproj")) for n in names):
        return True
    if "venv" in names or ".venv" in names:
        return True
    return sum(1 for n in names if Path(n).suffix.lower() in CODE_EXTS) >= 3


def _is_under(p: Path, ancestor: Path) -> bool:
    try:
        p.resolve().relative_to(ancestor)
        return True
    except ValueError:
        return False
# 判定式 11：头注里的历史堆叠
UPDATE_LINE = re.compile(r"^\s*>\s*(更新|最后更新|Updated|历史|变更)\s*[:：]")
# 判定式 18：久挂待办
# 只认真正的任务标记：行首（可带列表符）的待办类词，或紧跟冒号/括号的 TODO/FIXME。
# 正文里谈论"待办"这个概念的措辞不算——否则讲方法论的文档自己先中枪。
TODO_RE = re.compile(
    r"(?im)^[ \t]*(?:[-*+>]|\d+[.)])?[ \t]*(?:TODO|FIXME|XXX待|待办|待补|待确认|待拍板)"
    r"|\b(?:TODO|FIXME)\s*[:：（(]"
)
# 数据行（判定式 2/6）：表格行、JSON/JS 对象行
DATA_ROW = re.compile(r"^\s*(\|.*\||\{.*\}\s*,?\s*$|\[.*\]\s*,?\s*$|\{k:|\{q:)")
# md 相对链接
MD_LINK = re.compile(r"\[([^\]]+)\]\(([^)#:]+\.md)\)")
# 台账/清单类：表格是本职，不参与「数据当文档」判定
LEDGER_NAMES = ("清单", "台账", "索引", "登记表", "目录", "表")
# 判定式 10：台账里的日期流水行（行首可带列表/表格符，紧跟日期；"> 更新：…" 不算，那是 S5 的事）
DATE_FLOW = re.compile(r"^\s*(?:[-*+]|\||\d+[.)])?\s*\*{0,2}(?:\d{4}[-/]\d{2}[-/]\d{2}|\d{4}年\d{1,2}月)")
# 各项目标配的同名文件：跨目录同名很正常，不参与聚类判定
STANDARD_NAMES = {"README", "AGENTS", "CHANGELOG", "LICENSE", "CLAUDE", "SKILL", "指挥中心"}


def iter_md(root: Path):
    """遍历 MD，跳过依赖/构建/缓存目录。"""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for f in filenames:
            if f.lower().endswith(".md"):
                yield Path(dirpath) / f


def read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        try:
            return p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return ""


def center_keywords(center: Path | None, root: Path):
    """从中心文档（档案/总纲/宪法类）提取术语级关键词，用于复述检测。

    只取「表格首列」与「编号列表」里的加粗词——那是术语，不是句子。
    返回 (关键词列表, 中心文档路径)。
    """
    if center is None:
        # 自动找：名字里含 档案/总纲/宪法 的根级 md（不用 README，避免把宣传语当术语）
        for cand in sorted(root.glob("*.md")):
            if any(k in cand.name for k in ("档案", "总纲", "宪法", "原则")):
                center = cand
                break
    if center is None or not center.exists():
        return [], None
    t = read(center)
    # 签名登记表常混在中心文档里，但那是 AI 名字、不是原则术语——遇到它的**标题行**才截断。
    # 注意：不能按字符串整体切——文档头部说明里往往就写着"…+ AI 签名登记表"，会把正文切没了。
    kept = []
    for ln in t.split("\n"):
        if re.match(r"^#{1,4}\s.*(签名登记表|签名表|签名登记)", ln):
            break
        kept.append(ln)
    t = "\n".join(kept)
    kws = set()
    # 中心文档写法千差万别，多认几种：编号加粗术语 / 问答式箭尾 / 小标题
    patterns = [
        r"^\s*\d+\.\s*\*{0,2}([^*\n]{2,12})\*{0,2}",    # 1. **术语** — 说明
        r"→\s*\*{0,2}([^*\n→；。，]{2,12})\*{0,2}",      # …吗？—— 是 → 术语
        r"^#{2,4}\s+\*{0,2}([^*\n]{2,12})\*{0,2}\s*$",  # ### 术语
    ]
    for pat in patterns:
        for m in re.finditer(pat, t, re.M):
            kws.add(m.group(1).strip())
    # 表格行：优先抓整行加粗词（| 1 | **术语** | 的术语常在第二列，抓首列只会抓到序号）；
    # 整行无加粗时退回首列（| **术语** | … 与 | 术语 | … 两种都兜住）
    for ln in t.split("\n"):
        if not ln.lstrip().startswith("|"):
            continue
        bolds = re.findall(r"\*\*([^*\n]{2,12})\*\*", ln)
        if bolds:
            kws.update(b.strip() for b in bolds)
        else:
            m = re.match(r"^\s*\|\s*([^*|]{2,12})\s*\|", ln)
            if m:
                kws.add(m.group(1).strip())
    # 去掉：含标点/空白的（句子不是术语）、纯符号（表格分隔行残留）
    kws = {k for k in kws
           if k and not re.search(r"[，。、；：？！\s（）()]", k)
           and re.search(r"[\u4e00-\u9fa5A-Za-z]", k)}
    return sorted(kws, key=len, reverse=True)[:40], center


def scan(root: Path, center: Path | None, big_threshold: int, top: int):
    mds = list(iter_md(root))
    kws, center_doc = center_keywords(center, root)
    findings = []
    all_text = {p: read(p) for p in mds}
    # 全局引用索引（孤儿检测）：p 被引用 = 有链接指向 p，或 p 的文件名出现在别的文件里
    refd = set()
    for p, t in all_text.items():
        for m in MD_LINK.finditer(t):
            try:
                refd.add((p.parent / m.group(2)).resolve())
            except Exception:
                pass
        base = p.stem
        for q in mds:
            if q != p and base in all_text[q]:
                refd.add(p.resolve())
                break

    for p in mds:
        rel = p.relative_to(root).as_posix()
        lines = all_text[p].split("\n")
        n = len(lines)
        non_empty = [l for l in lines if l.strip()]

        # S1 大文件
        if n >= big_threshold:
            findings.append(("S1", "M", "中", "大文件", rel, f"{n} 行",
                             "压缩为要点表，或拆分为多个文件"))

        # S2 数据当文档（台账/清单类豁免——表格是它们的本职，不是冗余；台账的冗余由 S10 管）
        if non_empty and not any(k in p.name for k in LEDGER_NAMES):
            data_n = sum(1 for l in non_empty if DATA_ROW.match(l))
            if data_n >= 50 and data_n / len(non_empty) > 0.6:
                findings.append(("S2", "H", "中", "数据当文档", rel,
                                 f"数据行占比 {data_n * 100 // len(non_empty)}%（{data_n}/{len(non_empty)}）",
                                 "转 JSON/CSV 存档，MD 只留指针"))

        # S3 复述中心文档（排除中心文档自身）
        if kws and p.resolve() != center_doc.resolve():
            hit = [k for k in kws if k in all_text[p]]
            if len(hit) >= 2:
                findings.append(("S3", "M", "中", "疑似复述", rel,
                                 f"命中中心文档关键词 {len(hit)} 个（{'、'.join(hit[:4])}）",
                                 "确认是合法指针还是全文抄写；抄写则改指针"))

        # S5 头注堆叠历史：多行各带日期（常见形态）或单行堆多个日期
        upd = [(i, l) for i, l in enumerate(lines[:15], 1) if UPDATE_LINE.match(l)]
        if len(upd) >= 2 or any(len(re.findall(r"\d{4}-\d{2}-\d{2}", l)) >= 2 for _, l in upd):
            detail = (f'"> 更新" 类头注堆了 {len(upd)} 行' if len(upd) >= 2
                      else "单行头注堆了多个日期")
            findings.append(("S5", "L", "高", "头注堆叠", f"{rel}:{upd[0][0]}", detail,
                             "只留最近一次，历史交 git log"))

        # S7 死链
        for m in MD_LINK.finditer(all_text[p]):
            tgt = (p.parent / m.group(2)).resolve()
            if not tgt.exists():
                findings.append(("S7", "H", "高", "死链", rel, f"链接 ({m.group(2)}) 指向不存在的文件",
                                 "修复路径或删除链接"))

        # S8 孤儿（根级与一级；README/AGENTS/CHANGELOG/LICENSE 天然不被引用）
        is_center = center_doc is not None and p.resolve() == center_doc.resolve()
        if (not is_center and p.resolve() not in refd and p.name not in {
            "README.md", "AGENTS.md", "CHANGELOG.md", "LICENSE", "CLAUDE.md"
        }):
            depth = len(p.relative_to(root).parts)
            if depth <= 2:
                findings.append(("S8", "L", "中", "孤儿文件", rel, "未被任何 md 引用",
                                 "确认是否归档或删除"))

        # S9 空占位 / 久挂待办
        if n <= 3 and len("".join(non_empty)) < 40:
            findings.append(("S9", "M", "高", "空占位", rel, f"仅 {n} 行、内容极少",
                             "补内容或删除占位"))
        todos = TODO_RE.findall(all_text[p])
        if len(todos) >= 3:
            findings.append(("S9", "L", "中", "久挂待办", rel, f"含 {len(todos)} 处待办标记",
                             "兑现或删掉；久挂的待办等于噪音"))

        # S10 台账流水（判定式 10）：台账类文件里日期开头的行堆太多——流水回项目仓
        if non_empty and any(k in p.name for k in LEDGER_NAMES):
            flow = [l for l in non_empty if DATE_FLOW.match(l)]
            if len(flow) >= 10 and len(flow) / len(non_empty) > 0.3:
                findings.append(("S10", "M", "中", "台账流水", rel,
                                 f"日期流水行 {len(flow)} 行（占 {len(flow) * 100 // len(non_empty)}%）",
                                 "流水回项目仓 README/git log，台账只留定位与关键事实"))

    # S4 同名聚类（**同一目录内**比较——跨目录的 README/AGENTS 是每个项目的标配，不算冗余）
    by_stem = {}
    for p in mds:
        stem = re.sub(r"[-_vV]?\d+.*$", "", p.stem).strip("-_ ")
        by_stem.setdefault((p.parent, stem), []).append(p)
    for (parent, stem), group in by_stem.items():
        if len(group) >= 2 and stem and stem not in STANDARD_NAMES:
            sizes = [len(read(x).split("\n")) for x in group]
            if max(sizes) >= 30:
                rel_p = parent.relative_to(root).as_posix()
                findings.append(("S4", "M", "中", "同名聚类", f"{rel_p}/{stem}*",
                                 f"同目录 {len(group)} 个同名前缀文件（行数 {sizes}）",
                                 "diff 确认：旧版残留则归档，职责不同则保留并改名区分"))

    # S6 命名笼统 / S11 层级超标 / S12 命名不可扩展 / S13 缺标准
    # 判断链（08-29 定）：先问「有没有标准」——有声明按声明查；无声明但上级引用了
    # 2-06 按全局默认查；全链都没有 = 系统缺失（S13），缺失本身先报，**无标准不判违规**。
    code_roots = {root.resolve()} if is_code_root(root) else set()
    eff = {}  # resolved 目录 -> 生效标准（('kbstd', limit|None, reason) / ('inherit',) / None）
    for dirpath, dirnames, _ in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        pdir = Path(dirpath)
        own = dir_declared(pdir)
        parent_eff = None if pdir == root else eff.get(pdir.resolve().parent)
        eff[pdir.resolve()] = own or parent_eff
        in_code = any(_is_under(pdir, cr) for cr in code_roots)
        base_depth = len(pdir.relative_to(root).parts)
        for d in list(dirnames):
            sub = pdir / d
            rel_d = sub.relative_to(root).as_posix()
            sub_eff = dir_declared(sub) or eff[pdir.resolve()]
            if is_code_root(sub):
                code_roots.add(sub.resolve())
            # S13 缺标准（只查第一层：2-06 铁律①「第一层必有规范」的机检）
            if base_depth == 0 and sub_eff is None:
                hint = ("；检测到代码工程特征（venv/依赖清单/源码），"
                        "建议声明 max-depth=none reason=代码工程") if is_code_root(sub) else ""
                findings.append(("S13", "M", "高", "缺标准", rel_d,
                                 "本目录及上级均未声明文件夹标准——系统缺失，无标准则无法判合规" + hint,
                                 "在其 AGENTS.md/README.md 加一行 <!-- kbstd: max-depth=N|none reason=… -->，或引用总仓 2-06"))
            # S11 层级超标：有标准才判；标准来源写进证据。只报每支分支第一个超标目录，不级联刷屏
            limit, src = None, ""
            if sub_eff and sub_eff[0] == "kbstd":
                limit, src = sub_eff[1], "本目录声明"
            elif sub_eff:
                limit, src = DEFAULT_MAX_DEPTH, "全局默认（2-06 层级 <3）"
            if limit is not None and base_depth + 1 > limit:
                code_note = "；检测到代码工程特征——若属框架结构，请声明 kbstd 豁免而非默默超标" if in_code else ""
                findings.append(("S11", "L", "高", "层级超标", rel_d,
                                 f"目录第 {base_depth + 1} 层，超过{src}标准 max-depth={limit}{code_note}",
                                 "压平或归并；有意保留的（快照/工程结构）在最近目录声明 kbstd，而不是默默超标"))
                dirnames.remove(d)
                continue
            if d in VAGUE_DIRS:
                findings.append(("S6", "M", "高", "命名笼统", d, "泛词目录名会逼出下一层套娃",
                                 "改成具体名字，或解散该层"))
            if d.lower() in NONEXT_DIRS or d in NONEXT_DIRS:
                findings.append(("S12", "M", "中", "命名不可扩展", rel_d,
                                 f"「{d}」式命名撑不过第三轮（再来一轮叫什么？）",
                                 "改可扩展命名：轮次 r0/r1…、日期、版本号"))

    return mds, findings, kws, center_doc


def main():
    ap = argparse.ArgumentParser(description="知识库瘦身扫描（只报不修）")
    ap.add_argument("path", nargs="?", default=".", help="要扫描的目录（默认当前目录）")
    ap.add_argument("--center", help="中心文档路径（复述检测基准，默认自动找档案/总纲/README）")
    ap.add_argument("--big", type=int, default=300, help="大文件行数阈值（默认 300）")
    ap.add_argument("--top", type=int, default=10, help="大文件 Top N（默认 10）")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    args = ap.parse_args()

    root = Path(args.path).resolve()
    if not root.is_dir():
        print(f"❌ 不是目录：{root}")
        sys.exit(1)
    center = Path(args.center).resolve() if args.center else None

    mds, findings, kws, center_doc = scan(root, center, args.big, args.top)
    order = {"H": 0, "M": 1, "L": 2}
    findings.sort(key=lambda f: (order[f[1]], f[3]))

    if args.json:
        # 对齐 SKILL.md §十四 findings 契约：规则 ID + 位置 + 证据 + 置信度
        print(json.dumps(
            [{"rule": r, "severity": s, "confidence": cf, "category": c,
              "location": loc, "problem": pr, "action": ac}
             for r, s, cf, c, loc, pr, ac in findings],
            ensure_ascii=False, indent=1))
        return

    icon = {"H": "🔴", "M": "🟡", "L": "⚪"}
    print(f"知识库瘦身扫描 — 目录：{root}")
    if kws:
        scan_note = f"；复述检测基准：{center_doc.name}，提取 {len(kws)} 个关键词"
    elif center_doc is not None:
        scan_note = (f"；⚠️ 找到中心文档 {center_doc.name} 但提取到 0 个关键词，复述检测已跳过"
                     "（疑似真空绿——请检查中心文档写法，或用 --center 指定）")
    else:
        scan_note = "（未找到中心文档，跳过复述检测）"
    print(f"扫描 {len(mds)} 个 MD" + scan_note)
    print()
    hi = [f for f in findings if f[1] == "H"]
    mid = [f for f in findings if f[1] == "M"]
    lo = [f for f in findings if f[1] == "L"]
    print(f"问题总数：{len(findings)}（🔴高 {len(hi)} / 🟡中 {len(mid)} / ⚪低 {len(lo)}）")
    if not findings:
        print("  无明显机械可判的冗余。")
    else:
        print("可执行项：")
        for r, s, cf, c, loc, pr, ac in findings[:args.top * 3]:
            print(f"  [{icon[s]}][{r} {c}·置信{cf}] {loc}：{pr} → {ac}")
        if len(findings) > args.top * 3:
            print(f"  …（其余 {len(findings) - args.top * 3} 条，加 --top 调大显示条数）")
    print("\n（本工具只报不修；语义类冗余需人工判断，修复后署名 commit。）")


if __name__ == "__main__":
    main()
