# AI 开工须知

- 完工必须署名 commit：`git commit -m "[AI名字] 简述改动"`，签名取自本仓 `1-01_档案.md` 签名登记表（未登记的新 AI 先在表末加行）
- 项目状态或进展有变化时，同步更新本仓 `3-01_项目清单.md` 对应行并署名 commit
- 基本原则见 `1-01_档案.md`；人只看 `指挥中心.html`（改 MD 后跑 `python gen_html.py` 重新生成）
- **提交双闸（新 clone 后装一次）**：`copy hooks\pre-commit .git\hooks\` —— 闸①暂存文件 UTF-8 防呆（防 GBK 不可逆腐蚀）、闸② lint.py 机检 R1-R7（只报不修，有错即拦）；确要强行提交 `--no-verify`（留人为决策痕迹）
- **六维自评**：`python scripts/kb_audit.py .` 跑六维体检（总分取短板），README 首屏展示当前分数
