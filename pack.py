# -*- coding: utf-8 -*-
"""pack.py — AI共享知识库 打包工具

把指定的规范文件合并成一份"粘贴包"，自动复制到剪贴板，
方便投喂给豆包网页版 / Kimi 网页版等只能粘贴的平台。

用法：
    python pack.py 1-01 1-02 1-05      按编号合并 1-01、1-02、1-05 三个文件
    python pack.py 1-01 1-03 README    也支持 README / PLATFORMS
    python pack.py 1-01 1-02 --no-clip 只生成文件，不复制剪贴板
    python pack.py                     不带参数 = 列出所有可选编号
"""
import datetime
import glob
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(ROOT, "_打包")


def available_files():
    """返回 [(编号, 文件名, 完整路径), ...]，按编号排序。"""
    items = []
    for path in sorted(glob.glob(os.path.join(ROOT, "*.md"))):
        name = os.path.basename(path)
        code = name.split("_")[0] if "_" in name else name[:-3]
        items.append((code, name, path))
    return items


def find_file(code, items):
    code = code.upper()
    for c, name, path in items:
        if c.upper() == code or name.upper().startswith(code):
            return name, path
    return None, None


def copy_to_clipboard(text):
    """用 clip.exe 以 UTF-16 写入剪贴板，中文不乱码。"""
    try:
        subprocess.run("clip", input=text.encode("utf-16-le"), check=True)
        return True
    except Exception:
        return False


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    no_clip = "--no-clip" in sys.argv
    items = available_files()

    if not args:
        print("可选文件编号：")
        for code, name, _ in items:
            print(f"  {code:<10} {name}")
        print("\n用法: python pack.py 1-01 1-02 1-05 [--no-clip]")
        return

    parts, missing = [], []
    for code in args:
        name, path = find_file(code, items)
        if path is None:
            missing.append(code)
            continue
        with open(path, encoding="utf-8") as f:
            parts.append((name, f.read()))

    if missing:
        print(f"⚠️ 未找到编号: {', '.join(missing)}")
    if not parts:
        print("没有可打包的文件。")
        return

    today = datetime.date.today().isoformat()
    header = (
        f"# 共享规范包（{today}）\n\n"
        f"> 以下是我的共享知识库规范，请严格遵守。共 {len(parts)} 份："
        + "、".join(n for n, _ in parts)
        + "\n\n---\n\n"
    )
    body = "\n\n---\n\n".join(content for _, content in parts)
    bundle = header + body

    os.makedirs(OUT_DIR, exist_ok=True)
    out_name = f"pack_{today}_{'-'.join(a.upper() for a in args if a.upper() in [c.upper() for c, _, _ in items])}.md"
    out_path = os.path.join(OUT_DIR, out_name)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(bundle)

    print(f"✅ 已合并 {len(parts)} 个文件，共 {len(bundle)} 字符")
    print(f"📄 输出: {out_path}")

    if not no_clip:
        if copy_to_clipboard(bundle):
            print("📋 已复制到剪贴板，打开豆包/Kimi 直接 Ctrl+V")
        else:
            print("⚠️ 剪贴板复制失败，请手动打开上面的文件复制")


if __name__ == "__main__":
    main()
