#!/usr/bin/env python3
"""
指挥中心 HTML 生成器（通用版 · 单向渲染 · 整条重新生成）

适用：本模板仓（ai-knowledge-base-template）的使用者。
做法：
  1. 把 指挥中心.md 里的【】占位符换成你的内容（可让 AI 代劳）
  2. （可选）在 1-01_档案.md 加一节「## 我的 AI 工具」表格，会自动带进 HTML
  3. 跑本脚本：python gen_html.py → 生成 指挥中心.html（与脚本同目录，可在浏览器设书签）
严禁手改 HTML——手改内容会被下次生成覆盖。
"""
import re, shutil, sys
from pathlib import Path
from datetime import datetime

KB = Path(__file__).parent
MD_FILE = KB / "指挥中心.md"
# HTML 输出到知识库根目录（与 gen_html.py、指挥中心.md 同级）——这是你的总入口，在库里随手可开
# 唯一事实来源仍是 指挥中心.md；HTML 是可重新生成的投影，不进 git（见 .gitignore）
HTML_FILE = KB / "指挥中心.html"
PROFILE_FILE = KB / "1-01_档案.md"

def extract_matrix():
    """从 1-01 档案提取「我的 AI 工具」一节的表格行（无此节则跳过）。
    矩阵唯一维护点在 1-01，这里只是读取投影到 HTML，不复制维护。"""
    if not PROFILE_FILE.exists():
        return ""
    lines = PROFILE_FILE.read_text(encoding="utf-8").split("\n")
    out, grab = [], False
    for ln in lines:
        if ln.startswith("## "):
            grab = ln.startswith("## 我的 AI 工具")
            continue
        if grab and ln.strip().startswith("|"):
            out.append(ln.rstrip())
    return "\n".join(out)

def check_scores(md):
    """积分榜对账（仅当 MD 含「### 当前总分」时启用，避免无此小节时误报）。
    明细行(+N)按AI加总 vs 「当前总分」表逐格比对；明细是事实源，不一致说明手维护出错。"""
    if "### 当前总分" not in md:
        return []
    detail = {}
    for m in re.finditer(r'^\|\s*20\d\d-\d\d-\d\d\s*\|[^|]+\|([^|]+)\|\s*\+(\d+)\s*\|', md, re.M):
        ai = m.group(1).strip()
        detail[ai] = detail.get(ai, 0) + int(m.group(2))
    sec = md.split('### 当前总分')[-1]
    total = {}
    for m in re.finditer(r'^\|\s*([^|]+?)\s*\|\s*(\d+)\s*\|\s*$', sec, re.M):
        name = m.group(1).strip()
        if name and name != 'AI':
            total[name] = int(m.group(2))
    errors = []
    for ai, v in detail.items():
        if total.get(ai) != v:
            errors.append(f'{ai}: 明细合计 {v} vs 总分表 {total.get(ai, "缺行")}')
    for ai, v in total.items():
        if ai not in detail and v != 0:
            errors.append(f'{ai}: 总分表 {v} 但明细无记录')
    return errors

# ---------- 行内格式 ----------
def inline(text):
    t = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    t = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" target="_blank">\1</a>', t)
    t = re.sub(r'`([^`]+)`', r'<code>\1</code>', t)
    t = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', t)
    return t

# ---------- 块级解析 ----------
def render(md):
    lines = md.split("\n")
    out, i = [], 0
    while i < len(lines):
        line = lines[i]
        s = line.strip()

        # 表格
        if s.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(lines[i].strip())
                i += 1
            cells = [[c.strip() for c in r.strip("|").split("|")] for r in rows]
            header, body = cells[0], [c for c in cells[1:] if not all(set(x) <= set(":- ") for x in c)]
            h = "".join(f"<th>{inline(c)}</th>" for c in header)
            body_html = "".join(
                "<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in body)
            out.append(f'<div class="tbl"><table><thead><tr>{h}</tr></thead><tbody>{body_html}</tbody></table></div>')
            continue

        # 标题
        m = re.match(r'(#{1,3})\s+(.*)', s)
        if m:
            level, text = len(m.group(1)), m.group(2)
            if level == 1:
                out.append(f'<h1>{inline(text)}</h1>')
            else:
                out.append(f'<h{level}>{inline(text)}</h{level}>')
            i += 1
            continue

        # 分割线
        if s == "---":
            i += 1
            continue

        # 引用块
        if s.startswith(">"):
            buf = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip().lstrip(">").strip())
                i += 1
            out.append(f'<div class="note">{"<br>".join(inline(b) for b in buf if b)}</div>')
            continue

        # 有序列表
        if re.match(r'^\d+\.\s', s):
            items = []
            while i < len(lines) and re.match(r'^\d+\.\s', lines[i].strip()):
                items.append(re.sub(r'^\d+\.\s', '', lines[i].strip()))
                i += 1
            lis = "".join(f"<li>{inline(x)}</li>" for x in items)
            out.append(f"<ol>{lis}</ol>")
            continue

        # 无序列表
        if s.startswith("- "):
            items = []
            while i < len(lines) and lines[i].strip().startswith("- "):
                items.append(lines[i].strip()[2:])
                i += 1
            lis = "".join(f"<li>{inline(x)}</li>" for x in items)
            out.append(f"<ul>{lis}</ul>")
            continue

        # 空行 / 段落
        if s:
            out.append(f"<p>{inline(s)}</p>")
        i += 1
    return "\n".join(out)

# ---------- 按 ## 分节包可折叠卡片 ----------
def to_cards(body):
    parts = re.split(r'(?=<h2>)', body)
    result = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if part.startswith("<h1>") or part.startswith("<div class=\"note\">"):
            result.append(part)  # 页头和说明不包卡片
        else:
            h2_match = re.match(r'(<h2>.*?</h2>)(.*)', part, re.DOTALL)
            if h2_match:
                title = h2_match.group(1)
                content = h2_match.group(2).strip()
                # 默认折叠（打开都是折叠的，要看哪块点哪块）
                # 例外：口令速查是"给人看的首屏"，默认展开
                open_attr = " open" if "口令速查" in title else ""
                result.append(f'<details class="card"{open_attr}><summary>{title}</summary><div class="card-content">{content}</div></details>')
            else:
                result.append(f'<div class="card">{part}</div>')
    return "\n".join(result)

CSS = """
body{background:#1a1a2e;color:#e0e0e0;font-family:'Microsoft YaHei',sans-serif;
max-width:920px;margin:0 auto;padding:24px 16px;font-size:17px;line-height:1.75;}
h1{font-size:26px;color:#fff;border-bottom:2px solid #ff6b81;padding-bottom:10px;}
h2{font-size:20px;color:#70a1ff;margin:0;padding:0;border:none;display:inline-block;}
h3{font-size:17px;color:#ffa502;}
.card{background:#24243e;border-radius:12px;padding:0;margin:16px 0;
box-shadow:0 2px 8px rgba(0,0,0,.3);overflow:hidden;}
details.card summary{list-style:none;cursor:pointer;padding:18px 22px;user-select:none;
display:flex;align-items:center;gap:10px;}
details.card summary::-webkit-details-marker{display:none;}
details.card summary::before{content:"▶";color:#70a1ff;font-size:12px;transition:transform 0.2s;}
details.card[open] summary::before{transform:rotate(90deg);}
.card-content{padding:0 22px 18px 22px;}
.tbl{overflow-x:auto;}
table{border-collapse:collapse;width:100%;font-size:15px;}
th{background:#2f2f4a;color:#70a1ff;padding:8px 10px;text-align:left;}
td{padding:8px 10px;border-bottom:1px solid #333;vertical-align:top;}
tr:hover td{background:#2a2a44;}
a{color:#70a1ff;text-decoration:none;}
a:hover{color:#90b8ff;text-decoration:underline;}
code{background:#2a2a2a;color:#7bed9f;padding:2px 6px;border-radius:4px;font-size:14px;}
strong{color:#fff;}
.note{background:#2a2a2a;border-left:3px solid #ffa502;padding:10px 14px;
border-radius:0 8px 8px 0;color:#aaa;font-size:14px;margin:10px 0;}
ol,ul{padding-left:24px;} li{margin:6px 0;}
.footer{margin-top:24px;padding:14px 18px;background:#24243e;border-radius:12px;
color:#888;font-size:14px;line-height:1.8;}
.stamp{color:#666;font-size:13px;margin-top:6px;}
"""

def main():
    check_only = "--check" in sys.argv
    if not MD_FILE.exists():
        print(f"❌ 找不到 {MD_FILE.name}：请先填写仓库自带的 指挥中心.md（【】占位符换成你的内容）")
        sys.exit(1)
    md = MD_FILE.read_text(encoding="utf-8")

    # 自动带入 1-01 档案的「我的 AI 工具」矩阵（投影展示，维护点仍在 1-01；无此节则跳过）
    matrix = extract_matrix()
    if matrix:
        md += ("\n## 🤖 已入职AI特性矩阵（自动带自 1-01 档案）\n"
               "> 本表由 gen_html.py 从 `1-01_档案.md` 自动带入展示——唯一维护点在 1-01，AI能力有变化请改那里，不要改这里。\n"
               + matrix + "\n")

    # MD 头部"更新时间"（日期+分钟，精确到分钟；模板未写则为未知）
    m = re.search(r'>\s*更新时间?：\s*([0-9]{4}-[0-9]{2}-[0-9]{2})(?:\s+([0-9]{2}:[0-9]{2}))?', md)
    md_date = (m.group(1) + (f" {m.group(2)}" if m and m.group(2) else "")) if m else "未知"

    body = to_cards(render(md))

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>指挥中心</title>
<!-- 本文件由 gen_html.py 从 指挥中心.md 自动生成，禁止手改（会被覆盖） -->
<style>{CSS}</style>
</head>
<body>
{body}
<div class="footer">
  🎯 这是<strong>你的专属指挥中心</strong>——你只看这一页就够了，但<strong>最好别看</strong>：直接问任何一个 AI，它都会答<br>
  🤖 本页由 AI 从 <code>指挥中心.md</code> 一键生成，AI 日常只改 MD<br>
  📁 真想自己翻，本页在 <code>gen_html.py</code> 同目录的 <code>指挥中心.html</code>，可在浏览器设书签；详细数据在知识库其他 MD（给 AI 看的）
  <div class="stamp">🕐 更新时间：{md_date} ｜ 本页生成：{datetime.now().strftime("%Y-%m-%d %H:%M")}</div>
</div>
</body>
</html>"""

    # 结构校验
    d_open = len(re.findall(r'<div\b', html))
    d_close = len(re.findall(r'</div>', html))
    if d_open != d_close:
        print(f"❌ div不平衡({d_open}/{d_close}) — 未写入！")
        sys.exit(1)
    # 积分榜账实对账（仅当含该小节时启用）
    score_errors = check_scores(md)
    if score_errors:
        print("❌ 积分榜账实不符 — 未写入！")
        for e in score_errors:
            print("  -", e)
        print("（明细行是事实源：修正总分表，或补/删明细行使之一致）")
        sys.exit(1)
    if check_only:
        print(f"✅ --check 干跑通过（div {d_open}/{d_close}）｜ 未写入HTML、未备份")
        return
    # 备份 + 写入
    if HTML_FILE.exists():
        bak = HTML_FILE.parent / (HTML_FILE.stem + ".html.bak")
        shutil.copy2(HTML_FILE, bak)
    HTML_FILE.write_text(html, encoding="utf-8")
    print(f"✅ HTML 已从 MD 重新生成（div {d_open}/{d_close}）｜ 备份: .html.bak")

if __name__ == "__main__":
    # Windows 中文控制台默认 GBK，打印 ✅ 等字符会炸——统一重配 UTF-8
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    main()
