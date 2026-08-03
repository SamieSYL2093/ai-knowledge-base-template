#!/usr/bin/env python3
"""
check.py — 发布 / 跨库同步前四合一检查（全绿才发）

落地「硬触发纪律」：把发布前的口径核对从"靠人记得跑"变成"机器必过闸"。

  1. 脱敏扫描    —— 内部人名 / 内部绝对路径，命中即拒（词表见 FORBIDDEN，可自配）
  2. 版本一致性  —— SKILL.md front matter version ↔ README.md 版本节
  3. 旧术语残留  —— 已退役机制术语不得出现在运营正文（"> 更新 / > 历史"行豁免）
  4. 文件头三行  —— 每个 .md 头部须有 用途 / 关键词 / 更新（豁免见 HEADER_EXEMPT）

只检查 git 跟踪的文件（未跟踪的本地维护文件不属于发布面）。
用法：python check.py   退出码 0=全绿，1=有拦截项
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# ── 可配置区 ─────────────────────────────────────────────
FORBIDDEN = [                       # 脱敏禁词（出现在任何受检文件即拒）
    "苏老师",
]
FORBIDDEN_PATTERNS = [              # 脱敏正则（内部绝对路径等）
    r"[A-Za-z]:\\Users\\",
    r"00 AI doc",
    r"00 Customer Files",
]
STALE_TERMS = [                     # 已退役术语（运营正文 0 残留）
    "三轨", "四轨", "快速通道", "A轨", "B轨", "C轨",
    "对号入座", "签名制", "激活标记", "签名激活",
]
STALE_EXEMPT = {                    # 有意保留旧术语的文件（变更说明/事故记录）
    "_源映射与同步说明.md",
}
HEADER_EXEMPT = {                   # 不参与文件头三行检查（人窗口/维护者文件）
    "README.md", "SKILL.md", "_push前检查清单.md", "_源映射与同步说明.md",
}
SCAN_EXEMPT = {                     # 不参与脱敏扫描（本身在讲脱敏规则）
    "_push前检查清单.md",
}
HEADER_SKIP_DIRS = {"项目模板"}      # 占位模板目录不查文件头
# ──────────────────────────────────────────────────────────


def tracked_files() -> list[Path]:
    """只取 git 跟踪的文件；git 不可用时退回全量扫描。"""
    try:
        out = subprocess.run(
            ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout
        return [ROOT / line.strip() for line in out.splitlines() if line.strip()]
    except Exception:
        return [p for p in ROOT.rglob("*") if p.is_file() and ".git" not in p.parts]


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8-sig", errors="replace")


def check_sensitive(files) -> list[str]:
    hits = []
    for p in files:
        if p.name in SCAN_EXEMPT or p.suffix not in (".md", ".py"):
            continue
        text = read(p)
        for w in FORBIDDEN:
            if w in text:
                hits.append(f"{p.relative_to(ROOT)}: 含禁词「{w}」")
        for pat in FORBIDDEN_PATTERNS:
            for m in re.finditer(pat, text):
                hits.append(f"{p.relative_to(ROOT)}: 命中内部路径模式 /{pat}/ → …{text[max(0,m.start()-15):m.end()+15]}…")
    return hits


def check_version(files) -> list[str]:
    skill = ROOT / "SKILL.md"
    readme = ROOT / "README.md"
    if not skill.exists() or not readme.exists():
        return ["SKILL.md 或 README.md 缺失"]
    m = re.search(r"^version:\s*(\S+)", read(skill), re.M)
    if not m:
        return ["SKILL.md front matter 缺 version 字段"]
    ver = m.group(1)
    if f"v{ver}" not in read(readme):
        return [f"版本不一致：SKILL.md={ver}，但 README.md 找不到 v{ver}"]
    return []


def check_stale(files) -> list[str]:
    hits = []
    for p in files:
        if p.suffix != ".md" or p.name in STALE_EXEMPT:
            continue
        for i, line in enumerate(read(p).splitlines(), 1):
            s = line.lstrip()
            if s.startswith("> 更新") or s.startswith("> 历史"):
                continue
            for t in STALE_TERMS:
                if t in line:
                    hits.append(f"{p.relative_to(ROOT)}:{i}: 旧术语「{t}」")
    return hits


def check_headers(files) -> list[str]:
    hits = []
    for p in files:
        if p.suffix != ".md" or p.name in HEADER_EXEMPT:
            continue
        if set(p.relative_to(ROOT).parts) & HEADER_SKIP_DIRS:
            continue
        head = "\n".join(read(p).splitlines()[:8])
        for tag in ("用途", "关键词", "更新"):
            if tag not in head:
                hits.append(f"{p.relative_to(ROOT)}: 头部缺「{tag}」行")
    return hits


def main() -> int:
    files = tracked_files()
    results = {
        "1.脱敏扫描": check_sensitive(files),
        "2.版本一致性": check_version(files),
        "3.旧术语残留": check_stale(files),
        "4.文件头三行": check_headers(files),
    }
    failed = False
    for name, hits in results.items():
        if hits:
            failed = True
            print(f"❌ {name}：{len(hits)} 处拦截")
            for h in hits[:20]:
                print(f"   - {h}")
        else:
            print(f"✅ {name}")
    print("\n结论：" + ("有拦截项，处理完再发布/同步" if failed else "全绿，可以发布/同步"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
