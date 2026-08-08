<p align="center">
  <h1 align="center">🤖 AI 共享知识库模板</h1>
  <p align="center">
    <strong>一套 MD 规范，让所有 AI 用同一份脑子干活</strong>
  </p>
  <p align="center">
    豆包 / Kimi / DeepSeek / ChatGPT / Claude / OpenClaw 全平台通用
    <br />
    告别每次换 AI 都要重新自我介绍、重新讲规则
  </p>
</p>

<p align="center">
  <img src="https://img.shields.io/github/license/SamieSYL2093/ai-knowledge-base-template?style=flat-square" alt="License">
  <img src="https://img.shields.io/github/stars/SamieSYL2093/ai-knowledge-base-template?style=flat-square" alt="Stars">
  <img src="https://img.shields.io/github/forks/SamieSYL2093/ai-knowledge-base-template?style=flat-square" alt="Forks">
  <img src="https://img.shields.io/badge/Markdown-✓-blue?style=flat-square" alt="Markdown">
  <img src="https://img.shields.io/badge/AI%20Platforms-All-brightgreen?style=flat-square" alt="AI Platforms">
</p>

---

## 为什么需要这个

大多数人的 AI 使用还停在这一步：打开对话框、问一句、关掉——**对话是散的，文件夹是散的，项目是散的**。

于是换个 AI 要重新自我介绍；刚调教好的格式换个平台就跑偏；项目一多，连文件在哪都要翻半天。

这个模板做的事，说起来就三步：

1. **先整理** —— 把散落的文件夹和项目归拢：知识库一个目录，项目们和它平行放（"项目"泛指一切用 AI 辅助干活的事：软件开发、课件教材、数据分析、资料整理……）
2. **让 AI 建 Git** —— 你不用会 Git，AI 自己会。从此每个改动自动留痕、可回滚
3. **多 AI 多项目推进** —— 所有 AI 读同一份档案、守同一套规矩、改完署名 commit。你可以同时指挥几个 AI 在几个项目上干活，像管一个小团队

<img src="p13-overview.svg" alt="知识库文件夹放哪：和你的项目们平行" width="720">

## 人只需要两步

1. **把仓库丢给你的 AI，让它读 README 入职** —— 用能读写本地文件的桌面端 AI（豆包桌面端 / Kimi / WorkBuddy / OpenClaw 等），把仓库路径给它，说一句"读 README，以后按这套规矩干活"。整理文件夹、建 Git、填档案，都是 AI 干，你只核对
2. **问它一句："我的档案里写了什么规矩？"** —— 答得上来，入职成功。答不上来，让它再读一遍

> 之后日常就一个循环：**人指派 → AI 干活 → `git commit` 署名留痕**。

---

> ✋ 到这一步就能用了。下面的内容给想深究的人和 AI 看，上手不用读。

---

## AI 入职（新 AI 第一次进来）

你是 AI，被主人指到这个仓库。照做：

1. **读档案** —— 读 `1-01_档案.md`，了解主人和规矩；基本信息过时就主动代填，给主人核对一眼
2. **签名登记** —— 在档案的签名登记表加一行你的名字（避免重名，同平台多个 AI 用"名字+平台"区分）→ 署名 commit（如 `[豆包桌面端] 入职登记`）

> 之后遵守档案里的基本原则干活。MD 文件是给你看的；人只看 `指挥中心.html`（由 `指挥中心.md` 跑 `python gen_html.py` 生成）——人改了 MD 里的内容，记得重新生成。

## 主要功能

1. **信息共享 · 避免重复投喂** —— 个人/团队信息、档案、规矩一次写入，所有 AI 共用同一份，换 AI 不用重新自我介绍、重新讲规则
2. **团队协作管理** —— 多 AI 分工干活，各签各的名，谁干了什么一目了然
3. **多项目文件夹管理** —— 所有项目位置与状态统一登记，多 AI、多子项目也不乱
4. **精益式项目管理** —— 融入精益思维：skill 化、简化、防呆、自动化、持续迭代、学习成长

## 文件导览

| 文件 | 干什么 | 人要碰吗 |
|------|--------|---------|
| `1-01_档案.md` | 你的身份 + 基本原则 + AI 签名登记表（唯一档案） | 不碰，AI 代填你核对 |
| `3-01_项目清单.md` | 所有项目在哪、什么状态，找项目先看这张表 | 不碰，AI 维护 |
| `3-02_技能清单.md` | 各平台装过什么 skill，统一登记 | 不碰，AI 维护 |
| `指挥中心.md` + `gen_html.py` | 人看的唯一入口：跑脚本生成 `指挥中心.html`，浏览器设书签 | 只看 HTML |

> 知识库只存"地图"（规范 + 登记），项目内容（"行李"）在各项目目录自治。
> 想加自己的业务规范（SOP、模板、行业知识）？按 `2-xx_规范名.md` 加文件即可，没有编号焦虑。

## 常见问题

**Q：我不会用 Git 能用吗？**
A：完全不用你学。Git 是 AI 帮你做版本管理的工具——你只管指派，建库、提交、回滚都是 AI 干。

**Q：我需要打开那些 MD 文件改东西吗？**
A：不需要。MD 文件是给 AI 看的，连档案都是聊着天 AI 就帮你填好了。你唯一常看的只有 `指挥中心.html`。

**Q：我只有网页版 AI 能用吗？**
A：**不行。** 这套体系假设 AI 能读写你本地文件——读档案、改清单、生成仪表盘、Git 提交都依赖这个能力。请用桌面端 AI（豆包桌面端 / Kimi / WorkBuddy / OpenClaw 等）。

**Q：我已经有自己的文件结构了怎么办？**
A：模板只是参考。目录结构随你改，只要守住档案里的几条基本原则就行。

**Q：可以商用吗？**
A：完全可以，MIT 协议，随便用、随便改，保留原作者署名即可。

## 版本与升级

模板持续进化，你的内容永远是你的——clone 之后档案、清单、业务内容全是本地文件，模板升级撞不上。

每次发版的改动清单见 [CHANGELOG.md](./CHANGELOG.md)。想升级，把 CHANGELOG 发给你的 AI，说一句"按清单把改进抄进我的知识库，我的本地内容别动"，它会自己对比、替换、提交。

## License

MIT License © 2026。随便用、随便改，保留署名即可。

---

<p align="center">
  如果这个模板帮你省了时间，欢迎点个 ⭐ Star 支持一下！
</p>
