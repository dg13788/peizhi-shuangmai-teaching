# -*- coding: utf-8 -*-
# -*- coding: utf-8 -*-
"""培智·双脉教学引擎 —— 全量回归校验（当前引擎版本见 SKILL.md front-matter）

用法：python scripts/regression_check.py      （发布前须 100% PASS）
校验分组：
  ① 教案基准 examples/*.md：BOPPPS 六步 / 每课时时间恒等 / 探究活动 / LOS 成对列 /
     表头行 / 表号章节号 / 占位符 / 红区 / 行为支持卡 / 感官调节 / IEP 累计追踪 / 无障碍说明
  ② 结构化契约 references/output-schema.json 与 examples/*结构化输出样例.json
  ③ 引擎自身 SKILL.md：frontmatter 合规（name/description/version 必填 + 规范白名单）/
     SemVer / 版号一致 / 五条铁律 / 外部引用存在性
  ④ md→JSON 派生一致性（Single Source，含"落盘样例 ≡ 派生结果"防漂移）
  ⑤ Word 成品 md→docx：OOXML 包完整性与元素序列 / 版式契约 / 字节幂等 / 外部读取复校
  ⑥ 交付通道契约：CLI 参数 / --check 反篡改（临时目录端到端）/ PDF 通道已移除（否定式断言）
  ⑦ 双轨合规与仓库卫生：技能标准布局（scripts/references/examples）/ 无二进制成品 /
     无运行期报告 / GitHub 治理文件保留且版本同步（README/CHANGELOG）/ 章节号 / 不硬编码项数
输出：%TEMP%/peizhi_shuangmai/regression_report.txt（UTF-8；报告不进仓库）
元断言：同一分节内重复计入的断言必须为 0（防止通过率虚高）
"""
import re
import os
import sys
import json
import glob
import hashlib
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEP = re.compile(r'^[\s\-:|]+$')

REPORT_DIR = os.path.join(tempfile.gettempdir(), 'peizhi_shuangmai')


def report_path(name):
    """运行期报告一律落系统临时目录（包内不产 *_report.txt）"""
    os.makedirs(REPORT_DIR, exist_ok=True)
    return os.path.join(REPORT_DIR, name)


def blocks(lines):
    """提取 markdown 表格块"""
    out, cur = [], []
    for l in lines:
        if l.strip().startswith('|'):
            cur.append(l.strip())
        else:
            if cur:
                out.append(cur)
                cur = []
    if cur:
        out.append(cur)
    return out


def is_sep(row):
    return bool(SEP.match(row.replace('|', '').strip()))


def cells(row):
    return [c.strip() for c in row.strip().strip('|').split('|')]


def check(path):
    name = os.path.basename(path)
    text = open(path, encoding='utf-8').read()
    lines = text.splitlines()
    r = []

    m = re.search(r'_(\d)课时', name)
    # 课时数变量特意命名为 n_less：本节后续约 300 行都依赖它，
    # 若用短名 n 极易被新增代码无意覆盖（3.6.0 曾因此让 N 变成指令句字数）
    n_less = int(m.group(1)) if m else 1
    r.append(('课时数N在合理范围(1~6)', 1 <= n_less <= 6, str(n_less)))

    # 1 封面两行标题相邻
    h1 = [i for i, l in enumerate(lines) if l.startswith('# ')]
    r.append(('封面两行标题相邻', len(h1) >= 2 and h1[1] == h1[0] + 1))

    # 2 表格均有表头行（首行非分隔行）
    bs = blocks(lines)
    nohead = [b[0] for b in bs if len(b) >= 2 and is_sep(b[0])]
    r.append(('表格均有表头行', not nohead, '' if not nohead else str(nohead[:2])))

    # 2b 表格内部禁重复分隔行
    dup = []
    for b in bs:
        for row in b[3:]:
            if is_sep(row):
                dup.append(row[:20])
    r.append(('表格内无重复分隔行', not dup, ','.join(dup[:2])))

    # 2c 表格首行不得是数据行（防"缺语义表头"：如分层作业首行写成"第1课时·A"）
    DATA_ROW = re.compile(r'^(第\d+课时|生\d+|\d+′)')
    badhead = [b[0] for b in bs if b and cells(b[0]) and DATA_ROW.match(cells(b[0])[0])]
    r.append(('表格首行非数据行(表头不缺失)', not badhead, str(badhead[:1])))

    # 3 BOPPPS 六步 + 4 时间合计 + 5 探究活动（按五列表逐个校验；表头严格匹配防偏移）
    steps_needed = {'B', 'O', 'P前', 'P参', 'P后', 'S'}
    offhead = [b for b in bs if b and '教学环节' in b[0] and cells(b[0]) and cells(b[0])[0] != '教学环节']
    r.append(('五列表表头严格为"教学环节"', not offhead, str(offhead[:1])))
    proc_tables = [b for b in bs if b and cells(b[0]) and cells(b[0])[0] == '教学环节']
    r.append(('五列表数量=课时数N', len(proc_tables) == n_less,
              '%d/%d' % (len(proc_tables), n_less)))
    for idx, b in enumerate(proc_tables, 1):
        steps, minutes, inquiry = set(), 0, False
        for row in b[2:]:
            c0 = cells(row)[0] if cells(row) else ''
            mm = re.search(r'（([^）·]+)·(\d+)′）', c0)
            if mm:
                steps.add(mm.group(1))
                minutes += int(mm.group(2))
            if '【探究活动】' in row:
                inquiry = True
        r.append(('第%d课时 BOPPPS 六步齐全' % idx, steps_needed <= steps, '缺 ' + str(steps_needed - steps) if not steps_needed <= steps else ''))
        r.append(('第%d课时 时间合计=35′' % idx, minutes == 35, str(minutes)))
        r.append(('第%d课时 含≥1探究活动' % idx, inquiry))
        # 3.6.0 五列表填写规格（列内密度，禁骨架化；加列会触发横向节故锁死列数）
        rows = b[2:]
        p_rows = [rw for rw in rows if cells(rw) and '（P参·' in cells(rw)[0]]
        r.append(('第%d课时 P参按子步骤分行(≥3行)' % idx, len(p_rows) >= 3,
                  '实%d行' % len(p_rows)))
        colbad = [rw for rw in rows if len(cells(rw)) != 5]
        r.append(('第%d课时 五列表列数恒为5(禁加第6列)' % idx, not colbad,
                  '实%d列' % len(cells(colbad[0])) if colbad else ''))
        nocmd = [rw for rw in rows if '指令范式句' not in rw]
        r.append(('第%d课时 每行教师活动含指令范式句' % idx, not nocmd,
                  '缺%d行' % len(nocmd) if nocmd else ''))
        VAGUE = ('认真听讲', '积极参与', '感受', '体会', '理解', '领悟', '欣赏')
        vag = [rw for rw in rows if len(cells(rw)) > 2
               and any(v in cells(rw)[2] for v in VAGUE)]
        r.append(('第%d课时 学生活动为可观察行为(禁内隐词)' % idx, not vag,
                  cells(vag[0])[2][:12] if vag else ''))
        nolos = [rw for rw in rows if len(cells(rw)) > 3
                 and not re.search(r'（[IVGPF/]+）', cells(rw)[3])]
        r.append(('第%d课时 支持策略落LOS层级代号' % idx, not nolos,
                  cells(nolos[0])[3][:12] if nolos else ''))
        noev = [rw for rw in rows if len(cells(rw)) > 4
                and '证据' not in cells(rw)[4]]
        r.append(('第%d课时 设计意图附证据闭环' % idx, not noev,
                  '缺%d行' % len(noev) if noev else ''))
        bad_cmd, empty_verb = [], []
        for rw in rows:
            c = cells(rw)
            if len(c) < 5:
                continue
            mc = re.search(r'指令范式句：\s*[“"]([^”"]+)[”"]', c[1])
            if mc:
                cmd_len = len(re.sub(r'[，。？！、…\s“”"]', '', mc.group(1)))
                if cmd_len > 12:
                    bad_cmd.append('%d字' % cmd_len)
            for v in ('引导学生', '帮助学生', '培养学生', '教育学'):
                if v in c[1]:
                    empty_verb.append(v)
        r.append(('第%d课时 指令范式句≤12字' % idx, not bad_cmd,
                  ','.join(bad_cmd[:2])))
        r.append(('第%d课时 教师活动禁无动作空话' % idx, not empty_verb,
                  ','.join(empty_verb[:2])))

    # 3.6.0 LOS 分层支持表含学情依据列（支持可溯源；列数仍须 <6 以免触发横向节）
    # 表名在**表题**行（不进表格块）→ 按表头特征定位：首列"层级"＋含"支持类型"
    losup = [b for b in bs if b and cells(b[0]) and cells(b[0])[0] == '层级'
             and '支持类型' in ''.join(cells(b[0]))]
    if losup:
        hd = cells(losup[0][0])
        r.append(('LOS分层支持表含学情依据列', '学情依据' in ''.join(hd), str(hd[:1])))
        r.append(('LOS分层支持表列数=5(不触发横向节)', len(hd) == 5, '实%d列' % len(hd)))
    else:
        r.append(('LOS分层支持表存在', False))

    # 6 LOS 记录表逐课时成对列：1 + 2N + 1
    los = [b for b in bs if b and '起始LOS' in b[0]]
    if los:
        cols = len(cells(los[0][0]))
        r.append(('LOS表逐课时成对列(1+2N+1=%d)' % (2 * n_less + 2),
                  cols == 2 * n_less + 2, '实%d列' % cols))
        rows = [c for c in los[0][2:] if cells(c)[0].startswith('生')]
        r.append(('LOS表全生覆盖(12人)', len(rows) == 12, '实%d人' % len(rows)))
    else:
        r.append(('LOS变化记录表存在', False))

    # 7 材料清单 ☐ 勾选
    seg = text.split('材料清单')[1][:600] if '材料清单' in text else ''
    r.append(('材料清单含☐勾选框', '☐' in seg))
    # 3.6.0：教学过程向学生发家长记录条 → 材料清单必须列，否则课前照单核对必然漏带
    if '家长记录条' in text:
        r.append(('发家长记录条→材料清单须列', '家长记录条' in seg))

    # ---- 3.10.0 家长记录条（勾勾表制式）：此前引擎只列物料、未定义版式 ----
    hn_m = re.search(r'^### 家长记录条.*?\n(.*?)(?=^### |^## |\Z)', text, re.M | re.S)
    r.append(('家长记录条小节存在(3.10.0勾勾表制式)', bool(hn_m)))
    if hn_m:
        body_hn = hn_m.group(1)
        # 档位必须取自 ☐ 行本身——用全文子串会被条首/对齐说明里的同名词兜住，
        # 导致"档位被删"仍能通过（3.9.0 宽松子串教训的同类复发，此处以结构位置锚定）
        opts_hn = []
        for l in body_hn.splitlines():
            s2 = l.strip()
            if not s2.startswith('\u2610'):
                continue
            for seg in s2.split('\u2610'):
                seg = seg.strip().strip('\u3000').strip()
                if seg:
                    opts_hn.append(seg)
        r.append(('记录条勾选档位≥5(四档＋未发生)', len(opts_hn) >= 5, '实%d档' % len(opts_hn)))
        # 四档行为锚定须与课堂 LOS 层级代号 I/V/G/P 对齐，否则家校数据无法合并、回收即废
        miss_hn = [k for k in ('自己做的', '提醒一句', '指一下或做手势', '手把手')
                   if not any(k in o for o in opts_hn)]
        # detail 只在失败时给原因：3.13.0 修正——此前无条件写 '缺'+join(空) = '缺'，
        # 报告里一排 "PASS … 缺"，读的人会当成"缺了东西"，与 FAIL 无从分辨。
        r.append(('记录条四档行为锚定齐全(对齐I/V/G/P)', not miss_hn,
                  '' if not miss_hn else '缺' + ','.join(miss_hn)))
        # 未发生 ≠ 未填：空白格一律按缺失处理，不得计入达成
        r.append(('记录条末档含"今天没做"(未发生≠未填)',
                  any('今天没做' in o for o in opts_hn)))
        # 纯勾选捕捉不到生态事件 → 必须保留选填开放式
        r.append(('记录条保留1行选填开放式', '选填' in body_hn))
        # 表号恒等于出现顺序：记录条做成表格会使教学过程内"表N"内嵌引用整体错位
        r.append(('记录条不占表号(禁做成带编号表格)',
                  re.search(r'\*\*表\d+', body_hn) is None))
        # 无回填落点的记录条＝让家长白填，是回收率逐轮衰减的真因。
        # 须有独立条目且指向具体位置（只查"回填"二字会被同句其它表述掩盖）
        m_rb = re.search(r'^- \*\*回填落点\*\*：(.*)$', body_hn, re.M)
        r.append(('记录条指定回填落点(须有独立条目)', m_rb is not None))
        r.append(('记录条回填落点指向具体位置',
                  bool(m_rb) and re.search(r'生活泛化|IEP', m_rb.group(1)) is not None))
        # 一张条印满三层会让家长找不到本层题目 → 弃填
        r.append(('记录条按A/B/C三层分版',
                  re.search(r'三层[^。；\n]{0,14}?各\s*印?\s*一版', body_hn) is not None))
    # 材料清单须同步注明分版，否则教师只印一版、家长找不到本层题
    r.append(('材料清单注明记录条按层分版',
              re.search(r'家长记录条[^。\n]{0,24}?三层各一版', text) is not None))
    # 否定式：行为 ABC 简录禁止勾选化（前事—行为—后果一勾选即丧失功能评估价值）
    abc_rows = [l for l in text.splitlines() if 'ABC' in l]
    r.append(('ABC简录未被勾选化(禁☐罗列)',
              not any('\u2610' in l for l in abc_rows)))

    # 3.8.0 教学设计结构要素补齐：教材分析 / 学情分析 / 教学重难点 / 人力协同
    tb = re.search(r'^### 教材分析\s*\n(.*?)(?=^### |^## |\Z)', text, re.M | re.S)
    r.append(('教材分析小节存在', bool(tb)))
    if tb:
        body_tb = tb.group(1)
        miss_tb = [k for k in ('出处与定位', '地位与作用', '内容解读', '前后联系', '使用建议')
                   if k not in body_tb]
        r.append(('教材分析五要素齐全', not miss_tb,
                  '' if not miss_tb else '缺' + ','.join(miss_tb)))
        # 前后联系是"教材分析"最容易写漏的一条：只写本课、不写已学与铺垫＝没有分析
        r.append(('教材分析含前后联系(已学→本课→铺垫)',
                  '已学' in body_tb and ('铺垫' in body_tb or '后续' in body_tb)))
    la = re.search(r'^### 学情分析\s*\n(.*?)(?=^### |^## |\Z)', text, re.M | re.S)
    r.append(('学情分析小节存在', bool(la)))
    if la:
        body_la = la.group(1)
        miss_la = [k for k in ('已有基础与生活经验', '障碍与能力特点', '学习优势与困难',
                               '起点能力', '分层教学结论')
                   if k not in body_la]
        r.append(('学情分析五要素齐全', not miss_la,
                  '' if not miss_la else '缺' + ','.join(miss_la)))
        # 禁堆叠诊断标签（功能性描述才有教学决策价值）
        r.append(('学情分析为功能性描述(禁诊断标签堆叠)',
                  not re.search(r'(中度|重度|轻度)智力障碍[＋+].*(自闭|脑瘫|语言)', body_la)))
    # 每课时三条：教学重点 / 教学难点 / 突破策略（禁只在矩阵后写一行"重难点：……"）
    miss_kp = []
    for _i in range(1, n_less + 1):
        segk = re.search(r'^### 第%d课时.*?(?=^### |^## |\Z)' % _i, text, re.M | re.S)
        if not segk:
            miss_kp.append('%d缺节' % _i)
            continue
        for kk in ('教学重点', '教学难点', '突破策略'):
            if kk not in segk.group(0):
                miss_kp.append('%d%s' % (_i, kk))
    r.append(('每课时含重难点三要素(重点/难点/突破策略)', not miss_kp,
              ','.join(miss_kp)))
    # 教学资源要素：材料说清"物"，还须说清"人"
    hc = re.search(r'^### 人力协同.*?(?=^### |^## |\Z)', text, re.M | re.S)
    r.append(('人力协同小节存在', bool(hc)))
    if hc:
        miss_hc = [k for k in ('主教', '助教', '家长或陪读', '一致性要求') if k not in hc.group(0)]
        r.append(('人力协同四要素齐全(主教/助教/家长/一致)', not miss_hc,
                  '' if not miss_hc else '缺' + ','.join(miss_hc)))

        # 禁做成带编号表格：表号恒等于出现顺序，此处插表会使教学过程内"表N"引用整体错位
        r.append(('人力协同未占用编号表(防表号级联错位)',
                  not re.search(r'\*\*表\d+[^\n]*人力协同', hc.group(0))))

    # ---- 3.11.0 材料清单可获性三级标注（资源不足学校的刚需）----
    ms = re.search(r'^### 材料清单.*?\n(.*?)(?=^### |^## |\Z)', text, re.M | re.S)
    if ms:
        mat_l = [l for l in ms.group(1).splitlines() if l.strip().startswith('☐')]
        no_tag = [l for l in mat_l if not re.search(r'【(采购|自制|替代)', l)]
        r.append(('材料清单每条含可获性三级标注', len(mat_l) >= 1 and not no_tag,
                  '%d条未标' % len(no_tag) if no_tag else '%d条' % len(mat_l)))
        # 只写“替代”而不给替代物＝等于没标，教师临到课前仍无方案
        bad_alt = [l for l in mat_l if '替代' in l and not re.search(r'替代\s*[：:]', l)]
        r.append(('【替代】须写出具体替代物', not bad_alt, str(len(bad_alt)) + '条空标'))
        # 只按行检测会漏：一行常含多个条目，删掉其中一个的标注仍有同行别处兜住。
        # 故再加总量门槛，取"材料行数"——标注数低于行数即平均每行不到一处＝敷衍
        n_tag = len(re.findall(r'【(?:采购|自制|替代)', ms.group(1)))
        r.append(('材料三级标注覆盖充分(≥材料行数)', n_tag >= len(mat_l),
                  '%d处/%d行' % (n_tag, len(mat_l))))
        # ---- 3.12.0 一条一项（源稿层）：此前一行用分号串联 3~6 个材料，
        #      Word 里落成整段且相邻两项之间连分隔符都没有 → 课前逐项勾核形同虚设。
        #      结构判据：一条只许一个 ☐，且**只许一处【…】标注**
        #      （两处＝两个材料被并成一条；流于全文子串仍会被同行别处兜住，故按结构计数）
        multi = [l for l in mat_l
                 if l.count('\u2610') > 1 or len(re.findall(r'【', l)) > 1]
        r.append(('材料清单一条一项(禁一行串联多项)', not multi,
                  '%d条多项' % len(multi)))
        # 数量与负责人：缺数量则备料不足，缺负责人则临堂无人去拿
        no_qty = [l for l in mat_l if not re.search(r'(\d+\s*(个|张|套|份|包|台|版|支|块|人|按组计))', l)]
        r.append(('材料清单每条标数量', not no_qty,
                  '' if not no_qty else '%d条未标数量' % len(no_qty)))
        no_own = [l for l in mat_l
                  if not re.search(r'(主教|助教|教师|家长)', l)]
        r.append(('材料清单每条标负责人', not no_own,
                  '' if not no_own else '%d条未标负责人' % len(no_own)))
    # ---- 3.11.0 突破策略须显式挂 LOS 档位代号 ----
    bps = re.findall(r'^\*\*突破策略\*\*：(.*)$', text, re.M)
    r.append(('突破策略条数==课时数', len(bps) == n_less, '%d条/课时%d' % (len(bps), n_less)))
    # 按"有没有"检测会漏：一条内改掉一处档位标注，别处仍在。
    # 故要求每条覆盖≥3个档位组——只标一档等于没分档
    def _bp_grp(x):
        return len(re.findall(r'\*\*[IVGPFN]+', x))
    r.append(('突破策略挂LOS档位代号', len(bps) >= 1 and all(_bp_grp(x) >= 1 for x in bps)))
    r.append(('突破策略覆盖≥3个档位组', len(bps) >= 1 and all(_bp_grp(x) >= 3 for x in bps),
              '最少%d组' % min([_bp_grp(x) for x in bps]) if bps else ''))
    # I 档“已达成就无需策略”是错的：先会的学生无安排即课堂空转，是走神与扰动源
    r.append(('突破策略禁写"I档无需策略"',
              not any(re.search(r'(无需|不需要).{0,4}策略', x) for x in bps)))
    # ---- 3.11.0 情感态度判据（参与强度分级，禁不可执行的秒数判据）----
    emo = re.findall(r'^\| 情感态度价值观 \|(.*)$', text, re.M)
    c_col = [l.strip().strip('|').split('|')[-1].strip() for l in emo]
    r.append(('情感态度C列用参与强度分级', len(c_col) >= 1 and all('级' in c for c in c_col)))
    r.append(('情感态度C列禁旧口径"≥1次即合法证据"',
              not any('≥1次即合法证据' in c for c in c_col)))
    # 12人课堂教师无法同时为多人掐表：写了也记不了，是伪可测判据
    r.append(('禁"注视≥N秒"类不可执行判据',
              re.search(r'注视\s*[≥>]\s*\d+\s*秒', text) is None))

    # ===== 3.9.0 新增：字符级回测发现的内部自相矛盾 / 体例漂移 =====
    # 1) 交付稿是面向教师的中文正式文档，半角直引号与中文弯引号混用会视觉打架；
    #    且极易在编辑期被无意引入（3.8.0 一次引入 117 处，另一份基准为 0 处可对照）。
    straight_q = len(re.findall(r'(?<![A-Za-z0-9=,\n])"(?![=,\n])', text))
    r.append(('交付稿无中英引号混用(禁非标点半角引号)', straight_q == 0,
              '残留%d处' % straight_q if straight_q else ''))
    # 2) 低视力放大值曾低于图卡标签基线（要求≥24pt，却写"放大至18pt"）——给低视力生的字更小
    # 注：用正则而非固定子串——第一轮曾用 `'低视力生材料放大至18pt'` 固定串，
    # 结果漏掉 `format-baseline.md` 的"放大至 18pt"（带空格）与
    # `release-checklist.md` 的"低视力生18pt"（无"放大至"三字）两处同型缺陷。
    low_pat = re.compile(r'低视力生[^。；\n]{0,14}?18pt')
    hit_lv = [m.group() for m in low_pat.finditer(text)
              if '学习单正文≥18pt' not in m.group() and '学习单正文 ≥18pt' not in m.group()]
    # 学习单正文 ≥18pt 是合法（学习单≠图卡标签）；图卡标签类下降至 18pt 才是缺陷
    bad_lv = [h for h in hit_lv if '学习单' not in h and '打印学习单' not in h]
    r.append(('低视力放大值不低于图卡标签基线(防自相矛盾)', not bad_lv, ','.join(bad_lv[:2])))
    r.append(('低视力生仍有明确再放大口径', bool(re.search(r'低视力生.*再放大', text))))
    # 3) 节名禁中英混排
    r.append(('交付稿无裸英文节名(checklist)', 'checklist' not in text))
    # 4) P参 子步骤编号须属本课时（4.1/4.2 是跨课时通用编号，三课时同名=无法核对）
    dup_sub = re.findall(r'新授 4\.\d', text)
    r.append(('P参子步骤未用跨课时通用编号', not dup_sub, ','.join(dup_sub[:3])))
    # 5) 起始 LOS 由 P前 前测确定；B 导入环节在前测之前，其证据不得占用「起始列」
    bad_ev = re.findall(r'证据：[^|]*?→表\d+起始列', text)
    r.append(('B导入证据未占用起始列(起始LOS以P前为准)', not bad_ev,
              '残留%d处' % len(bad_ev) if bad_ev else ''))

    # 8 安全替代表三列含风险
    safe = [b for b in bs if b and '安全替代' in b[0]]
    r.append(('安全替代表三列(含风险列)', bool(safe) and len(cells(safe[0][0])) == 3 and '风险' in safe[0][0]))

    # 9 板书版式为代码块
    r.append(('板书为版式代码块', bool(re.search(r'### 板书与图卡设计\s*\n\s*```', text))))

    # 10 教务归档视图含课标锚点三级（≥2 个“·”分隔）
    arch = text.split('教务归档视图')[1] if '教务归档视图' in text else ''
    anchor = re.search(r'课标依据\s*\|\s*([^|]+)', arch)
    r.append(('归档视图含课标锚点三级', bool(anchor) and anchor.group(1).count('·') >= 2))

    # 11 表号连续
    nums = [int(x) for x in re.findall(r'\*\*表(\d+)', text)]
    r.append(('表号连续无跳号', nums == list(range(1, len(nums) + 1)), str(nums)))

    # 12 章节中文数字编号连续
    cn = re.findall(r'^## ([一二三四五六七八九十]+)、', text, re.M)

    def cn2num(s):
        d = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9}
        if s in d:
            return d[s]
        if s.startswith('十'):
            return 10 + (d.get(s[1:], 0) if len(s) > 1 else 0)
        return 0

    idxs = [cn2num(c) for c in cn]
    r.append(('章节编号连续', idxs == list(range(1, len(idxs) + 1)), '/'.join(cn)))

    # 12b ===== 3.5.0 新增：课后回填宽表汇为文末单一附表 =====
    # 理由：LOS 变化记录表（1+2N+1 列）与 IEP 累计追踪表（≥7 列）在纵向版心下每列仅约
    # 1.7cm，压不进纵向；原地成横向节会把正文纵向流打断成三段（并逼出近空白页），故统一
    # 收进文末附表。正文保留起始LOS预设速查，保障课上动线不因移表而断。
    app_line = next((i for i, l in enumerate(lines)
                     if l.startswith('## 附：课后回填附表')), -1)
    r.append(('文末「课后回填附表」节存在', app_line > 0))
    body_text = '\n'.join(lines[:app_line]) if app_line > 0 else text
    appx_text = '\n'.join(lines[app_line:]) if app_line > 0 else ''
    wide_pos, i = [], 0
    while i < len(lines):
        if lines[i].strip().startswith('|'):
            j, cols = i, 0
            while j < len(lines) and lines[j].strip().startswith('|'):
                if not is_sep(lines[j]):
                    cols = max(cols, len(cells(lines[j])))
                j += 1
            if cols >= 6:
                wide_pos.append(i)
            i = j
        else:
            i += 1
    r.append(('宽表仅 LOS/IEP 两张', len(wide_pos) == 2, '%d 张' % len(wide_pos)))
    r.append(('宽表全部位于文末附表(正文全程纵向)',
              bool(wide_pos) and all(p > app_line for p in wide_pos),
              '正文内仍留 %d 张' % len([p for p in wide_pos if p < app_line])))
    r.append(('附表内含 LOS 变化记录表与 IEP 累计追踪表',
              '起始LOS' in appx_text and '年度长期目标' in appx_text))
    r.append(('正文保留起始LOS预设速查(课上动线不断)', '起始LOS预设速查' in body_text))
    r.append(('IEP 累计口径随表进附表', '累计口径' in appx_text))
    # 否定式：禁"附表N"第二套编号——两套体系会让"表号＝出现顺序"失效，教务核对必乱
    r.append(('表号单一体系(禁"附表N"第二套编号)',
              not re.search(r'\*\*附表\s*\d', text)
              and not re.search(r'附表[一二三四]', text)))

    # 13 占位符保留
    r.append(('占位符{{}}保留', '{{}}' in text))

    # 14 红区扫描
    hits = []
    if re.search(r'\d{17}[\dXx]', text):
        hits.append('疑似身份证')
    if re.search(r'(?<!\d)1[3-9]\d{9}(?!\d)', text):
        hits.append('疑似手机号')
    if re.search(r'\d{11,}', text):
        hits.append('≥11位数字串')
    r.append(('红区扫描干净', not hits, ','.join(hits)))

    # ===== 2.2.0 新增：跨课时行为干预 =====
    card_sec = ''
    mm = re.search(r'^## [一二三四五六七八九十]+、跨课时行为干预支持卡.*?(?=^## )', text, re.M | re.S)
    if mm:
        card_sec = mm.group(0)
    r.append(('跨课时行为支持卡章节存在', bool(card_sec)))
    keys = ['触发信号', '前因调整', '替代行为', '强化计划', '危机处置', '全员一致要求']
    miss = [k for k in keys if k not in card_sec]
    r.append(('行为支持卡六要素齐全', not miss, '缺' + ','.join(miss) if miss else ''))
    r.append(('强化计划逐课时削弱', '连续强化' in card_sec and ('FR2' in card_sec or '变动强化' in card_sec)))
    r.append(('替代行为标注已先教先练', '≥2次' in card_sec or '2次' in card_sec))
    r.append(('晋级降级阈值含80%判据', '80%' in card_sec and '无参与' in card_sec and '危机' in card_sec))
    taboo = [t for t in ['体罚', '惩罚性隔离', '强制进食', '当众批评']
             if not re.search(r'禁(止)?\s*' + t, card_sec)]
    r.append(('危机处置禁忌齐全(4条)', not taboo, ','.join(taboo)))

    # ===== 2.4.0 新增：五维感官调节前置 =====
    sn_sec = ''
    # 末节收尾时用 \Z 兜底：3.5.0 起 IEP 附表已是文档最后一个小节，其后不再有 ^## / ^### 可锚
    msn = re.search(r'^### .*感官调节.*?(?=^## |^### (?!.*感官调节)|\Z)', text, re.M | re.S)
    if msn:
        sn_sec = msn.group(0)
    r.append(('感官调节章节存在', bool(sn_sec)))
    dims = ['听觉', '视觉', '前庭', '口欲', '触觉']
    miss_d = [d for d in dims if d not in sn_sec]
    r.append(('感官五维度齐全', not miss_d, '缺' + ','.join(miss_d) if miss_d else ''))
    sn_tbl = [b for b in bs if b and cells(b[0]) and cells(b[0])[0] == '感官/环境维度']
    r.append(('感官调节表四列(维度/触发/前置/降刺激通道)',
              bool(sn_tbl) and len(cells(sn_tbl[0][0])) == 4, '' if sn_tbl else '缺表'))
    r.append(('降刺激通道非惩罚性(无"隔离"作唯一通道)',
              bool(sn_sec) and '惩罚性' in sn_sec))
    # 3.6.0：教学过程用到"闻"（多感官课常见）→ 感官表须有嗅觉维度，否则气味过敏无前置安排
    if re.search(r'[“"]?闻[”"]?（|闻一闻|闻气味|—闻—', text):
        r.append(('用"闻"则感官表含嗅觉维度', '嗅觉' in sn_sec, '缺嗅觉'))

    # ===== 2.4.0 新增：IEP 长期目标跨课时累计追踪 =====
    ie_sec = ''
    mie = re.search(r'^### .*IEP.*?(?=^## |^### (?!.*IEP)|\Z)', text, re.M | re.S)
    if mie:
        ie_sec = mie.group(0)
    r.append(('IEP累计追踪章节存在', bool(ie_sec)))
    ie_tbl = [b for b in bs if b and '年度长期目标' in b[0]]
    r.append(('IEP追踪表含年度长期目标列', bool(ie_tbl)))
    if ie_tbl:
        hdr = cells(ie_tbl[0][0])
        reach = len([h for h in hdr if re.search(r'课时\d+达成', h)])
        r.append(('IEP追踪表逐课时达成列==N', reach == n_less,
                  '实%d列/N=%d' % (reach, n_less)))
        rows = [c for c in ie_tbl[0][2:] if cells(c) and cells(c)[0].startswith('生')]
        r.append(('IEP追踪表全生覆盖(12人)', len(rows) == 12, '实%d人' % len(rows)))
        r.append(('IEP累计口径含成功率算式', '累计' in ie_sec and '成功率' in ie_sec and '÷' in ie_sec))

    # ===== 2.2.0 起创设、3.2.0 重构：学生可视材料规格 =====
    # 降级理由：原"排版与无障碍执行说明"大节描述的是**本 docx 的排版参数**，而 V2.4.0 起
    # 这些已由 scripts/md_to_docx.py 代码固化、且引擎铁律禁止手工重排 → 对教师零信息量，
    # 且"无引擎元信息/{{}} 占位符保留"属内部工作流语言，会随 Word 外发。故缩减为约束
    # **教师另外制作的可视教具**（图卡/投屏/板书大字卡/打印学习单）的规格，归入配套件节。
    ma = re.search(r'^### .*学生可视材料规格.*?(?=^## |^### (?!.*学生可视材料规格))',
                   text, re.M | re.S)
    acc_sec = ma.group(0) if ma else ''
    in_kit = bool(re.search(r'^## [一二三四五六七八九十]+、配套件.*?^### .*学生可视材料规格',
                            text, re.M | re.S))
    r.append(('学生可视材料规格存在且归入配套件下(三级标题)', bool(acc_sec) and in_kit,
              '缺三级标题' if not acc_sec else '未归入配套件'))
    legacy = re.search(r'^## [一二三四五六七八九十]+、排版与无障碍', text, re.M)
    r.append(('已无独立"排版与无障碍执行说明"大节(防回流)', not legacy))
    leak = [k for k in ('12pt', '小四', 'A4', '页边距', '页脚居中页码', '{{}} 占位符保留')
            if k in acc_sec]
    r.append(('可视材料规格不描述成品排版参数(防回流)', not leak, ','.join(leak)))
    miss_a = [k for k in ('36pt', '24pt', '18pt', '7:1', '4.5:1', '不得仅依赖颜色', '黑体')
              if k not in acc_sec]
    r.append(('可视材料规格要素齐全', not miss_a, '缺' + ','.join(miss_a) if miss_a else ''))

    # ===== 3.3.0 新增：交付稿打印安全 / 交叉引用抗漂移 =====
    # emoji 字形不在宋体与 Consolas 内，Word 靠系统 fallback 渲染，打印或另存时可能变方框；
    # 板书设计图是教师照做教具的蓝图，出现豆腐块即失效 → 一律改用文字标签。
    # 例外：U+2610 ☐ 是材料清单的勾选框，同时是 md_to_json.py 的**解析锚点**（不可替换），
    # 且它是单色几何符号、Word 内置字体覆盖良好，故显式放行。
    emo = re.findall(r'(?![\u2610-\u2612])[\u2600-\u26FF\u2700-\u27BF'
                     r'\U0001F000-\U0001FAFF]', text)
    r.append(('交付稿无 emoji(打印安全，防豆腐块)', not emo, ','.join(sorted(set(emo)))[:40]))
    # 绝对编号会随章节增减漂移（认识5 曾写"见第十一节配套件"而配套件实为第十节）→ 一律改用节名
    absref = re.findall(r'见第[一二三四五六七八九十]+节', text)
    r.append(('交叉引用不用绝对编号(防章节漂移)', not absref, ','.join(absref)))
    q = re.findall(r'^>', text, re.M)
    r.append(('引用块使用 > 标记(口径/注释分层)', bool(q), '实%d处' % len(q)))

    # ===== 3.1.0 新增：课时量研判（源稿侧，防"课时数靠默认/靠输入"回流）=====
    mj = re.search(r'^### 课时量研判.*?(?=^## |^### (?!.*课时量研判))', text, re.M | re.S)
    r.append(('课时量研判章节存在', bool(mj)))
    if mj:
        jseg = mj.group(0)
        jkeys = ['研判身份', '基础时长', '复现系数', '分层系数', '有效利用时长',
                 '测算课时数', '学科校验锚', '研判课时数N', '用户指定', '确定方式', '研判依据']
        miss_j = [k for k in jkeys if k not in jseg]
        r.append(('课时研判表字段齐全(11项)', not miss_j, '缺' + ','.join(miss_j) if miss_j else ''))
        r.append(('研判身份为双身份(学科专家＋特级教师)',
                  '资深教学专家' in jseg and '特级教师' in jseg))
        r.append(('研判表有表头行(项目/内容)',
                  bool([b for b in bs if b and cells(b[0]) and cells(b[0])[0] == '项目'])))
        jhow = re.search(r'确定方式\s*\|\s*(轻打扰直定|输出确认)', jseg)
        r.append(('确定方式属合法枚举(直定/确认)', bool(jhow), jhow.group(1) if jhow else ''))
        jn = re.search(r'研判课时数N\s*\|\s*(\d+)', jseg)
        r.append(('研判课时数N == 文件名课时数N',
                  bool(jn) and int(jn.group(1)) == n_less,
                  '%s/%s' % (jn.group(1) if jn else '?', n_less)))
        r.append(('研判依据含三阶切分口径(感知→理解→表达/应用)',
                  '感知' in jseg and ('应用' in jseg or '泛化' in jseg)))

    return name, r


def read_engine_version(root):
    """从 SKILL.md frontmatter 读取引擎版本（避免脚本内硬编码）"""
    try:
        text = open(os.path.join(root, 'SKILL.md'), encoding='utf-8').read()
        m = re.search(r'^version: (.+)$', text, re.M)
        return m.group(1).strip() if m else ''
    except Exception:
        return ''


def check_schema(root, ev=''):
    """结构化输出契约与样例校验"""
    r = []
    sp = os.path.join(root, 'references', 'output-schema.json')
    try:
        schema = json.load(open(sp, encoding='utf-8'))
        r.append(('Schema 文件为合法 JSON', True))
    except Exception as e:
        return [('Schema 文件为合法 JSON', False, str(e))]

    top = schema.get('required', [])
    r.append(('Schema 顶层 required 齐全', len(top) >= 8, str(len(top))))
    try:
        step_enum = schema['properties']['lessons']['items']['properties']['timeline']['items']['properties']['step']['enum']
    except KeyError:
        step_enum = []
    r.append(('Schema 含 BOPPPS step 枚举', set(step_enum) == {'B', 'O', 'P前', 'P参', 'P后', 'S'}, str(step_enum)))
    anc = schema.get('properties', {}).get('anchors', {})
    anc_req = anc.get('items', {}).get('required', [])
    sensory = schema.get('properties', {}).get('sensory_regulation', {})
    iep = schema.get('properties', {}).get('iep_tracking', {})
    r.append(('Schema anchors 为多锚点数组', anc.get('type') == 'array' and set(anc_req) == {'板块', '条目', '表述'}))
    sd = sensory.get('items', {}).get('required', [])
    r.append(('Schema 感官调节四字段', set(sd) == {'维度', '触发信号', '前置安排', '降刺激通道'}, str(sd)))
    r.append(('Schema 感官调节≥5维度', sensory.get('minItems') == 5 and
              set(sensory.get('items', {}).get('properties', {}).get('维度', {}).get('enum', [])) ==
              {'听觉', '视觉', '前庭与座位', '口欲与过敏', '触觉与材料'}))
    idf = iep.get('items', {}).get('required', [])
    r.append(('Schema IEP 追踪五字段',
              set(idf) == {'学生代号', '年度长期目标', '本课短期目标', '分课时达成', '累计口径'}, str(idf)))
    r.append(('Schema 顶层含 sensory_regulation/iep_tracking',
              'sensory_regulation' in schema.get('required', []) and 'iep_tracking' in schema.get('required', [])))
    try:
        bc = schema['properties']['support']['properties']['behavior_card']['required']
    except KeyError:
        bc = []
    r.append(('Schema 行为支持卡六要素', len(bc) == 6, str(len(bc))))

    jf = glob.glob(os.path.join(root, 'examples', '*结构化输出样例.json'))
    if not jf:
        return r + [('存在结构化输出样例', False)]
    try:
        data = json.load(open(jf[0], encoding='utf-8'))
        r.append(('JSON 样例为合法 JSON', True))
    except Exception as e:
        return r + [('JSON 样例为合法 JSON', False, str(e))]

    r.append(('JSON schema_version 符合引擎版本', data.get('schema_version') == ev,
              'JSON=%s SKILL=%s' % (data.get('schema_version'), ev)))
    miss_top = [k for k in top if k not in data]
    r.append(('JSON 顶层字段无缺失', not miss_top, '缺' + ','.join(miss_top) if miss_top else ''))
    # SKILL.md §6 声明的顶层字段集合必须与 Schema required 一致（防文档与契约漂移）
    try:
        sm = open(os.path.join(root, 'SKILL.md'), encoding='utf-8').read()
        decl = re.search(r'顶层必填\s*`([^`]+)`', sm)
        names = set(re.findall(r'[A-Za-z_][A-Za-z0-9_]*', decl.group(1))) if decl else set()
        r.append(('SKILL.md §6 顶层字段声明 ≡ Schema required',
                  bool(names) and names == set(top),
                  '多%s 缺%s' % (','.join(sorted(names - set(top))),
                                 ','.join(sorted(set(top) - names)))))
    except Exception as e:
        r.append(('SKILL.md §6 顶层字段声明 ≡ Schema required', False, str(e)[:60]))
    ancs = data.get('anchors', [])
    r.append(('JSON 多锚点且每条三级齐全',
              len(ancs) >= 1 and all(all(a.get(k) for k in ('板块', '条目', '表述')) for a in ancs),
              '%d条' % len(ancs)))

    n = data['meta']['课时数N']
    dur = data['meta']['单课时时长分钟']
    lessons = data['lessons']
    r.append(('JSON lessons 数 == 课时数N', len(lessons) == n, '%d/%d' % (len(lessons), n)))

    # ===== 3.1.0 新增：课时量研判（课时数由引擎研判，非默认 1 课时、非用户输入）=====
    jg = data.get('meta', {}).get('课时研判', {})
    jk = ['研判身份', '基础时长分钟', '复现系数', '分层系数', '有效利用时长分钟',
          '测算课时数', '学科校验锚', '研判课时数N', '确定方式', '研判依据']
    miss_j = [k for k in jk if not jg.get(k)]
    r.append(('JSON meta.课时研判 十项齐全', not miss_j, '缺' + ','.join(miss_j) if miss_j else ''))
    r.append(('研判身份为双身份(学科专家＋特级教师)',
              '资深教学专家' in jg.get('研判身份', '') and '特级教师' in jg.get('研判身份', '')))
    r.append(('JSON 研判课时数N == 课时数N', jg.get('研判课时数N') == n,
              '%s/%s' % (jg.get('研判课时数N'), n)))
    r.append(('确定方式属合法枚举(直定/确认)',
              jg.get('确定方式') in ('轻打扰直定', '输出确认'), str(jg.get('确定方式'))))
    b, rc, lc, ef, calc = (jg.get('基础时长分钟'), jg.get('复现系数'), jg.get('分层系数'),
                           jg.get('有效利用时长分钟'), jg.get('测算课时数'))
    num_ok = all(isinstance(x, (int, float)) and x for x in (b, rc, lc, ef, calc))
    if num_ok:
        want = b * rc * lc / ef
        r.append(('测算式可复核(基础×复现×分层÷有效≈测算值)', abs(want - calc) < 0.02,
                  '%.2f vs %s' % (want, calc)))
        r.append(('研判N == ceil(测算值)', n == int(calc) + (1 if calc % 1 else 0),
                  'N=%d 测算=%s' % (n, calc)))
        r.append(('复现/分层系数在规定区间', 1.2 <= rc <= 1.5 and 1.1 <= lc <= 1.3,
                  '复现%s 分层%s' % (rc, lc)))
        r.append(('有效利用时长 == 单课时时长×0.75(±1)', abs(ef - dur * 0.75) <= 1,
                  '%s vs %s' % (ef, dur * 0.75)))
        margin = (n - calc) / n
        r.append(('双出口判定自洽(余量>10%且N≤3 ⇔ 轻打扰直定)',
                  (margin > 0.10 and n <= 3) == (jg.get('确定方式') == '轻打扰直定'),
                  '余量%.0f%% N=%d %s' % (margin * 100, n, jg.get('确定方式'))))
    else:
        r.append(('测算式可复核(基础×复现×分层÷有效≈测算值)', False, '研判字段非数值'))

    needed = {'B', 'O', 'P前', 'P参', 'P后', 'S'}
    steps_ok, time_ok, matrix_ok, inq_ok = True, True, True, True
    detail = []
    for ls in lessons:
        steps = set(x['step'] for x in ls['timeline'])
        s = sum(x['分钟'] for x in ls['timeline'])
        if not needed <= steps:
            steps_ok = False
        if s != dur:
            time_ok = False
        if len(ls['objectives_matrix']) < 9:
            matrix_ok = False
        if len(ls['inquiry_activities']) < 1:
            inq_ok = False
        detail.append('L%d=%d' % (ls['课时序号'], s))
    r.append(('JSON 每课时 BOPPPS 六步齐全', steps_ok))
    r.append(('JSON 每课时分钟合计==%d' % dur, time_ok, ' '.join(detail)))
    r.append(('JSON 每课时目标矩阵≥9格', matrix_ok))
    r.append(('JSON 每课时探究活动≥1', inq_ok))

    los_ok, code_ok = True, True
    for row in data['los_table']:
        recs = row['records']
        if len(recs) != n:
            los_ok = False
        if any(('起始LOS' not in x or '达成LOS' not in x) for x in recs):
            los_ok = False
        if not re.match(r'^生\d+$', row['学生代号']):
            code_ok = False
    r.append(('JSON LOS 逐生逐课时成对', los_ok, '%d人' % len(data['los_table'])))
    r.append(('JSON 学生一律代号(红区合规)', code_ok))

    sup = data['support']
    keys = {'触发信号', '前因调整', '替代行为', '强化计划', '危机处置', '全员一致要求'}
    r.append(('JSON 行为支持卡六要素', keys <= set(sup['behavior_card'])))
    r.append(('JSON 含晋级降级阈值规则', len(sup.get('progression_rules', {})) >= 5))
    r.append(('JSON 泛化三场景齐全', all(data['generalization'].get(k) for k in ('家庭', '学校', '社区'))))
    r.append(('JSON 安全替代表三字段', all({'环节材料', '风险', '安全替代'} <= set(x) for x in data['safety_alternatives'])))
    r.append(('JSON 隐私声明 red_zone_free', data['privacy'].get('red_zone_free') is True))
    # 2.4.0：感官调节与 IEP 追踪
    sdims = [x['维度'] for x in data.get('sensory_regulation', [])]
    r.append(('JSON 感官五维度齐全',
              set(sdims) == {'听觉', '视觉', '前庭与座位', '口欲与过敏', '触觉与材料'}, '/'.join(sdims)))
    r.append(('JSON 感官每条四字段非空',
              all(all(x.get(k) for k in ('触发信号', '前置安排', '降刺激通道'))
                  for x in data.get('sensory_regulation', []))))
    ie_rows = data.get('iep_tracking', [])
    r.append(('JSON IEP 追踪全生覆盖(12人)', len(ie_rows) == 12, '实%d人' % len(ie_rows)))
    r.append(('JSON IEP 追踪逐课时达成列==N',
              all(len(row.get('分课时达成', {})) == n for row in ie_rows)))
    r.append(('JSON IEP 追踪字段非空且代号合规',
              bool(ie_rows) and all(row.get('年度长期目标') and row.get('本课短期目标')
                                    and re.match(r'^生\d+$', row['学生代号']) and row.get('累计口径')
                                    for row in ie_rows)))
    return r


def check_derived(root, ev=''):
    """md → JSON 派生一致性校验（Single Source 硬保证）"""
    r = []
    sys.path.insert(0, os.path.join(root, 'scripts'))
    try:
        import md_to_json as M
        r.append(('派生器 ENGINE_VERSION 与引擎一致', M.ENGINE_VERSION == ev,
                  'M=%s SKILL=%s' % (M.ENGINE_VERSION, ev)))
    except Exception as e:
        return [('可导入 md_to_json', False, str(e))]
    try:
        import md_to_docx as D
        r.append(('Word 生成器版本与引擎一致', D.ENGINE_VERSION == ev,
                  'D=%s SKILL=%s' % (D.ENGINE_VERSION, ev)))
    except Exception as e:
        r.append(('可导入 md_to_docx', False, str(e)))
    files = sorted(glob.glob(os.path.join(root, 'examples', '*.md')))
    for f in files:
        nm = os.path.basename(f)
        try:
            data = M.derive(open(f, encoding='utf-8').read())
        except Exception as e:
            r.append(('[%s] 派生成功' % nm, False, str(e)[:60]))
            continue
        n = data['meta']['课时数N']
        dur = data['meta']['单课时时长分钟']
        tag = '[%s]' % nm
        r.append((tag + ' 派生 lessons 数==N', len(data['lessons']) == n, '%d/%d' % (len(data['lessons']), n)))
        bad = []
        for ls in data['lessons']:
            s = sum(x['分钟'] for x in ls['timeline'])
            if s != dur:
                bad.append('L%d=%d' % (ls['课时序号'], s))
        r.append((tag + ' 派生每课时时间合计==%d' % dur, not bad, ' '.join(bad)))
        # 3.8.0 教学设计结构要素派生：教材分析 / 学情分析 / 重难点 / 人力协同
        tbj = data['meta'].get('教材分析', {})
        laj = data['meta'].get('学情分析', {})
        r.append((tag + ' 派生教材分析五要素',
                  all(tbj.get(k) for k in ('出处与定位', '地位与作用', '内容解读',
                                           '前后联系', '使用建议')),
                  str(sorted(tbj.keys()))))
        r.append((tag + ' 派生学情分析五要素',
                  all(laj.get(k) for k in ('已有基础与生活经验', '障碍与能力特点',
                                           '学习优势与困难', '起点能力', '分层教学结论')),
                  str(sorted(laj.keys()))))
        kp_bad = [ls['课时序号'] for ls in data['lessons']
                  if not all(ls.get('重难点', {}).get(k)
                             for k in ('教学重点', '教学难点', '突破策略'))]
        r.append((tag + ' 派生每课时重难点三要素', not kp_bad, str(kp_bad)))
        hcj = data['support'].get('人力协同', {})
        r.append((tag + ' 派生人力协同四要素',
                  all(hcj.get(k) for k in ('主教', '助教', '家长或陪读', '一致性要求')),
                  str(sorted(hcj.keys()))))
        r.append((tag + ' 派生 LOS 逐课时成对',
                  len(data['los_table']) >= 1 and all(len(row['records']) == n for row in data['los_table']),
                  '%d人' % len(data['los_table'])))
        r.append((tag + ' 派生目标矩阵≥9格', all(len(ls['objectives_matrix']) >= 9 for ls in data['lessons'])))
        r.append((tag + ' 派生探究活动≥1/课时', all(len(ls['inquiry_activities']) >= 1 for ls in data['lessons'])))
        r.append((tag + ' 派生分层作业三层齐全',
                  all(all(ls['分层作业'].get(k) for k in ('A', 'B', 'C')) for ls in data['lessons'])))
        r.append((tag + ' 派生锚点非空且三级',
                  len(data['anchors']) >= 1 and all(all(a.get(k) for k in ('板块', '条目', '表述')) for a in data['anchors']),
                  '%d条' % len(data['anchors'])))
        r.append((tag + ' 派生行为支持卡六要素', len(data['support']['behavior_card']) >= 6,
                  str(len(data['support']['behavior_card']))))
        r.append((tag + ' 派生泛化三场景', all(data['generalization'].get(k) for k in ('家庭', '学校', '社区'))))
        r.append((tag + ' 派生安全替代表非空', len(data['safety_alternatives']) >= 1))
        r.append((tag + ' 派生材料清单非空', len(data['materials']) >= 1))
        hn_d = data.get('support', {}).get('家长记录条', {})
        r.append((tag + ' 派生记录条勾选档位≥5', len(hn_d.get('勾选档位', [])) >= 5,
                  '实%d档' % len(hn_d.get('勾选档位', []))))
        r.append((tag + ' 派生记录条回填落点非空', bool(hn_d.get('回填落点', ''))))
        # ☐ 同时是材料清单的解析锚点：记录条若被误并入 materials 即为解析串味
        r.append((tag + ' 派生材料清单未被记录条污染',
                  not any('自己做的' in m for m in data.get('materials', []))))
        p = os.path.join(root, 'examples', '%s_结构化输出样例.json' % data['meta']['课题'])
        if os.path.exists(p):
            saved = json.load(open(p, encoding='utf-8'))
            same = json.dumps(saved, sort_keys=True, ensure_ascii=False) == json.dumps(data, sort_keys=True, ensure_ascii=False)
            r.append((tag + ' 落盘样例≡派生结果(防漂移)', same, '' if same else '须重跑 scripts/md_to_json.py'))
    return r


def check_skill_md(root):
    """SKILL.md 引擎自身防漂移校验（frontmatter / 版本号 / 铁律 / 新增机制 / 外部引用）"""
    r = []
    p = os.path.join(root, 'SKILL.md')
    text = open(p, encoding='utf-8').read()
    fm = re.match(r'^---\n(.*?)\n---\n', text, re.S)
    if not fm:
        return [('SKILL.md frontmatter 存在', False)]
    head = fm.group(1)
    keys = [l.split(':', 1)[0] for l in head.splitlines() if l and not l.startswith(' ')]
    # —— AgentKit / 豆包 / 千问技能规范（2.5.0 起）：name+description 必填、version 平台解析、
    #    其余顶层字段仅限规范白名单（license/compatibility/metadata/allowed-tools）——
    need = ['name', 'description', 'version']
    miss = [k for k in need if k not in keys]
    r.append(('frontmatter 必填字段齐全(name/description/version)', not miss,
              '缺' + ','.join(miss) if miss else ''))
    allowed = {'name', 'description', 'version', 'license', 'compatibility',
               'metadata', 'allowed-tools'}
    extra = [k for k in keys if k not in allowed]
    r.append(('frontmatter 顶层字段不超出规范白名单', not extra, ','.join(extra)))
    banned = ['display_name', 'display_name_en', 'description_zh', 'description_en',
              'tags', 'requires', 'author']
    left = [k for k in banned if k in keys]
    r.append(('旧版非标顶层字段已移除(防平台解析异常)', not left, ','.join(left)))
    nm = re.search(r'^name: (.+)$', head, re.M)
    nm_v = nm.group(1).strip() if nm else ''
    r.append(('name 合规(小写+连字符,≤64,不含agentkit)',
              bool(re.match(r'^[a-z0-9]+(-[a-z0-9]+)*$', nm_v))
              and len(nm_v) <= 64 and 'agentkit' not in nm_v, nm_v))
    ds = re.search(r'^description: (.+)$', head, re.M)
    ds_v = ds.group(1).strip() if ds else ''
    r.append(('description 非空且≤1024字符', 0 < len(ds_v) <= 1024, '%d字符' % len(ds_v)))
    r.append(('description 不含 XML 标签', not re.search(r'<[A-Za-z/!]', ds_v)))
    ver = re.search(r'^version: (.+)$', head, re.M)
    ok_semver = bool(ver and re.match(r'^\d+\.\d+\.\d+$', ver.group(1).strip()))
    r.append(('SKILL.md version 为 SemVer 三段', ok_semver, ver.group(1) if ver else ''))
    # 版本号多处一致：frontmatter / 正文标题 / JSON 样例 schema_version（脚本与 Schema 由派生组校验）
    v = ver.group(1).strip() if ver else ''
    jf = glob.glob(os.path.join(root, 'examples', '*结构化输出样例.json'))
    sv = ''
    if jf:
        try:
            sv = json.load(open(jf[0], encoding='utf-8')).get('schema_version', '')
        except Exception:
            sv = 'ERR'
    r.append(('JSON 样例版本与引擎一致', sv == v, 'JSON=%s SKILL=%s' % (sv, v)))
    r.append(('SKILL.md 正文标题含版本号', ('V' + v) in text, 'V' + v))
    # 五条铁律不漂移
    laws = ['红区零输入零输出', '学情禁编造', '教材禁杜撰', '课标锚点三级', '时长恒等']
    miss_l = [k for k in laws if k not in text]
    r.append(('五条铁律表述保留', not miss_l, '缺' + ','.join(miss_l) if miss_l else ''))
    # 2.2.0 新增机制保留
    # 2.6.0 三层渐进式披露：细则已外置到 references/，契约锚点按"引擎全库"判定
    # （SKILL.md ∪ references/*.md），既允许外置瘦身，又防止外置过程中规则丢失
    corpus = text + '\n' + '\n'.join(
        open(x, encoding='utf-8').read()
        for x in sorted(glob.glob(os.path.join(root, 'references', '*.md'))))
    mech = ['跨课时行为干预递进', 'ABC 简录', '连续 2 课时', '80%', '连续强化',
            '危机处置', '跨课时行为支持卡', '无参与(N)']
    miss_m = [k for k in mech if k not in corpus]
    r.append(('行为干预机制保留(全库)', not miss_m, '缺' + ','.join(miss_m) if miss_m else ''))
    acc = ['7:1', '4.5:1', '24pt', '36pt', '不得仅依赖颜色']
    miss_a = [k for k in acc if k not in corpus]
    r.append(('无障碍基线保留(全库)', not miss_a, '缺' + ','.join(miss_a) if miss_a else ''))
    # 3.9.0：低视力放大口径不得低于图卡标签基线（在效条文口径只能有一套）。
    # 范围＝SKILL.md ∪ references/ ∪ examples/；**不含 CHANGELOG**（其历史条目记录的是
    # 当时口径，按"历史版本标注不得回改"铁律保留原文，不可因断言而篡改历史）。
    lv_hits = []
    for _src, _txt in [('SKILL.md', text)] + [
            (os.path.basename(x), open(x, encoding='utf-8').read())
            for x in sorted(glob.glob(os.path.join(root, 'references', '*.md')))
    ] + [(os.path.basename(x), open(x, encoding='utf-8').read())
         for x in sorted(glob.glob(os.path.join(root, 'examples', '*.md')))]:
        for m in re.finditer(r'低视力生[^。；\n]{0,14}?18pt', _txt):
            if '学习单' not in m.group():
                lv_hits.append('%s:%s' % (_src, m.group()))
    r.append(('在效条文无"低视力降至18pt"旧口径(全扫描)', not lv_hits,
              ';'.join(lv_hits[:2])))
    # 3.9.0：教材/学情分析在主文件六环节表中只能挂载一次（曾同时挂在环节0与环节1）
    wf = re.search(r'## 2\. 六环节工作流.*?(?=\n## |\Z)', text, re.M | re.S)
    wf_txt = wf.group(0) if wf else ''
    r.append(('环节表中教材/学情分析只挂载一次(防重复挂载)',
              wf_txt.count('教材/学情分析') + wf_txt.count('教材分析·学情分析') == 1,
              '出现%d次' % (wf_txt.count('教材/学情分析') + wf_txt.count('教材分析·学情分析'))))
    # 2.6.0 渐进式披露元断言：①主文件体积封顶（防细则回流膨胀）②细则层无孤儿文件
    #   ③主文件常驻关键枚举（LOS/BOPPPS/分层/判据三段式）
    size = len(text.encode('utf-8'))
    r.append(('SKILL.md 体积≤12KB(渐进式披露防膨胀)', size <= 12288, '%d字节' % size))
    orphan = [os.path.basename(x) for x in sorted(glob.glob(os.path.join(root, 'references', '*')))
              if os.path.isfile(x) and os.path.basename(x) not in text]
    r.append(('references/ 无孤儿文件(均被主文件引用)', not orphan, ','.join(orphan)))
    enum = ['无参与(N)', 'BOPPPS', 'A轻度', '〔条件/支持〕']
    miss_e = [k for k in enum if k not in text]
    r.append(('主文件常驻关键枚举(LOS/BOPPPS/分层/判据)', not miss_e,
              '缺' + ','.join(miss_e) if miss_e else ''))
    # 主文件须声明三层架构与读取索引（否则后续维护者会把细则塞回主文件）
    r.append(('主文件声明三层渐进式披露', '渐进式披露' in text))
    # 纯对话平台可能不支持读取 references/ 文件 → 主文件必须写明该场景的降级出口，
    # 否则细则层在豆包/千问等纯对话环境等于丢失
    r.append(('主文件含"无法读取细则层"降级出口',
              '不能读取' in text and '降级' in text))
    # 外部引用存在性（防改名失联）
    refs = re.findall(r'`((?:scripts|references)/[\w\.\-]+|examples/[\w一-龥\.\-]+\.(?:md|json))`', text)
    broken = [x for x in set(refs) if not os.path.exists(os.path.join(root, x.replace('/', os.sep)))]
    r.append(('SKILL.md 外部引用均存在', not broken, ','.join(broken)))
    return r


def wide_table_count(text):
    """md 中列数 ≥ 6 的表格数（生成器应渲染为独立的 A4 横向节）"""
    lines = text.replace('\r\n', '\n').split('\n')
    i, n = 0, 0
    while i < len(lines):
        if lines[i].strip().startswith('|'):
            blk = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                blk.append(lines[i].strip())
                i += 1
            rows = [[c.strip() for c in r.strip().strip('|').split('|')]
                    for r in blk if r.strip('|').strip() and not SEP.match(r.replace('|', '').strip())]
            if rows and max(len(x) for x in rows) >= 6:
                n += 1
        else:
            i += 1
    return n


def wide_layout(text):
    """3.5.0：**连续宽表段**数 + 文档是否以宽表段收尾。

    生成器把"连续"宽表（其间仅隔标题/表题/口径引用这些轻量块）并入**同一**横向节，
    不再每张宽表各起一节——否则两宽表之间只剩一行小标题时，该标题会被"横向节另页起"
    逼成独占一整页，成品出现近空白页。轻量块不改变分节状态（它们被缓冲、归属待定）。"""
    items, cur = [], []
    for l in text.replace('\r\n', '\n').split('\n') + ['']:
        s = l.strip()
        if s.startswith('|'):
            cur.append(s)
            continue
        if cur:
            rows = [[c.strip() for c in r.strip().strip('|').split('|')] for r in cur
                    if not SEP.match(r.replace('|', '').strip())]
            cols = max((len(x) for x in rows), default=0)
            items.append(('wide' if cols >= 6 else 'narrow', cols))
            cur = []
        if not s:
            continue
        if s.startswith('#') or s.startswith('>') or re.match(r'^\*\*表\d+', s):
            items.append(('light', 0))
        else:
            items.append(('other', 0))
    runs, in_run, ends = 0, False, False
    for kind, _c in items:
        if kind == 'wide':
            if not in_run:
                runs += 1
                in_run = True
            ends = True
        elif kind == 'light':
            pass                      # 轻量块被缓冲，不决定分节
        else:
            in_run, ends = False, False
    return runs, ends


def first_body_sect(doc):
    """正文首节属性（第一个含页脚引用的 sectPr 片段）——3.4.0 起页码重排须落在它上面"""
    for m in re.finditer(r'<w:sectPr>(.*?)</w:sectPr>', doc, re.S):
        if 'footerReference' in m.group(1):
            return m.group(1)
    return ''


def check_docx(root):
    """Word 成品校验（2.4.0）：结构 / 版式契约 / 字节幂等 / 与源稿防漂移 / 外部读取复校"""
    import zipfile
    import xml.dom.minidom as minidom
    r = []
    sys.path.insert(0, os.path.join(root, 'scripts'))
    try:
        import md_to_docx as G
        r.append(('可导入 md_to_docx 生成器', True))
    except Exception as e:
        return [('可导入 md_to_docx 生成器', False, str(e)[:60])]

    for f in sorted(glob.glob(os.path.join(root, 'examples', '*.md'))):
        nm = os.path.basename(f)
        tag = '[%s]' % nm
        text = open(f, encoding='utf-8').read()
        try:
            data = G.build_docx_bytes(text)
        except Exception as e:
            r.append((tag + ' docx 生成成功', False, str(e)[:60]))
            continue
        r.append((tag + ' docx 生成成功', True))

        # ① 字节幂等：同一输入两次生成必须一致
        same_idem = hashlib.sha256(data).hexdigest() == hashlib.sha256(
            G.build_docx_bytes(text)).hexdigest()
        r.append((tag + ' docx 字节级幂等', same_idem))

        # ② OOXML 结构良构 + 版式契约（2.5.0 起 docx 不入库作基准，
        #    "成品≡源稿"端到端校验由交付通道组在临时目录执行）
        try:
            z = zipfile.ZipFile(__import__('io').BytesIO(data))
            doc = z.read('word/document.xml').decode('utf-8')
            sty = z.read('word/styles.xml').decode('utf-8')
            ftr = z.read('word/footer1.xml').decode('utf-8')
            minidom.parseString(doc)
            r.append((tag + ' document.xml 良构', True))
        except Exception as e:
            r.append((tag + ' document.xml 良构', False, str(e)[:60]))
            continue
        # ③ 打印安全与 markdown 残留（3.3.0）：成品正文不得出现 emoji，
        #    不得出现未解析的 markdown 标记（如引用块的 "> " 前缀）
        plain = re.sub(r'<[^>]+>', '', doc)
        emo = re.findall(r'(?![\u2610-\u2612])[\u2600-\u26FF\u2700-\u27BF'
                         r'\U0001F000-\U0001FAFF]', plain)
        r.append((tag + ' 成品无 emoji(打印安全)', not emo, ','.join(sorted(set(emo)))[:40]))
        junk = re.search(r'&gt;\s*[^\s]', plain)
        r.append((tag + ' 成品无 markdown 残留符号(> 前缀)', not junk))
        r.append((tag + ' 成品无 ** 与代码块围栏残留',
                  '**' not in plain and '```' not in plain))

        first = doc.index('<w:sectPr>')
        cover_sp = doc[first:doc.index('</w:sectPr>', first)]
        # 3.5.0 起文档可能以横向节（文末附表）收尾 → 页面与页边距须以**正文首节**为准，
        # 不能再取最后一个 sectPr（那已是横向页属性）
        body_sp = first_body_sect(doc)
        # 3.5.0：连续宽表并入同一横向节 → 节数 = 2 + 2×连续宽表段 −(末节即横向时 1)
        runs, ends_wide = wide_layout(text)
        want_sect = 2 + 2 * runs - (1 if ends_wide else 0)
        r.append((tag + ' 节属性数 = 2+2×连续宽表段−收尾修正',
                  doc.count('<w:sectPr') == want_sect,
                  'sectPr=%d 段=%d 收尾横向=%s 应%d'
                  % (doc.count('<w:sectPr'), runs, ends_wide, want_sect)))
        r.append((tag + ' 连续宽表段渲染为 A4 横向节',
                  doc.count('<w:pgSz w:w="16840"') == runs,
                  '横%d/段%d' % (doc.count('<w:pgSz w:w="16840"'), runs)))
        # 3.5.0：文末附表收尾时末节即横向，不另起空纵向节 → 无空白尾页
        last_sp = doc[doc.rindex('<w:sectPr>'):]
        r.append((tag + ' 末节为横向且与"以宽表段收尾"一致',
                  ('w:w="16840"' in last_sp) == ends_wide and 'footerReference' in last_sp))
        # 3.5.0：同一横向段内的连续宽表之间不得有分节符（否则又变回各占一节）
        wpos = []
        for m in re.finditer(r'<w:tbl>', doc):
            seg = doc[m.start():doc.find('</w:tbl>', m.start())]
            if len(re.findall(r'<w:gridCol', seg)) >= 6:
                wpos.append(m.start())
        gap_bad = ['%d→%d' % (a, b) for a, b in zip(wpos, wpos[1:])
                   if '<w:sectPr' in doc[doc.find('</w:tbl>', a):b]]
        r.append((tag + ' 连续宽表之间无分节符(并入同一横向节)',
                  len(wpos) >= 1 and not gap_bad, ','.join(gap_bad)))
        r.append((tag + ' 封面节无页脚引用(封面不出现页码)', 'footerReference' not in cover_sp))
        # 3.4.0：页码重排只加在**正文首节**（此前误加在末节 → 封面既占第 1 页使正文页码
        #        整体偏移一格，末节又因 start=1 回跳）
        r.append((tag + ' 页码重排唯一且落在正文首节',
                  doc.count('<w:pgNumType w:start="1"/>') == 1
                  and 'w:start="1"' in first_body_sect(doc),
                  'pgNumType=%d' % doc.count('<w:pgNumType w:start="1"/>')))
        # 3.4.0：含横向节的文档为多节结构，总页数域必然失真（SECTIONPAGES 按"本节页数"
        #        计 → 横向页显示"共 1 页"；NUMPAGES 又计入无页码的封面）→ 页脚只标页码
        r.append((tag + ' 页脚仅 PAGE 字段(不列必失真的总页数)',
                  'PAGE' in ftr and 'SECTIONPAGES' not in ftr and 'NUMPAGES' not in ftr))
        r.append((tag + ' 页面 A4 与页边距 2.54/3.18cm',
                  'w:w="11906"' in body_sp and 'w:h="16840"' in body_sp
                  and 'w:top="1440"' in body_sp and 'w:left="1803"' in body_sp))
        r.append((tag + ' 默认字体宋体/TimesNewRoman/小四',
                  all(k in sty for k in ('w:eastAsia="宋体"', 'w:ascii="Times New Roman"',
                                         '<w:sz w:val="24"/>'))))
        r.append((tag + ' 一级标题黑体三号加粗',
                  'w:eastAsia="黑体"' in sty and '<w:sz w:val="32"/>' in sty and '<w:b/>' in sty))
        used = set(re.findall(r'<w:pStyle w:val="(Heading\d)"/>', doc))
        r.append((tag + ' 章节标题用 Heading 样式(keepNext 禁标题孤行)',
                  len(used) >= 2 and '<w:keepNext/>' in sty, ','.join(sorted(used))))

        tbls = re.findall(r'<w:tbl>(.*?)</w:tbl>', doc, re.S)
        bad_w, heads, ratio_bad = [], 0, []
        for t in tbls:
            grid = [int(x) for x in re.findall(r'<w:gridCol w:w="(\d+)"', t)]
            row0 = re.search(r'<w:tr>(.*?)</w:tr>', t, re.S).group(1)
            # 3.3.0 起宽表（≥6 列）落在横向节，版心为 13234；其余为纵向版心 8300
            want_w = 13234 if len(grid) >= 6 else 8300
            if sum(grid) != want_w:
                bad_w.append('%d(应%d)' % (sum(grid), want_w))
            if '<w:tblHeader/>' in row0:
                heads += 1
            # 3.6.0：5 列的不止教学过程表（LOS 分层支持表亦为 5 列）→ 按表头精确区分
            if len(grid) == 5 and '教学环节' in row0:
                want = [round(8300 * x / 100.0) for x in (14, 26, 20, 24, 16)]
                if max(abs(a - b) for a, b in zip(grid, want)) > 3:
                    ratio_bad.append(str(grid))
        r.append((tag + ' 表格宽度合计=所在节版心且不溢出', not bad_w, str(bad_w[:2])))
        r.append((tag + ' 表格表头跨页重复', len(tbls) > 0 and heads == len(tbls),
                  '%d/%d' % (heads, len(tbls))))
        r.append((tag + ' 五列表列宽比 14/26/20/24/16', not ratio_bad, ','.join(ratio_bad[:1])))
        doc_wide = sum(1 for t in tbls if len(re.findall(r'<w:gridCol', t)) >= 6)
        r.append((tag + ' 成品宽表数与 md 宽表数一致',
                  doc_wide == wide_table_count(text),
                  'docx%d/md%d' % (doc_wide, wide_table_count(text))))

        # ③a' 3.4.0：表题—表格同页契约。此前表题属前一纵向节、宽表进横向节（新页起），
        #      表题被孤零零留在上一页；现由生成器把表题挂起、随表落入同一节。
        md_caps = re.findall(r'^\*\*((?:表\d+|附)[^\n]*?)\*\*\s*$', text, re.M)
        ppos = {}
        for m in re.finditer(r'<w:p>(.*?)</w:p>', doc, re.S):
            t = ''.join(re.findall(r'<w:t[^>]*>([^<]*)</w:t>', m.group(1))).strip()
            ppos.setdefault(t, (m.start(), m.end(), m.group(1)))
        located = [c for c in md_caps if c in ppos]
        r.append((tag + ' 表题全部在成品中定位', bool(located) and len(located) == len(md_caps),
                  '%d/%d' % (len(located), len(md_caps))))
        sep_bad = [c[:14] for c in located
                   if doc.find('<w:tbl>', ppos[c][1]) > 0
                   and '<w:sectPr' in doc[ppos[c][1]:doc.find('<w:tbl>', ppos[c][1])]]
        r.append((tag + ' 表题带 keepNext 且与其后表格同节(无分节符隔断)',
                  bool(located) and not sep_bad
                  and all('<w:keepNext/>' in ppos[c][2] for c in located), ','.join(sep_bad)))
        paren = [c for c in located if '（' in c]
        r.append((tag + ' 表题括号说明另起一行(w:br)，无括号表题不插多余换行',
                  bool(paren) and all('<w:br/>' in ppos[c][2] for c in paren)
                  and all('<w:br/>' not in ppos[c][2] for c in located if '（' not in c),
                  '%d 条带括号' % len(paren)))
        wide_cap_bad = []
        for c in located:
            en = ppos[c][1]
            ntbl = doc.find('<w:tbl>', en)
            if ntbl < 0:
                continue
            mt = re.match(r'<w:tbl>(.*?)</w:tbl>', doc[ntbl:], re.S)
            if mt and len(re.findall(r'<w:gridCol', mt.group(1))) >= 6:
                ns = doc.find('<w:sectPr>', en)
                if 'w:w="16840"' not in doc[ns:doc.find('</w:sectPr>', ns)]:
                    wide_cap_bad.append(c[:14])
        r.append((tag + ' 宽表表题随表进入横向节', not wide_cap_bad, ','.join(wide_cap_bad)))

        # ③b OOXML 包完整性 + 版式细节 + 无障碍底线
        names = z.namelist()
        ct = z.read('[Content_Types].xml').decode('utf-8')
        rels = z.read('_rels/.rels').decode('utf-8')
        r.append((tag + ' 含 docProps/core.xml 且类型与关系齐全',
                  'docProps/core.xml' in names and '/docProps/core.xml' in ct
                  and 'core-properties' in rels))
        core = z.read('docProps/core.xml').decode('utf-8') if 'docProps/core.xml' in names else ''
        leak2 = [k for k in ('双脉', 'WorkBuddy', 'SKILL', 'python', 'md_to_docx', '引擎')
                 if k in core]
        r.append((tag + ' core.xml 零引擎元信息', not leak2, ','.join(leak2)))
        r.append((tag + ' 正文 1.5 倍行距', 'w:line="360" w:lineRule="auto"' in sty))
        r.append((tag + ' 正文段首缩进 2 字符', 'w:firstLineChars="200"' in doc))
        r.append((tag + ' 表格字号≥小五(9pt)', 'w:sz w:val="18"' in doc))
        r.append((tag + ' 表头加粗居中',
                  re.search(r'<w:tblHeader/>.*?<w:b/>', doc, re.S) is not None))
        fills = set(re.findall(r'w:fill="([0-9A-Fa-f]{6})"', doc))

        def neutral_light(h):                      # 中性灰且浅色（禁彩色底纹作唯一编码）
            r_, g_, b_ = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            return max(r_, g_, b_) - min(r_, g_, b_) <= 6 and min(r_, g_, b_) >= 0xE0
        colored = [h for h in fills if not neutral_light(h)]
        r.append((tag + ' 底纹为中性浅色(色彩不作唯一编码)', not colored,
                  ','.join(sorted(colored))))
        r.append((tag + ' 封面标题二号居中',
                  'w:sz w:val="44"' in doc and 'w:val="center"' in doc))

        # ③c OOXML 元素序列（Word 对顺序敏感，顺序错会触发"内容不可读"修复提示）
        def seq_ok(fragment, tags):
            idx = [fragment.find(t) for t in tags]
            return all(i >= 0 for i in idx) and idx == sorted(idx)
        r.append((tag + ' sectPr 元素序(footerRef→pgSz→pgMar→pgNumType→cols→docGrid)',
                  seq_ok(first_body_sect(doc), ['<w:footerReference', '<w:pgSz', '<w:pgMar',
                                                '<w:pgNumType', '<w:cols', '<w:docGrid'])))
        tblpr = re.search(r'<w:tblPr>(.*?)</w:tblPr>', doc, re.S)
        r.append((tag + ' tblPr 元素序(tblW→jc→borders→layout→cellMar)',
                  tblpr is not None and seq_ok(tblpr.group(1),
                                               ['<w:tblW', '<w:jc', '<w:tblBorders',
                                                '<w:tblLayout', '<w:tblCellMar'])))
        r.append((tag + ' trPr 元素序(cantSplit→tblHeader)',
                  seq_ok(doc, ['<w:cantSplit/>', '<w:tblHeader/>'])))
        shd_ps = [m.group(0) for m in re.finditer(r'<w:pPr>.*?</w:pPr>', doc, re.S)
                  if 'w:shd' in m.group(0)]
        r.append((tag + ' pPr 中 shd 在 spacing/ind/jc 之前',
                  bool(shd_ps) and all(seq_ok(s, ['<w:shd', '<w:spacing', '<w:ind'])
                                       or '<w:spacing' not in s for s in shd_ps)))

        all_text = re.sub(r'<w:t[^>]*>([^<]*)</w:t>', r'\1', doc + ftr)
        r.append((tag + ' 占位符{{}}在成品中保留', '{{}}' in all_text))
        leak = [k for k in ('双脉教学引擎', 'V2.', 'SKILL.md', 'regression') if k in all_text]
        r.append((tag + ' 成品零引擎元信息', not leak, ','.join(leak)))
        hits = G.red_scan(all_text)
        r.append((tag + ' 成品红区扫描干净', not hits, ','.join(hits)))

        # ④ 外部读取复校（安装 python-docx 时启用）
        try:
            import docx
            d = docx.Document(__import__('io').BytesIO(data))
            txt = '\n'.join(p.text for p in d.paragraphs)
            for t in d.tables:
                for row in t.rows:
                    txt += '\n' + '|'.join(c.text for c in row.cells)
            ok_par = len(d.paragraphs) > 50 and len(d.tables) > 5
            r.append((tag + ' python-docx 可读且结构完整', ok_par,
                      '段%d/表%d' % (len(d.paragraphs), len(d.tables))))
            r.append((tag + ' 外部读取后占位符与五列表完好',
                      '{{}}' in txt and any('教学环节' in row.cells[0].text
                                            for t2 in d.tables for row in t2.rows
                                            if len(row.cells) == 5)))
        except ImportError:
            pass
    return r


def check_delivery(root):
    """交付通道契约（3.0.0 起）：CLI 参数 / PDF 通道已移除（否定式断言）/ --check 反篡改端到端
    （2.5.0 起 docx 成品不入库，反篡改端到端在系统临时目录执行，不触碰仓库）"""
    r = []
    src = open(os.path.join(root, 'scripts', 'md_to_docx.py'), encoding='utf-8').read()
    r.append(('CLI 支持 --check', "'--check' in sys.argv" in src))
    # 3.0.0：PDF 输出通道与 --pdf 参数已彻底移除 → 一律用**否定式断言**锁死，防日后回流
    r.append(('CLI 不再支持 --pdf(3.0.0 移除)', "'--pdf' in sys.argv" not in src))
    r.append(('生成器源码无 PDF 导出通道(3.0.0 移除)',
              'export_pdf' not in src and 'wdFormatPDF' not in src and 'docx2pdf' not in src))
    sys.path.insert(0, os.path.join(root, 'scripts'))
    try:
        import md_to_docx as G
        r.append(('生成器不暴露 PDF 导出函数', not hasattr(G, 'export_pdf')))
    except Exception as e:
        r.append(('生成器不暴露 PDF 导出函数', False, str(e)[:60]))

    # 在临时目录复刻 `--check` 的判定逻辑（跨进程调用在部分 Windows 控制台下会产生解码噪声；
    # 判定核心是「落盘成品 hash ≡ 源稿派生 hash」，进程内执行等价且更快）
    import md_to_docx as G
    tmp = os.path.join(REPORT_DIR, 'check_tmp')
    os.makedirs(tmp, exist_ok=True)

    def gen_all():
        for f in sorted(glob.glob(os.path.join(root, 'examples', '*.md'))):
            text = open(f, encoding='utf-8').read()
            dest = os.path.join(tmp, G.plan_name(text, os.path.basename(f)[:-3]))
            open(dest, 'wb').write(G.build_docx_bytes(text))

    def run_check():
        states = []
        for f in sorted(glob.glob(os.path.join(root, 'examples', '*.md'))):
            text = open(f, encoding='utf-8').read()
            want = hashlib.sha256(G.build_docx_bytes(text)).hexdigest()
            dest = os.path.join(tmp, G.plan_name(text, os.path.basename(f)[:-3]))
            got = hashlib.sha256(open(dest, 'rb').read()).hexdigest() if os.path.exists(dest) else ''
            states.append(got == want)
        return states

    try:
        gen_all()
        states = run_check()
        r.append(('--check 判定：全部成品 ≡ 源稿(SAME)', all(states) and states,
                  '%d/%d' % (sum(states), len(states))))
        victim = os.path.join(tmp, '认识5_教学设计方案_2课时.docx')
        orig = open(victim, 'rb').read()          # 内存备份（不新建文件，避免触发文件监控进程噪声）
        try:
            with open(victim, 'wb') as fh:
                fh.write(orig[:60] + b'X' + orig[61:])   # 模拟成品被手工改动
            r.append(('--check 判定：能识别被改动的成品(DIFF)',
                      not all(run_check())))
        finally:
            with open(victim, 'wb') as fh:
                fh.write(orig)
        r.append(('--check 判定：还原后重新 SAME', all(run_check())))
    except Exception as e:
        r.append(('--check 判定：全部成品 ≡ 源稿(SAME)', False, str(e)[:60]))
    return r


def check_repo(root, ev):
    """双轨合规与仓库卫生（2.5.0）：技能上传规范（豆包/千问/WorkBuddy）＋ GitHub 仓库规范
    —— 仓库保留治理文件（GitHub 轨），上传 zip 由 scripts/build_package.py 从仓库产出（技能轨）"""
    r = []
    # ① 技能标准布局（scripts/ + references/ + examples/）
    r.append(('scripts/ 四脚本齐全(含打包器)', all(os.path.exists(os.path.join(root, 'scripts', f)) for f in
              ('md_to_docx.py', 'md_to_json.py', 'regression_check.py', 'build_package.py'))))
    # 2.6.0 三层渐进式披露：references/ 承载细则层，七件缺一即断链
    ref_need = ('output-schema.json', 'format-baseline.md', 'release-checklist.md',
                'domain-core.md', 'workflow.md', 'strategy-matrix.md', 'state-and-fallback.md')
    miss_ref = [f for f in ref_need if not os.path.exists(os.path.join(root, 'references', f))]
    r.append(('references/ 细则层七件齐全', not miss_ref, '缺' + ','.join(miss_ref) if miss_ref else ''))
    r.append(('docs/ 自定义目录已移除', not os.path.exists(os.path.join(root, 'docs'))))
    # 打包器不得硬编码入包白名单（细则层会持续增长，白名单必然漏包）
    bp = os.path.join(root, 'scripts', 'build_package.py')
    bps = open(bp, encoding='utf-8').read() if os.path.exists(bp) else ''
    r.append(('打包器自动收集入包文件(无硬编码白名单)',
              'INCLUDE_REFERENCES' not in bps and 'INCLUDE_SCRIPTS' not in bps
              and 'def collect(' in bps))
    r.append(('打包器覆盖 scripts/*.py 与 references/*.md|json',
              all(x in bps for x in ("'*.py'", "'*.md'", "'*.json'"))))
    # ② GitHub 轨：治理文件保留且与当前版本同步
    gov = [f for f in ('README.md', 'CHANGELOG.md', 'CONTRIBUTING.md', 'LICENSE', '.gitignore')
           if not os.path.exists(os.path.join(root, f))]
    r.append(('GitHub 治理文件保留(README/CHANGELOG/CONTRIBUTING/LICENSE/.gitignore)',
              not gov, '缺' + ','.join(gov) if gov else ''))
    try:
        rd = open(os.path.join(root, 'README.md'), encoding='utf-8').read()
        r.append(('README 标题含当前版本', ev in rd.split('\n', 1)[0],
                  rd.split('\n', 1)[0][:40]))
        cl = open(os.path.join(root, 'CHANGELOG.md'), encoding='utf-8').read()
        r.append(('CHANGELOG 含当前版本条目', '## [%s]' % ev in cl))
    except Exception as e:
        r.append(('README/CHANGELOG 可读', False, str(e)[:60]))
    # ③ 包体卫生：无二进制成品、无运行期报告、无临时调试件（递归，跳过隐藏目录与 dist）
    bins = glob.glob(os.path.join(root, 'examples', '*.docx'))
    r.append(('examples/ 无二进制成品(docx)', not bins,
              ','.join(os.path.basename(b) for b in bins[:3])))
    junk = []
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if not d.startswith('.') and d != 'dist']
        for f in fn:
            if f.endswith('_report.txt') or f.startswith('_'):
                junk.append(os.path.relpath(os.path.join(dp, f), root))
    r.append(('仓库无运行期报告与临时调试件', not junk, ','.join(junk[:3])))
    # ④ SKILL.md 体积（渐进式披露：主文件只做路由层，行数字节双封顶）
    n_lines = len(open(os.path.join(root, 'SKILL.md'), encoding='utf-8').read().splitlines())
    r.append(('SKILL.md 行数≤150(路由层)', n_lines <= 150, '%d行' % n_lines))
    # ⑤ .gitignore：覆盖缓存/工作目录/打包产物
    gi_p = os.path.join(root, '.gitignore')
    gi = open(gi_p, encoding='utf-8').read() if os.path.exists(gi_p) else ''
    r.append(('.gitignore 覆盖缓存/工作目录/dist',
              '__pycache__/' in gi and '.workbuddy/' in gi and 'dist/' in gi))
    # ⑥ 现行文档不得引用 2.0.0 之前的旧章节号（现为 §0~§6）；CHANGELOG 属历史记录，回溯性引用合法，排除；
    #    回归项数随版本增长，硬编码必然过期 → 一律改为引用报告
    stale_sec, stale_num = [], []
    cand = [os.path.join(root, 'SKILL.md'), os.path.join(root, 'README.md'),
            os.path.join(root, 'CONTRIBUTING.md')]
    cand += glob.glob(os.path.join(root, 'references', '*.md'))
    for p in cand:
        if not os.path.exists(p):
            continue
        t = open(p, encoding='utf-8').read()
        bad = [s for s in re.findall(r'§(\d+)', t) if int(s) > 6]
        if bad:
            stale_sec.append('%s:%s' % (os.path.basename(p), ','.join(bad)))
        # 排除多段比例链（如五列表列宽比 14/26/20/24/16）：其每段两侧仍带 '/'，
        # 而"通过率 232/232"这类硬编码两侧不带 '/'
        hits = [m for m in re.finditer(r'(?<![\d.])\d{2,3}\s*/\s*\d{2,3}(?![\d.])', t)
                if not (m.start() > 0 and t[m.start() - 1] == '/')
                and not (m.end() < len(t) and t[m.end()] == '/')]
        if hits:
            stale_num.append(os.path.basename(p))
    r.append(('现行文档无已废弃章节号(>§6)', not stale_sec, ';'.join(stale_sec)))
    r.append(('治理文件不硬编码回归项数(改引用报告)', not stale_num, ','.join(stale_num)))
    # ⑦ 3.0.0 单格式（源 md ＋ Word 成品）：引擎全库不得残留任何 PDF 输出表述。
    #    扫描范围＝SKILL.md ＋ references/*.md ＋ scripts/*.py；本文件因需内置关键词字面量，跳过自身。
    #    注：附件"教材 PDF/Word"属**输入**类型，写法为 PDF/Word 不在关键词内，故不受影响。
    pdf_words = ['Word/PDF', 'Word+PDF', 'Word·PDF', 'Word 与 PDF', '.pdf', '--pdf',
                 'export_pdf', 'PDF 成品', 'PDF 导出', '双格式']
    pdf_hits = []
    for p in [os.path.join(root, 'SKILL.md')] + \
            sorted(glob.glob(os.path.join(root, 'references', '*.md'))) + \
            sorted(glob.glob(os.path.join(root, 'scripts', '*.py'))):
        if os.path.basename(p) == 'regression_check.py':
            continue
        t = open(p, encoding='utf-8').read()
        hit = [w for w in pdf_words if w in t]
        if hit:
            pdf_hits.append('%s:%s' % (os.path.basename(p), ','.join(hit)))
    r.append(('引擎全库无 PDF 输出表述(3.0.0 单格式)', not pdf_hits, ';'.join(pdf_hits)))
    return r


def main():
    out = []
    EV = read_engine_version(ROOT)
    out.append('引擎版本：%s' % EV)
    files = sorted(glob.glob(os.path.join(ROOT, 'examples', '*.md')))
    total = ok = 0
    for f in files:
        name, rs = check(f)
        out.append('=== %s ===' % name)
        for item in rs:
            label, passed = item[0], item[1]
            note = item[2] if len(item) > 2 else ''
            total += 1
            ok += 1 if passed else 0
            out.append('  [%s] %s %s' % ('PASS' if passed else 'FAIL', label, note))
    out.append('')
    out.append('=== 结构化输出契约 references/output-schema.json ===')
    for item in check_schema(ROOT, EV):
        total += 1
        ok += 1 if item[1] else 0
        out.append('  [%s] %s %s' % ('PASS' if item[1] else 'FAIL', item[0], item[2] if len(item) > 2 else ''))
    out.append('')
    out.append('=== 引擎自身 SKILL.md ===')
    for item in check_skill_md(ROOT):
        total += 1
        ok += 1 if item[1] else 0
        out.append('  [%s] %s %s' % ('PASS' if item[1] else 'FAIL', item[0], item[2] if len(item) > 2 else ''))
    out.append('')
    out.append('=== md→JSON 派生一致性（Single Source） ===')
    for item in check_derived(ROOT, EV):
        total += 1
        ok += 1 if item[1] else 0
        out.append('  [%s] %s %s' % ('PASS' if item[1] else 'FAIL', item[0], item[2] if len(item) > 2 else ''))
    out.append('')
    out.append('=== Word 成品 md→docx（结构/版式/幂等/防漂移） ===')
    for item in check_docx(ROOT):
        total += 1
        ok += 1 if item[1] else 0
        out.append('  [%s] %s %s' % ('PASS' if item[1] else 'FAIL', item[0], item[2] if len(item) > 2 else ''))
    out.append('')
    out.append('=== 交付通道契约 md→docx CLI / 反篡改 / PDF 已移除 ===')
    for item in check_delivery(ROOT):
        total += 1
        ok += 1 if item[1] else 0
        out.append('  [%s] %s %s' % ('PASS' if item[1] else 'FAIL', item[0], item[2] if len(item) > 2 else ''))
    out.append('')
    out.append('=== 双轨合规与仓库卫生 ===')
    for item in check_repo(ROOT, EV):
        total += 1
        ok += 1 if item[1] else 0
        out.append('  [%s] %s %s' % ('PASS' if item[1] else 'FAIL', item[0], item[2] if len(item) > 2 else ''))
    out.append('')
    # 元断言：同一分节内同一断言重复计入会让通过率虚高，必须为 0
    # （跨文件同名断言是合法的，故按分节重置去重集）
    seen, dup = set(), []
    for l in out:
        if l.startswith('==='):
            seen.clear()
            continue
        if l.startswith('  [PASS') or l.startswith('  [FAIL'):
            key = l.split(']', 1)[1].strip()
            if key in seen:
                dup.append(l.strip())
            seen.add(key)
    for d in dup[:5]:
        total += 1
        out.append('  [FAIL] 断言重复计入 %s' % d)
    out.append('')
    rate = ok * 100.0 / total if total else 0
    out.append('通过率：%d/%d = %.1f%%' % (ok, total, rate))
    open(report_path('regression_report.txt'), 'w', encoding='utf-8').write('\n'.join(out))


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        import traceback
        open(report_path('regression_report.txt'), 'w',
             encoding='utf-8').write('ERROR:\n' + traceback.format_exc())
