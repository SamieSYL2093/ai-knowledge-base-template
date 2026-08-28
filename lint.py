#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lint.py — 知识库模板体检脚本

只报不修：输出可执行项清单，修复由 AI/人执行并署名 commit。
用法：
    python lint.py
（在本仓根目录跑；无 git 环境时自动跳过 git 相关检查）

规则一览：
  R1 核心文件齐全        1-01/3-01/3-02/指挥中心.md/gen_html.py 缺一不可
  R2 文件头三行说明      核心 MD 须有 > 用途 / > 关键词 / > 更新
  R3 签名表占位行        1-01 末尾须保留（新AI在此加行）
  R4 示例行残留          已有实际签名/项目，但表里还留着【示例：…】没删
  R5 敏感信息            MD 里出现绝对路径（如 D:\…）——对外发布前必看，防泄露
  R6 commit 消息泄露     git log 消息里含绝对路径
"""

import re
import subprocess
import sys
from pathlib import Path

# Windows 中文控制台默认 GBK，emoji 会炸——强制 UTF-8
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

KB = Path(__file__).parent
CORE_FILES = ["1-01_档案.md", "3-01_项目清单.md", "3-02_技能清单.md", "指挥中心.md", "gen_html.py"]
HEADER_FILES = ["1-01_档案.md", "3-01_项目清单.md", "3-02_技能清单.md", "指挥中心.md"]
ABS_PATH_RE = re.compile(r"(?<![/\w])[A-Za-z]:[/\\][^\s`），。；]+")
URL_RE = re.compile(r"https?://\S+")

errors, warns, infos = [], [], []


def read(name):
    p = KB / name
    return p.read_text(encoding="utf-8") if p.exists() else ""


def check():
    # R1 核心文件
    for f in CORE_FILES:
        if not (KB / f).exists():
            errors.append(f"R1 缺核心文件: {f}")

    # R2 文件头三行
    for f in HEADER_FILES:
        text = read(f)
        if not text:
            continue
        for kw in ("用途", "关键词", "更新"):
            if f"> {kw}" not in text.split("##")[0]:
                errors.append(f"R2 {f} 文件头缺「{kw}」行")

    # R3 签名占位行
    profile = read("1-01_档案.md")
    if profile and "（新AI在此加行）" not in profile:
        errors.append("R3 1-01 签名表末尾缺「（新AI在此加行）」占位行（新 AI 要知道往哪加）")

    # R4 示例行残留（判据：已有实际内容，示例行就该删）
    has_real_sign = bool(re.search(r"^\|\s*[^【|（][^|]*\|\s*[^【|（\s]", profile.split("AI 签名登记表")[-1], re.M))
    if has_real_sign and "示例：" in profile:
        warns.append("R4 1-01 已有实际签名但还留着【示例：…】行，可删")
    for f in ("3-01_项目清单.md", "3-02_技能清单.md"):
        t = read(f)
        rows = [ln for ln in t.split("\n") if ln.strip().startswith("|")]
        real = [ln for ln in rows if "P0" in ln or ln.startswith("| S0") or ("|" in ln and "示例" not in ln and not set(ln.strip("| ")) <= set("-: "))]
        if len(real) > 3 and "示例：" in t:  # 超过表头+分隔+占位
            warns.append(f"R4 {f} 已有实际登记但还留着示例行，可删")

    # R5 敏感信息（跳过 URL 和【示例行——示例里的假路径是故意的）
    for p in KB.glob("*.md"):
        if p.name == "CHANGELOG.md":
            continue  # 历史记录里改不了，只看现行文件
        for ln in p.read_text(encoding="utf-8", errors="ignore").split("\n"):
            if "示例" in ln:
                continue
            for m in ABS_PATH_RE.finditer(URL_RE.sub("", ln)):
                warns.append(f"R5 {p.name} 含绝对路径「{m.group(0)[:40]}」——对外发布/截图前注意脱敏")

    # R6 commit 消息泄露
    try:
        log = subprocess.run(["git", "log", "--pretty=%s", "-50"], cwd=KB,
                             capture_output=True, text=True, encoding="utf-8", errors="ignore").stdout
        for line in log.splitlines():
            if ABS_PATH_RE.search(line):
                errors.append(f"R6 commit 消息含绝对路径: {line[:60]}")
    except Exception:
        infos.append("R6 跳过（无 git 环境）")


def main():
    check()
    for e in errors:
        print("🔴", e)
    for w in warns:
        print("🟡", w)
    for i in infos:
        print("⚪", i)
    total = len(errors) + len(warns)
    if total == 0:
        print("✅ 体检通过，无发现")
    else:
        print(f"— 共 {total} 项（🔴 错误 {len(errors)} / 🟡 提醒 {len(warns)}）；修复后重跑本脚本确认，改完记得署名 commit")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
