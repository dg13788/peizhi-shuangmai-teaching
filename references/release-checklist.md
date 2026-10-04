# 发布检查清单（Release Checklist · 双轨制）

> 本文件为**发布唯一逐项检查清单**（依据 SKILL.md §6 维护），覆盖两条轨道：
> **GitHub 仓库轨**（治理文件齐全、版本同步）与**技能平台上传轨**（豆包/千问/WorkBuddy，zip 合规）。
> 每次发布（含主版本与修订版本）前逐项打钩执行；任一 ☐ 未通过不得发布。
> 完成后将"发布执行记录"追加至本文件末尾（版本 / 日期 / 执行人 / 逐项结果）。

## 一、GitHub 仓库轨

- [ ] 治理文件齐全且与当前版本一致：`README.md`（标题含当前版本）、`CHANGELOG.md`（含当前版本条目）、`CONTRIBUTING.md`、`LICENSE`、`.gitignore`
- [ ] README 含"红区零输入"隐私与安全说明（位置醒目）、外部方法论致谢、双环境安装方式（zip 上传 / 提示词复制）
- [ ] LICENSE 附加条款：红区护栏不可移除（最高优先）/ 衍生保留署名（Xd_香墩）/ 商业用途须书面授权（或文档模板部分 CC BY-NC-SA 替代）/ 隐私责任边界与疗效免责
- [ ] `git status` 复核实跑产物（锚定单/内容提取卡/Word 成品/dist）未入暂存区；提交历史无真实学生信息
- [ ] 职务作品书面确认：作者确认非职务作品 / 已获单位授权（留存书面确认）

## 二、技能平台上传轨（AgentKit/豆包/千问 校验口径）

- [ ] 已用 `python scripts/build_package.py` 产出 `dist/peizhi-shuangmai-teaching.zip`（**禁止手工拼装**；打包器已强制 frontmatter 必检＋入包全文红区扫描，失败即拒绝出包）
- [ ] zip 顶层为技能名目录 `peizhi-shuangmai-teaching/`，目录内根路径存在 `SKILL.md`
- [ ] 包内仅含：`SKILL.md`、`scripts/`（四脚本）、`references/`（契约/格式基线/清单/LICENSE.md）、`examples/`（md＋JSON）
- [ ] 包内**无**：README/CHANGELOG/CONTRIBUTING/.gitignore、`.git/.workbuddy/dist`、`*_report.txt`、`*.docx`、锚定单/内容提取卡等会话产物
- [ ] frontmatter 合规：必填 `name`（小写+连字符、≤64、不含 agentkit）＋ `description`（≤1024 字符、无 XML 标签）；`version` 为 SemVer 三段；顶层字段不超出白名单（license/compatibility/metadata/allowed-tools）
- [ ] SKILL.md 行数 ≤500（渐进式披露，长内容拆 references/）

## 三、全库隐私扫描（红区零输入）

- [ ] 全库无真实学生姓名（仅允许代号"生1/生2…"或占位符 `{{字段名}}`）
- [ ] 全库无学生照片 / 人脸图片 / 含学生影像的媒体文件
- [ ] 全库无病历 / 身份证号 / 手机号 / 长数字串（正则扫描：身份证 17+ 位、手机号 11 位、任意 ≥11 位连续数字）
- [ ] 扫描记录留存（工具输出 / 本文件"发布执行记录"注明扫描方式与结论）

## 四、版本一致性与回归最小集（发布前必跑）

- [ ] 版本号**八处一致**：① SKILL.md frontmatter `version` ② SKILL.md 正文标题 `Vx.y.z` ③ `references/output-schema.json` 的 `schema_version const` ④ `scripts/md_to_json.py` ⑤ `scripts/md_to_docx.py` ⑥ `scripts/build_package.py` 三处 `ENGINE_VERSION` ⑦ `CHANGELOG.md` 当前条目 ⑧ `README.md` 标题与"版本与兼容性"段；示例 JSON `schema_version` 随派生同步（回归自动校验，脚本版本以 SKILL.md frontmatter 为唯一真源，禁在脚本内硬编码）
- [ ] 示例教案实跑：多课时（2~3 课时）各 1 篇，产出一致（每课时五列表〔BOPPPS 步别、≥1 探究活动、时间合计=该课时时长〕、分课时目标矩阵、LOS 表逐课时成对列且全生覆盖）
- [ ] **跨课时行为干预**：支持卡六要素齐全、强化计划逐课时削弱（连续→FR2→变动＋社会性）、晋级降级阈值含 80% 判据、危机处置四条红线（禁体罚、禁惩罚性隔离、禁强制进食、禁当众批评）；出现 N 的学生不计学业判据
- [ ] **无障碍基线**：成品 Word 的版式（宋体小四 1.5 倍行距、表格≥9pt、A4 与页边距、表头跨页重复、页脚页码）由生成器固化，`--check` 抽检全 **SAME**；教师另制的可视材料规格已在 examples「配套件 · 学生可视材料规格」落位——图卡标签≥24pt、关键句≥36pt、低视力生18pt，对比度≥7:1 且不低于 4.5:1、色彩不得仅依赖颜色区分、黑体无衬线、线条≥1.5pt
- [ ] **Single Source 派生**：改动教案后已重跑 `python scripts/md_to_json.py`，且回归中"落盘样例≡派生结果"PASS（禁止手工编辑 JSON）
- [ ] **结构化输出契约**：`examples/*结构化输出样例.json` 合 `references/output-schema.json`（`anchors` 每条三级齐全），且 `schema_version` 与 SKILL.md `version` 一致
- [ ] **Word 成品**：已用 `python scripts/md_to_docx.py <成品目录>` 生成（禁手工排版），`--check` 判定成品≡源稿且字节幂等；结构校验全过（封面独立节无页码、**页脚仅 `PAGE` 字段、"第 X 页"**（3.4.0 起不再列总页数：多节文档下 `SECTIONPAGES` 按本节页数计、`NUMPAGES` 计入无页码封面，两者必失真）、A4 与页边距、表头跨页重复、列宽合计=版心、五列表列宽比、占位符保留、零引擎元信息、红区干净）；PDF 通道已移除（3.0.0 起仅交付 Word）
- [ ] `python scripts/regression_check.py` 全项 PASS（通过率达 100%，项数以报告为准），报告写系统临时目录 `peizhi_shuangmai/regression_report.txt`
- [ ] 引擎规则变更而示例未同步＝破坏性变更：已升大版本并回改 examples 基准

---

## 发布执行记录

### v1.0 · 2026-09-15 · 开源前准备

| 检查项 | 结果 | 备注 |
|---|---|---|
| 仓库结构与文件完整性 | ☑ 通过 | 已补齐开源配套文件；examples 含 2 篇教案 |
| LICENSE 附加条款 | ☑ 通过 | MIT＋护栏不可移除＋署名＋商业限制＋责任边界 |
| 全库隐私扫描 | ☑ 通过 | 正则扫描 0 命中；教案仅含"生1~生12"代号 |
| 合规确认 | ☐ 待作者确认 | 职务作品书面确认需作者本人签署 |
| 回归测试最小集① 示例实跑 | ☑ 通过 | 两份多课时基准结构齐全 |
| 回归测试最小集② 附件识别 | ☐ 需实跑环境 | 依赖平台附件上传/OCR 能力，上架前在目标平台实跑 1 次 |
| 回归测试最小集③ Word 成品 | ☐ 需实跑环境 | 上架前在文件系统环境实跑 1 次并过 §4 核验 |
| 回归测试最小集④ 全库红区扫描 | ☑ 通过 | 见上 |

> 说明：②③ 两项为运行态回归（依赖平台 OCR 与本地文档生成环境），正式发布前须在实跑环境补跑。

### v2.5.0 · 2026-09-25 · 双轨合规整改（技能上传规范 × GitHub）

| 检查项 | 结果 | 备注 |
|---|---|---|
| GitHub 仓库轨 | ☑ 通过 | 治理文件保留并同步 2.5.0；README 标题/CHANGELOG 条目回归自动校验 |
| 技能平台上传轨 | ☑ 通过 | `build_package.py` 产出 dist zip；顶层技能名目录；frontmatter 合规；治理文件/二进制/报告件均未入包 |
| 版本一致性 | ☑ 通过 | 2.5.0 六处一致，回归自动校验 |
| 回归最小集 | ☑ 通过 | `python scripts/regression_check.py` 全项 PASS，通过率以报告末尾为准 |
| 全库隐私扫描 | ☑ 通过 | 红区正则 0 命中；生成器与打包器双重红区拒绝落盘 |

### v2.6.0 · 2026-09-26 · 三层渐进式披露重构（路由层瘦身 × 细则层外置）

| 检查项 | 结果 | 备注 |
|---|---|---|
| 路由层瘦身 | ☑ 通过 | 主文件约 31KB → 约 10KB（-66%），行数 169 → 89；体积与行数由回归双封顶防回流膨胀 |
| 细则层完整 | ☑ 通过 | 新增 domain-core / workflow / strategy-matrix / state-and-fallback 四件，内容自原主文件原样外置 |
| 规则零丢失 | ☑ 通过 | 契约锚点（行为干预 / 无障碍基线）改为全库判定，外置后仍全部命中 |
| 无孤儿文件 | ☑ 通过 | references/ 七件均被主文件"读取索引"引用，回归自动校验 |
| 降级出口 | ☑ 通过 | 主文件写明"运行环境不能读取 references 时"的压缩版四视图回退，防纯对话平台细则丢失 |
| 打包不漏件 | ☑ 通过 | 打包器改目录级自动收集，新增细则无需改白名单即自动入包 |
| 版本一致性 | ☑ 通过 | 2.6.0 六处一致（当时落点数），回归自动校验 |
| 回归最小集 | ☑ 通过 | `python scripts/regression_check.py` 全项 PASS，通过率以报告末尾为准 |

### v3.7.0 · 2026-09-29 · 三视角极限回测修订 × 目录与版本核验

| 检查项 | 结果 | 备注 |
|---|---|---|
| GitHub 仓库轨 | ☑ 通过 | 治理文件 6 件齐全（README/CHANGELOG/CONTRIBUTING/LICENSE/.gitignore/SKILL.md）；README 标题含 3.7.0、CHANGELOG 含 `[3.7.0]` 且无版本倒挂 |
| 技能平台上传轨 | ☑ 通过 | `build_package.py` 重建 `dist/peizhi-shuangmai-teaching.zip`，17 条目、顶层唯一技能名目录、含 SKILL.md＋4 脚本＋8 references（7 细则＋注入 LICENSE.md）＋4 examples |
| 目录整洁 | ☑ 通过 | 根 6 治理文件＋`scripts/`4＋`references/`7＋`examples/`4；已清理 `scripts/__pycache__`；根目录与 examples/ 无 docx 残留；references/ 无孤儿文件 |
| 版本一致性 | ☑ 通过 | **八处一致** 3.7.0（frontmatter/正文标题/schema const/三脚本/CHANGELOG/README）＋两份示例 JSON 随派生同步；回归 6 条版本断言全 PASS |
| 回归最小集 | ☑ 通过 | `regression_check.py` 全项 PASS（项数随版本增长，以 `%TEMP%/peizhi_shuangmai/regression_report.txt` 末尾通过率为准）；`--check` 一致性 SAME 2/2 |
| 主文件封顶 | ☑ 通过 | SKILL.md 12235 字节 / 91 行（≤12KB 且 ≤150 行双封顶） |
| 全库隐私扫描 | ☑ 通过 | 红区正则 0 命中；生成器与打包器双重拒绝落盘；学生仅代号"生1~生12" |

### v3.8.0 · 2026-10-02 · 教学设计结构要素补齐

| 检查项 | 结果 | 备注 |
|---|---|---|
| 要素补录 | ☑ 通过 | 对照通用教学设计要素逐项核：新增**教材分析**（五要素，含"前后联系：已学→本课→为后续铺垫"）／**学情分析**（五要素，功能性描述、禁堆叠诊断标签）／**教学重难点**（一行式→重点/难点/突破策略三行）／**人力协同与分工**（教学资源的"人"） |
| 契约兼容 | ☑ 通过 | 新字段均以**嵌套**方式加入（`meta.教材分析`／`meta.学情分析`／`lessons[].重难点`／`support.人力协同`），**顶层 required 集合不变**（仍 12 项），SKILL.md §6 无需改动——这是守住主文件 ≤12KB 封顶的关键取舍 |
| 表号稳定性 | ☑ 通过 | 人力协同改用**项目符号**而非编号表，避开教学过程内"表15/表16"内嵌引用的错位风险（此坑已写入项目记忆） |
| 版本一致性 | ☑ 通过 | 八处一致 3.8.0；回归全项 PASS、`--check` SAME 2/2；包 17 条目 |

> 备注：3.0.0~3.6.0 因连续迭代未逐版登记执行记录，本条已在本次核验中一并复核（版本号历史条目与治理文件均同步）。
