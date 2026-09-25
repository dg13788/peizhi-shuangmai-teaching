# 发布检查清单（Release Checklist · 双轨制）

> 本文件为**发布唯一逐项检查清单**（依据 SKILL.md §6 维护），覆盖两条轨道：
> **GitHub 仓库轨**（治理文件齐全、版本同步）与**技能平台上传轨**（豆包/千问/WorkBuddy，zip 合规）。
> 每次发布（含主版本与修订版本）前逐项打钩执行；任一 ☐ 未通过不得发布。
> 完成后将"发布执行记录"追加至本文件末尾（版本 / 日期 / 执行人 / 逐项结果）。

## 一、GitHub 仓库轨

- [ ] 治理文件齐全且与当前版本一致：`README.md`（标题含当前版本）、`CHANGELOG.md`（含当前版本条目）、`CONTRIBUTING.md`、`LICENSE`、`.gitignore`
- [ ] README 含"红区零输入"隐私与安全说明（位置醒目）、外部方法论致谢、双环境安装方式（zip 上传 / 提示词复制）
- [ ] LICENSE 附加条款：红区护栏不可移除（最高优先）/ 衍生保留署名（Xd_香墩）/ 商业用途须书面授权（或文档模板部分 CC BY-NC-SA 替代）/ 隐私责任边界与疗效免责
- [ ] `git status` 复核实跑产物（锚定单/内容提取卡/Word/PDF/dist）未入暂存区；提交历史无真实学生信息
- [ ] 职务作品书面确认：作者确认非职务作品 / 已获单位授权（留存书面确认）

## 二、技能平台上传轨（AgentKit/豆包/千问 校验口径）

- [ ] 已用 `python scripts/build_package.py` 产出 `dist/peizhi-shuangmai-teaching.zip`（**禁止手工拼装**；打包器已强制 frontmatter 必检＋入包全文红区扫描，失败即拒绝出包）
- [ ] zip 顶层为技能名目录 `peizhi-shuangmai-teaching/`，目录内根路径存在 `SKILL.md`
- [ ] 包内仅含：`SKILL.md`、`scripts/`（四脚本）、`references/`（契约/格式基线/清单/LICENSE.md）、`examples/`（md＋JSON）
- [ ] 包内**无**：README/CHANGELOG/CONTRIBUTING/.gitignore、`.git/.workbuddy/dist`、`*_report.txt`、`*.docx/*.pdf`、锚定单/内容提取卡等会话产物
- [ ] frontmatter 合规：必填 `name`（小写+连字符、≤64、不含 agentkit）＋ `description`（≤1024 字符、无 XML 标签）；`version` 为 SemVer 三段；顶层字段不超出白名单（license/compatibility/metadata/allowed-tools）
- [ ] SKILL.md 行数 ≤500（渐进式披露，长内容拆 references/）

## 三、全库隐私扫描（红区零输入）

- [ ] 全库无真实学生姓名（仅允许代号"生1/生2…"或占位符 `{{字段名}}`）
- [ ] 全库无学生照片 / 人脸图片 / 含学生影像的媒体文件
- [ ] 全库无病历 / 身份证号 / 手机号 / 长数字串（正则扫描：身份证 17+ 位、手机号 11 位、任意 ≥11 位连续数字）
- [ ] 扫描记录留存（工具输出 / 本文件"发布执行记录"注明扫描方式与结论）

## 四、版本一致性与回归最小集（发布前必跑）

- [ ] 版本号六处一致：SKILL.md frontmatter `version` / 正文标题 `Vx.y.z` / `references/output-schema.json` 的 `schema_version const` / `scripts/md_to_json.py` 与 `scripts/md_to_docx.py` 的 `ENGINE_VERSION` / `CHANGELOG.md` 当前条目；示例 JSON `schema_version` 随派生同步
- [ ] 示例教案实跑：多课时（2~3 课时）各 1 篇，产出一致（每课时五列表〔BOPPPS 步别、≥1 探究活动、时间合计=该课时时长〕、分课时目标矩阵、LOS 表逐课时成对列且全生覆盖）
- [ ] **跨课时行为干预**：支持卡六要素齐全、强化计划逐课时削弱（连续→FR2→变动＋社会性）、晋级降级阈值含 80% 判据、危机处置四条红线（禁体罚、禁惩罚性隔离、禁强制进食、禁当众批评）；出现 N 的学生不计学业判据
- [ ] **无障碍基线**：字号下限（正文≥12pt、表格≥9pt、图卡标签≥24pt、关键句≥36pt）、对比度 ≥7:1 且不低于 4.5:1、色彩不得仅依赖颜色区分、学生可视材料用黑体无衬线
- [ ] **Single Source 派生**：改动教案后已重跑 `python scripts/md_to_json.py`，且回归中"落盘样例≡派生结果"PASS（禁止手工编辑 JSON）
- [ ] **结构化输出契约**：`examples/*结构化输出样例.json` 合 `references/output-schema.json`（`anchors` 每条三级齐全），且 `schema_version` 与 SKILL.md `version` 一致
- [ ] **Word 成品**：已用 `python scripts/md_to_docx.py <成品目录>` 生成（禁手工排版），`--check` 判定成品≡源稿且字节幂等；结构校验全过（封面独立节无页码、页脚 PAGE/SECTIONPAGES、A4 与页边距、表头跨页重复、列宽合计=版心、五列表列宽比、占位符保留、零引擎元信息、红区干净）；`--pdf` 三通道皆无时已给出降级指引
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
| 回归测试最小集③ Word+PDF 双格式 | ☐ 需实跑环境 | 上架前在文件系统环境实跑 1 次并过 §4 核验 |
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
