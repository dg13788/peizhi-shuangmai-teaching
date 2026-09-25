# 培智·双脉教学引擎（特教 IEP 备课 Skill）V2.5.0

> 不拼通用、专精培智、沉淀方法论。

面向**培智学校（及同类特殊教育、个别化教学）各学科**的备课与教学设计 Skill。
以"**个别化 × 生活化**"双脉为主干、以 **BOPPPS** 为组织骨架、**趣味化参与式学习**为核心，
产出**可测、可按 LOS 六级分层、可迁移到真实生活**的教学方案，最终交付 **Word/PDF** 成品。
内置**红区隐私护栏**、**双 Gate 低打扰确认协议**、**跨课时行为干预递进（PBS）**、**无障碍排版基线**与 **4×3 知识类型策略路由**；机器可读产物遵循 `references/output-schema.json` 结构化契约。

## 核心特性

| 特性 | 说明 |
|---|---|
| 六环节引擎 | 双脉诊断 → 锚定目标 → 拆解生成 → 研判精修 → 课堂实施 → 复盘写库（另含 0.5 附件识别、3.5 格式交付两个辅助环节） |
| 双 Gate 低打扰 | Gate-A 授课内容理解（不确认不继续）＋ Gate-B 学情线索（具备即通过、不具备硬性停等）；其余环节低打扰推进 |
| 四视图一次生成 | 教师一页速览 / 教师全量 / 教务归档 / 家校反馈，同一数据源渲染、禁止冲突 |
| 双格式交付 | Word（.docx 可编辑）＋ PDF（.pdf 打印/归档），md 为唯一源稿（Single Source），§4 格式与无障碍基线统一核验 |
| 成品一键生成 | `python scripts/md_to_docx.py`：md → docx 的**唯一执行通道**（零第三方依赖、字节幂等、红区命中拒绝落盘），A4/页边距/字号行距/中西文字体/表头跨页重复/列宽比/封面独立节/页脚页码全部由代码强制；`--pdf` 自动尝试 Word COM → docx2pdf → LibreOffice，皆无则给出降级指引；`--check` 校验成品是否被改动或失同步 |
| 红区零输入护栏 | 学生姓名/身份证/病历/照片/家庭敏感结构零输入零输出，附件摄入前置红区检测 |
| 4×3 策略路由 | 知识类型（事实/概念/程序/元认知）× 学科属性（强逻辑/强叙事/强技能）动态装配生成策略，拒绝万能模板 |
| 1~N 课时模型 | 默认 1 课时 35′；每课时自成闭环（独立矩阵/五列表/前后测/作业/板书），跨课时"上一课后测＝下一课起点"，时间逐课时独立合计 |
| LOS 六级连续体 | 支持强度递增：独立(I) → 口头(V) → 手势(G) → 身体(P) → 完全辅助(F)；**无参与(N)** 不属强度序列，转优先参与目标与环境调整 |
| BOPPPS 分档 | 导入(B)/目标(O)/前测(P前)/参与式学习(P参)/后测(P后)/总结(S)；P参 ≥50% 且必须内嵌 ≥1 个学生可操作探究活动；**25′/35′/40′ 三档固化，禁临场换算** |
| 跨课时行为干预递进（PBS） | ABC 简录、替代行为须先教先练、逐课时强化削弱（连续→FR2→变动＋社会性）、80% 晋级/降级阈值、危机处置四条红线、全员一致的"行为支持卡" |
| 结构化输出契约 | 机器可读产物合 `references/output-schema.json`（JSON Schema draft 2020-12），支持**多锚点** anchors，含 timeline 步别枚举与时间恒等硬约束，可直接对接教务系统 |
| Single Source 派生 | 结构化 JSON **只可由 md 源稿经 `scripts/md_to_json.py` 派生**，禁止手工样例；回归自动比对"落盘样例≡派生结果"防漂移 |
| 无障碍排版基线 | 字号下限（正文12pt/表格9pt/图卡24pt/关键句36pt）、对比度 ≥7:1(AAA)、色彩必须多重编码、黑体无衬线与间距规范 |

## 快速开始

三种触发等价（任选其一，均默认 35 分钟 1 课时）：

```
① 纯课题驱动：请按培智·双脉教学引擎备一节培智二年级生活数学课，课题：5 的认识。
   班级：二年级（1）班。缺的基线你按合理默认补全并列出假设清单。
② 附件驱动：请按培智·双脉教学引擎备一节培智二年级生活数学课。已上传：教材页照片
   《5 的认识》＋课文文本，请先走环节 0.5 识别提取内容，再跑完整工作流。
③ 趣味化/BOPPPS：你是培智学校生活数学学科特级教师、资深教学设计专家。请按培智·双脉教学引擎
   设计一份趣味化教学方案：a.对象=培智二年级；b.内容=《6 的认识》；c.参考 BOPPPS 模型，
   并在"参与式学习"环节设计一个学生可操作的探究活动；d.逐步输出详细教学流程。
```

## 安装

| 环境 | 方式 |
|---|---|
| 技能平台上传（豆包 / 千问 / WorkBuddy 等） | 运行 `python scripts/build_package.py` 产出 `dist/peizhi-shuangmai-teaching.zip`，在平台"上传 Skill/技能"入口提交该 zip（顶层技能名目录、frontmatter 合 AgentKit 规范，治理文件与二进制成品已自动排除） |
| 支持 SKILL 目录的 Agent 平台 | 将本目录放入 skills 目录（如 `~/.marvis/skills/`）；front-matter 可被平台自动发现 |
| 无 SKILL 机制的平台（Kimi/ChatGPT 等） | 复制 `SKILL.md` 全文作"系统提示词/自定义指令"（front-matter 一并携带） |
| 有文件系统环境 | 建 `{{工作目录}}/` 存放锚定单、方法论库、附件、交付包 |

兼容性：豆包 / 千问 / DeepSeek / Kimi / ChatGPT / WorkBuddy 及任意支持长提示词、文件系统或附件上传的 AI 平台。无额外依赖。

## 仓库结构（双轨制：仓库＝GitHub 开发态，zip＝技能平台上传态）

```
peizhi-shuangmai-teaching/
├── SKILL.md                       # 引擎主体（唯一源稿，frontmatter 对齐 name/description 规范）
├── README.md                      # 本文件（GitHub 轨，不入上传包）
├── LICENSE                        # MIT + 红区护栏不可移除附加条款（打包时复制为包内 references/LICENSE.md）
├── CHANGELOG.md                   # 版本变更记录（GitHub 轨，不入上传包）
├── CONTRIBUTING.md                # 贡献指南（GitHub 轨，不入上传包）
├── scripts/
│   ├── md_to_json.py              # md 源稿 → 结构化 JSON 派生器（Single Source 唯一通道）
│   ├── md_to_docx.py              # md 源稿 → Word 成品生成器（唯一执行通道，零依赖/字节幂等）
│   ├── regression_check.py        # 回归校验脚本（教案/契约/引擎自身/派生/成品/双轨合规）
│   └── build_package.py           # 技能包打包器：仓库 → dist/*.zip（上传轨唯一出口）
├── references/
│   ├── output-schema.json         # 结构化输出契约（JSON Schema draft 2020-12）
│   ├── format-baseline.md         # 成品格式基线完整条文（SKILL.md §4 的展开）
│   └── release-checklist.md       # 发布逐项检查清单（GitHub＋技能平台双轨）
├── examples/
│   ├── 认识5_教学设计方案_2课时.md             # 多课时基准（生活数学）
│   ├── 好吃的水果_教学设计方案_3课时.md        # 多课时基准（生活语文）
│   ├── 认识5_结构化输出样例.json               # 结构化输出样例（由 md 派生）
│   └── 好吃的水果_结构化输出样例.json          # 结构化输出样例（由 md 派生）
├── dist/                          # 打包产物 *.zip（git 忽略，不上传仓库）
└── .gitignore                     # 排除交付成品、dist/、工作中间产物
```

> 运行期报告（`*_report.txt`）一律写系统临时目录 `peizhi_shuangmai/`，不进仓库与上传包；
> examples/ 不再入库 docx 成品（回归在临时目录做"成品≡源稿"端到端校验）。

## 隐私与安全（红区零输入）

- **红区**＝学生姓名、身份证、家庭敏感结构、病历、照片——**零输入零输出**（含 Word/PDF 成品与内容提取卡），学生一律代号"生1/生2…"。
- 上传附件（含学生照片、含姓名的作业/名单）**不得绕过护栏**；识别前先做红区检测，命中即不识别、不输出、提示脱敏重传。
- 本 Skill 为教学辅助工具，**不构成医疗/康复建议，不承诺疗效**。
- 详见 `SKILL.md` §0 铁律 1 与 LICENSE 附加条款。

## 致谢（外部方法论来源）

本 Skill 融合以下公开方法论与政策（理念借鉴，不含文献原文）：
- 《培智学校义务教育课程标准（2016年版）》（教育部）
- 《中小学生成式人工智能使用指南（2025年版）》（教育部）
- Wiggins & McTighe《Understanding by Design》（UbD 逆向设计三阶段）
- Mississippi 特殊教育 LOS 连续体（本 Skill 扩展为六级官方连续体）
- BOPPPS 教学模型（20 世纪 80 年代加拿大 ISW 工作坊）
- 正向行为支持（PBS）、各地培智"六个一""11211 小步子-多循环"等公开经验

## 许可证

[MIT License](LICENSE)，含不可移除附加条款：红区护栏不可移除、衍生须保留署名（Xd_香墩）、商业用途须书面授权（或文档/模板部分采用 CC BY-NC-SA 替代）。详见 [LICENSE](LICENSE)。

## 版本与兼容性

- 版本：2.5.0（2026-09-25 双轨合规整改：frontmatter 对齐 name/description 上传规范、scripts/references 标准布局、新增 build_package.py 打包器产出技能上传 zip、GitHub 治理文件保留、格式基线拆分 references/format-baseline.md；回归校验全项通过，以 `%TEMP%/peizhi_shuangmai/regression_report.txt` 末尾通过率为准），明细见 [CHANGELOG.md](CHANGELOG.md)。
- 回归校验：`python scripts/regression_check.py`，**发布前须 100% 通过**（项数随版本增长，以报告为准，不硬编码）。
- 结构化 JSON 派生：`python scripts/md_to_json.py`；**改教案请先改 md 再派生**，禁止手工编辑 JSON。
- Word 成品生成：`python scripts/md_to_docx.py <成品目录>`（加 `--pdf` 导出 PDF，加 `--check` 校验成品一致性）。顺序恒为：改 md → 派生 JSON → 生成 docx → 跑回归。
- 技能包打包：`python scripts/build_package.py` → `dist/peizhi-shuangmai-teaching.zip`（上传豆包/千问/WorkBuddy 的唯一出口，禁止手工拼装）。
- 主线"六环节＋双 Gate＋四视图＋双格式"各版本保持不变；2.0.0 起 SKILL.md 仅保留运行态引擎（治理内容外置）。
