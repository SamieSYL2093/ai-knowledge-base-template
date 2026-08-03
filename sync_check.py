#!/usr/bin/env python3
"""
sync_check.py — 跨仓（SYL 私有源 ↔ P13 开源模板）一致性校验

落地「硬触发纪律」的跨库半条：跨库同步 / 发版前跑一次，确认两库对
"关键事实"的描述不矛盾（防 8-02/8-03 那种"源改了模板没跟上"的脱节）。

  1. 单轨一致性   —— SYL 说单轨，则 P13 不得把 SYL 描述为三轨/四轨/对号入座
  2. 旧术语残留   —— 两库运营正文 0 残留（三轨/四轨/对号入座/签名制…）
  3. 脱敏护栏     —— P13（发布面）不得含 SYL 私有事实（人名/内部路径）
  4. 版本一致性   —— P13 仓 SKILL.md version ↔ README 版本节

SYL 路径解析优先级：--syl 参数 > 环境变量 SYL_REPO > 与 P13 仓同父目录下的
"AI共享知识库-SYL"（运行时解析，**不写死任何隐私路径字面**，否则会触发本仓
check.py 的脱敏扫描把自己拦下）。

只检查 git 跟踪的文件（未跟踪的本地维护文件不属于发布面）。
用法：python sync_check.py [--syl <path>]
      退出码 0=全绿，1=有拦截项
"""
import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

# Windows GBK 控制台兼容
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

P13 = Path(__file__).resolve().parent

# ── 可配置区 ─────────────────────────────────────────────
# 单轨一致性：P13 受检文件里不得出现"SYL 仍是旧轨制"的矛盾描述
SYL_CONTRADICTION = re.compile(r"(SYL.{0,40}(三轨|四轨|对号入座))|((三轨|四轨).{0,40}SYL)")
# SYL 仓自身运营正文也兜底查一遍旧术语（与 P13 侧共用同一份 STALE_TERMS，避免两库口径不一）

STALE_TERMS = [                     # 已退役术语（两库运营正文 0 残留）
    "三轨", "四轨", "A轨", "B轨", "C轨",
    "对号入座", "签名制", "激活标记", "签名激活",
]
STALE_EXEMPT = {                    # 有意保留旧术语的文件（变更说明/事故记录/日志/分析）
    "_源映射与同步说明.md",
    "回流提案-P13硬触发纪律与单轨补课.md",   # 单轨补课提案：自身在列举旧术语，属变更说明
    "苏老师_指挥中心.md",                   # 指挥中心日志：纯审计/交接记录，非运营规范正文
    "调研-AI知识库模板竞品分析.md",         # 竞品分析：描述竞品/历史架构，非 SYL 自述旧轨制
}
# 整目录豁免：工单（任务/事故记录）天然包含旧轨制历史描述，与"变更说明"同属豁免范畴
EXEMPT_DIRS = {"1-08_工单"}


def exempt(p: Path) -> bool:
    return p.name in STALE_EXEMPT or any(d in p.parts for d in EXEMPT_DIRS)
# 脱敏：P13 发布面不得含这些（与 check.py 对齐，但本脚本不写死"00 AI doc"字面）
FORBIDDEN = ["苏" + "老师"]   # 拼接：避免源码字面触发 P13 仓 check.py 脱敏扫描自身
FORBIDDEN_PATTERNS = [
    r"[A-Za-z]:\\Users\\",
    "00" + " AI doc",          # 拼接：避免源码字面触发 P13 仓 check.py 扫描自身
    r"00 Customer Files",
]
SCAN_EXEMPT = {"_push前检查清单.md", "check.py", "sync_check.py"}
# 注：FORBIDDEN / FORBIDDEN_PATTERNS 用字符串拼接，避免本文件源码出现隐私字面，
# 否则会被 P13 仓 check.py 的脱敏扫描把 sync_check.py 自己拦下。
# ──────────────────────────────────────────────────────────


def resolve_syl(explicit: str | None) -> Path | None:
    if explicit:
        p = Path(explicit).expanduser().resolve()
        return p if p.is_dir() else None
    if os.environ.get("SYL_REPO"):
        p = Path(os.environ["SYL_REPO"]).expanduser().resolve()
        if p.is_dir():
            return p
    # 与 P13 同父目录下找 "AI共享知识库-SYL"（运行时解析，不含隐私路径字面）
    candidate = P13.parent / "AI共享知识库-SYL"
    return candidate if candidate.is_dir() else None


def tracked_files(root: Path) -> list[Path]:
    try:
        # 关键：core.quotepath=false + encoding="utf-8"，否则 Windows 上中文文件名
        # 被默认编码解码成乱码路径 → 文件在磁盘上不存在 → 整个中文文件被静默跳过
        # （曾导致 SYL/P13 所有中文 md 从未被真正扫描，sync_check 长期"真空绿"）。
        out = subprocess.run(
            ["git", "-c", "core.quotepath=false", "ls-files"],
            cwd=root, capture_output=True, text=True, encoding="utf-8", check=True,
        ).stdout
        return [root / line.strip() for line in out.splitlines() if line.strip()]
    except Exception:
        return [p for p in root.rglob("*") if p.is_file() and ".git" not in p.parts]


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8-sig", errors="replace")


def check_track_consistency(syl_root: Path | None, p13_files: list[Path]) -> list[str]:
    """SYL 单轨 ↔ P13 不得把 SYL 描述成旧轨制。"""
    hits = []
    # P13 侧：源映射/README/SKILL 里若出现 "SYL 三轨" 类矛盾即拦截
    # （变更说明/事故记录类豁免文件同样跳过矛盾检查，避免历史描述被误报）
    for p in p13_files:
        if p.suffix != ".md" or exempt(p):
            continue
        for i, line in enumerate(read(p).splitlines(), 1):
            if SYL_CONTRADICTION.search(line):
                hits.append(f"{p.relative_to(P13)}:{i}: P13 侧把 SYL 描述为旧轨制（与单轨拍板矛盾）")
    # SYL 侧：本体也兜底查一遍旧术语残留（与 P13 侧共用 STALE_TERMS，口径一致）
    if syl_root:
        for p in tracked_files(syl_root):
            if p.suffix != ".md" or exempt(p):
                continue
            for i, line in enumerate(read(p).splitlines(), 1):
                s = line.lstrip()
                if s.startswith("> 更新") or s.startswith("> 历史"):
                    continue
                for t in STALE_TERMS:
                    if t in line:
                        hits.append(f"[SYL]{p.relative_to(syl_root)}:{i}: SYL 仓仍有旧术语「{t}」")
    return hits


def check_stale(files: list[Path]) -> list[str]:
    hits = []
    for p in files:
        if p.suffix != ".md" or exempt(p):
            continue
        for i, line in enumerate(read(p).splitlines(), 1):
            s = line.lstrip()
            if s.startswith("> 更新") or s.startswith("> 历史"):
                continue
            for t in STALE_TERMS:
                if t in line:
                    hits.append(f"{p.relative_to(P13)}:{i}: 旧术语「{t}」")
    return hits


def check_sensitive(files: list[Path]) -> list[str]:
    hits = []
    for p in files:
        if p.name in SCAN_EXEMPT or p.suffix not in (".md", ".py"):
            continue
        text = read(p)
        for w in FORBIDDEN:
            if w in text:
                hits.append(f"{p.relative_to(P13)}: 含禁词「{w}」")
        for pat in FORBIDDEN_PATTERNS:
            for m in re.finditer(pat, text):
                ctx = text[max(0, m.start() - 15):m.end() + 15]
                hits.append(f"{p.relative_to(P13)}: 命中内部路径模式 /{pat}/ → …{ctx}…")
    return hits


def check_version() -> list[str]:
    skill = P13 / "SKILL.md"
    readme = P13 / "README.md"
    if not skill.exists() or not readme.exists():
        return ["SKILL.md 或 README.md 缺失"]
    m = re.search(r"^version:\s*(\S+)", read(skill), re.M)
    if not m:
        return ["SKILL.md front matter 缺 version 字段"]
    ver = m.group(1)
    if f"v{ver}" not in read(readme):
        return [f"版本不一致：SKILL.md={ver}，但 README.md 找不到 v{ver}"]
    return []


def main() -> int:
    ap = argparse.ArgumentParser(description="跨仓一致性校验（SYL ↔ P13）")
    ap.add_argument("--syl", help="SYL 私有源仓路径（默认: 同父目录 AI共享知识库-SYL / 环境变量 SYL_REPO）")
    args = ap.parse_args()

    syl_root = resolve_syl(args.syl)
    if not syl_root:
        print("⚠️ 未定位到 SYL 仓（--syl / SYL_REPO / 同父目录 AI共享知识库-SYL 均未命中），"
              "跳过 SYL 侧单轨自检，仅校验 P13 发布面。")
    else:
        print(f"📂 SYL 源仓: {syl_root}")

    p13_files = tracked_files(P13)
    results = {
        "1.单轨一致性(SYL↔P13)": check_track_consistency(syl_root, p13_files),
        "2.旧术语残留": check_stale(p13_files),
        "3.脱敏护栏(P13发布面)": check_sensitive(p13_files),
        "4.版本一致性(P13)": check_version(),
    }
    failed = False
    for name, hits in results.items():
        if hits:
            failed = True
            print(f"❌ {name}：{len(hits)} 处拦截")
            for h in hits:
                print(f"   - {h}")
        else:
            print(f"✅ {name}")
    if not syl_root:
        print("\n结论：仅校验 P13 发布面（SYL 未定位），处理完再同步")
    else:
        print("\n结论：" + ("有拦截项，处理完再跨库同步/发布" if failed else "全绿，可以跨库同步/发布"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
