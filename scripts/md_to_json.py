# -*- coding: utf-8 -*-
"""从教案 md 源稿派生结构化 JSON（Single Source 硬保证）。

背景：V2.2.0 曾手工维护一份 JSON 样例，与 md 源稿存在语义漂移（丢失"阅读"锚点、
     分层作业结构不对齐），违反 Single Source 铁律。本脚本让 JSON 只能由 md 派生，杜绝漂移。

用法：python scripts/md_to_json.py [输出目录（默认 examples）]
输出：<课题>_结构化输出样例.json（合 references/output-schema.json）
约定：md 是唯一源稿；本脚本是唯一转换器；禁止手工编辑产物 JSON。
报告：写入系统临时目录 %TEMP%/peizhi_shuangmai/（不进仓库/技能包，避免运行期产物混入）。
"""
import re
import os
import json
import sys
import glob
import tempfile

ENGINE_VERSION = '3.20.0'

REPORT_DIR = os.path.join(tempfile.gettempdir(), 'peizhi_shuangmai')


def report_path(name):
    """运行期报告一律落系统临时目录（包内不产 *_report.txt）"""
    os.makedirs(REPORT_DIR, exist_ok=True)
    return os.path.join(REPORT_DIR, name)

# 感官维度映射（domain-core §4 感官六维，3.13.0 补齐嗅觉）。
# 教训：3.7.0 已把感官表升为六维并写入 domain-core/glossary，但本表仍停在五维，
# 导致 md 里的「嗅觉（气味）」行匹配失败被 `continue` 静默丢弃——而 JSON 恰恰因为少一条
# 才满足下游 `set(...)=={五维}` 的硬相等断言，**丢数据却被验证为通过**。
# 故本表必须覆盖 domain-core §4 的全部六个维度，且下方解析改为「不再静默丢弃」。
SENSORY_MAP = [
    ('听觉', '听觉'), ('视觉', '视觉'), ('前庭', '前庭与座位'),
    ('口欲', '口欲与过敏'), ('过敏', '口欲与过敏'), ('触觉', '触觉与材料'),
    ('嗅觉', '嗅觉'), ('气味', '嗅觉'),
]


# ---------- 基础切分 ----------
def split_sections(text):
    """按 ## / ### 标题切分为 [(level, title, body_lines)]"""
    lines = text.splitlines()
    heads = [(i, l) for i, l in enumerate(lines) if re.match(r'^#{2,3} ', l)]
    secs = []
    for k, (i, l) in enumerate(heads):
        end = heads[k + 1][0] if k + 1 < len(heads) else len(lines)
        level = 2 if l.startswith('## ') else 3
        secs.append((level, l.strip('# ').strip(), lines[i + 1:end]))
    return secs


SEC_RE = re.compile(r'^[\s\-:|]+$')


def table_blocks(body):
    """从段落中提取表格 [(header, rows)]"""
    out, cur = [], []
    for l in body:
        s = l.strip()
        if s.startswith('|'):
            cur.append(s)
        elif cur:
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    res = []
    for b in out:
        if len(b) < 2:
            continue
        header = [c.strip() for c in b[0].strip('|').split('|')]
        rows = []
        for r in b[1:]:
            if SEC_RE.match(r.replace('|', '').strip()):
                continue
            rows.append([c.strip() for c in r.strip().strip('|').split('|')])
        res.append((header, rows))
    return res


def kv_table(header, rows):
    """两列 key/value 表 -> dict"""
    d = {}
    for r in rows:
        if len(r) >= 2 and r[0] and r[0] != '---':
            d[r[0]] = r[1]
    return d


def find_sec(secs, *subs, level=None):
    for lv, title, body in secs:
        if all(s in title for s in subs) and (level is None or lv == level):
            return (lv, title, body)
    return None


def parse_bold_kv(body):
    """解析 '**键**：值' / '- **键**：值' 形式的行 -> dict（3.8.0 教材分析/学情分析/重难点共用）"""
    d = {}
    for l in body:
        m = re.match(r'^\s*(?:[-*]|\d+[.、)])?\s*\*\*(.+?)\*\*\s*[：:]\s*(.+)$', l.strip())
        if m:
            # 键名归一化：剥离行尾括号补充说明，使"使用建议（培智化取舍）"→"使用建议"，
            # 与 output-schema.json 的属性名严格对齐（否则派生键与契约键对不上）
            key = re.sub(r'[（(][^）)]*[）)]\s*$', '', m.group(1)).strip()
            d[key] = m.group(2).strip()
    return d


# ---------- 字段解析 ----------
CN_NUM = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9}


# 课时序号唯一解析入口（3.14.0）：容许中文数字／全角数字／序数与"课时"之间的空格。
# 此前散落三处硬编码 `re.search(r'第(\d+)课时', t)`：教师把标题写成「第一课时」「第 2 课时」
# 这类最常见的中文书写形态时**匹配失败**，该课时的 timeline 与目标矩阵被 continue 静默丢弃，
# 而 lessons 数与 meta.课时数N 仍照常输出——派生便得到一份"课时齐全但教学过程全空"的教案，
# 且不报错、不告警。CN_NUM 与 cn2int 早已备好却从未被调用（死代码），本版接上。
_LESSON_NUM_RE = re.compile(r'第\s*([0-9０-９一二三四五六七八九十]{1,3})\s*课时')
_FULLWIDTH = str.maketrans('０１２３４５６７８９', '0123456789')


def cn2int(s):
    if s in CN_NUM:
        return CN_NUM[s]
    if s.startswith('十'):
        return 10 + (CN_NUM.get(s[1:], 0) if len(s) > 1 else 0)
    if len(s) == 2 and s[0] in CN_NUM and s[1] == '十':      # 二十 / 三十
        return CN_NUM[s[0]] * 10
    return 0


def lesson_idx(title):
    """取课时序号；无法识别返回 0（调用方自行决定兜底策略）。"""
    m = _LESSON_NUM_RE.search(title or '')
    if not m:
        return 0
    raw = m.group(1).translate(_FULLWIDTH)
    if raw.isdigit():
        return int(raw)
    return cn2int(raw)


def parse_step(name_cell):
    """'趣味导入（B·3′）' -> ('B', 3, '趣味导入')"""
    m = re.search(r'（([^）·]+)·(\d+)′）', name_cell)
    if not m:
        return None
    step = m.group(1)
    minutes = int(m.group(2))
    name = name_cell[:m.start()].strip() or name_cell.replace(m.group(0), '').strip()
    return {'step': step, '环节名': name, '分钟': minutes}


def clean_title(raw):
    """'《好吃的水果》（人教版…第4课）' -> ('好吃的水果', '人教版…第4课')"""
    m = re.match(r'^《(.+?)》(.*)$', raw.strip())
    if m:
        return m.group(1), m.group(2).strip('（）() ')
    return raw.strip(), ''


CRITERION_RE = re.compile(r'(（[^（）]*?[≥≤][^（）]*?）|（[^（）]*?\d+次[^（）]*?）|≥[^，。；、）]*|≤[^，。；、）]*)')


def split_criterion(cell):
    """从目标单元格中剥离可测判据"""
    crits = CRITERION_RE.findall(cell)
    crit = '；'.join([c.strip('（）() ') for c in crits if c.strip('（）() ')])
    goal = CRITERION_RE.sub('', cell).strip('，。； ')
    return goal or cell, crit or '（目标描述内含判定条件）'


def derive(text):
    secs = split_sections(text)

    # ---- meta ----
    # 3.17.0：「教案头」更名「教案信息」。find_sec 是子串匹配，改名后若不同步，
    # meta（课题/班级/时长/课时数）会被整体取空而不报错——这是改名类改动最典型的静默事故。
    head_sec = find_sec(secs, '教案信息')
    meta_raw = {}
    if head_sec:
        tbl = table_blocks(head_sec[2])
        if tbl:
            meta_raw = kv_table(*tbl[0])
    title, textbook_note = clean_title(meta_raw.get('课题', ''))
    cls = meta_raw.get('班级', '')
    n_stu = len(re.findall(r'A组\d+人|B组\d+人|C组\d+人', cls))
    dur_m = re.search(r'每课时(\d+)分钟', meta_raw.get('课堂时长', ''))
    dur = int(dur_m.group(1)) if dur_m else 35
    n_m = re.search(r'共(\d+)课时', meta_raw.get('课堂时长', '')) or re.search(r'共(\d+)课时', meta_raw.get('课时定位', ''))
    n = int(n_m.group(1)) if n_m else 1

    # ---- 课时量研判（3.1.0 起：课时数由引擎研判，测算过程随产物留痕供教务溯源）----
    judge = {}
    j_sec = find_sec(secs, '课时量研判')
    if j_sec:
        jt = table_blocks(j_sec[2])
        if jt:
            jr = kv_table(*jt[0])

            def jnum(key, pat, cast=float, default=0):
                mm = re.search(pat, jr.get(key, ''))
                try:
                    return cast(mm.group(1))
                except Exception:
                    return default

            base = jnum('基础时长', r'(\d+)\s*′', int)
            rep_c = jnum('复现系数', r'(\d+(?:\.\d+)?)')
            lay_c = jnum('分层系数', r'(\d+(?:\.\d+)?)')
            eff = jnum('有效利用时长', r'≈\s*(\d+)\s*′', int)
            if not eff:
                eff = int(round(dur * 0.75))          # 兜底：单课时时长 × 0.75
            calc = jnum('测算课时数', r'=\s*(\d+(?:\.\d+)?)')
            if not calc and base and rep_c and lay_c and eff:
                calc = round(base * rep_c * lay_c / eff, 2)   # 兜底：按测算式反算
            jn = jnum('研判课时数N', r'(\d+)', int) or n
            judge = {
                '研判身份': jr.get('研判身份', ''),
                '基础时长分钟': base,
                '复现系数': rep_c,
                '分层系数': lay_c,
                '有效利用时长分钟': eff,
                '测算课时数': calc,
                '学科校验锚': jr.get('学科校验锚', ''),
                '研判课时数N': jn,
                '用户指定': jr.get('用户指定', '无'),
                '确定方式': '轻打扰直定' if '轻打扰' in jr.get('确定方式', '') else '输出确认',
                '研判依据': jr.get('研判依据', ''),
            }

    # ---- anchors（多锚点；须定位到真正含列表的三级小节，避开父章节）----
    anchors = []
    a_sec = None
    for s in secs:
        if '课标锚点' in s[1] and any('｜' in l for l in s[2]):
            a_sec = s
            break
    if a_sec:
        for l in a_sec[2]:
            l = l.strip()
            if l.startswith('- '):
                l = l[2:]
            if '｜' not in l:
                continue
            entry, rest = l.split('｜', 1)
            parts = [p.strip() for p in rest.split('·') if p.strip()]
            if len(parts) >= 2:
                anchors.append({'板块': parts[0], '条目': entry.strip(), '表述': ' · '.join(parts[1:])})
            elif parts:
                anchors.append({'板块': parts[0], '条目': entry.strip(), '表述': parts[0]})

    # ---- 课时总体安排 ----
    sched = []
    s_sec = find_sec(secs, '课时总体安排')
    if s_sec:
        tbl = table_blocks(s_sec[2])
        if tbl:
            for r in tbl[0][1]:
                if len(r) >= 4:
                    sched.append({'主题': r[1], '核心目标': r[2], '生活化落点': r[3]})

    # ---- 目标矩阵 ----
    matrices = []
    for _, t, body in secs:
        joined = '\n'.join(body)
        idx = lesson_idx(t)
        if not idx or ('目标矩阵' not in joined and '维度' not in joined):
            continue
        for header, rows in table_blocks(body):
            if not header or '维度' not in header[0]:
                continue
            cells_out = []
            for r in rows:
                if len(r) < 4 or not r[0]:
                    continue
                dim = r[0]
                for layer, val in zip(('A', 'B', 'C'), r[1:4]):
                    g, c = split_criterion(val)
                    cells_out.append({'维度': dim, '层': layer, '目标': g, '评测判据': c})
            matrices.append((idx, cells_out))

    # ---- 五列表 / 探究活动 ----
    timelines, inquiries, boards = {}, {}, {}
    for _, t, body in secs:
        idx = lesson_idx(t)
        if not idx:
            continue
        for header, rows in table_blocks(body):
            if not header or '教学环节' not in header[0]:
                continue
            tl, inq = [], []
            for r in rows:
                if not r or not r[0]:
                    continue
                s = parse_step(r[0])
                if s:
                    tl.append(s)
                teacher = r[1] if len(r) > 1 else ''
                if '【探究活动】' in teacher:
                    mi = re.search(r'【探究活动】[“"]([^”"]+)[”"]', teacher)
                    mm = re.search(r'（([^）]*?)）\s*$', r[0]) or re.search(r'·(\d+)′', r[0])
                    minutes = int(re.search(r'·(\d+)′', r[0]).group(1)) if re.search(r'·(\d+)′', r[0]) else 0
                    versions = r[3] if len(r) > 3 else ''
                    inq.append({
                        '名称': mi.group(1) if mi else '探究活动',
                        '步别': 'P参',
                        '分钟': minutes,
                        '版本': {'A': '见支持策略列·A', 'B': '见支持策略列·B', 'C': '见支持策略列·C'},
                        '材料': [],
                        # 3.15.0：去掉 [:120] 固定窗口截断——探究流程是教师照着做的步骤，
                        # 截断后 JSON 侧永远缺尾巴，且这种"悄悄切一刀"正是本项目反复
                        # 出事的老写法（见 sec_body 注释里的两条禁忌）。
                        '流程': teacher,
                        '支持策略': versions,
                    })
            if tl:
                timelines[idx] = tl
            if inq:
                inquiries[idx] = inq

    # ---- 板书（代码块）----
    # 3.15.0 修「取第一个」：此前只取节内**第一个**代码块并复制给全部课时，而 domain-core
    # 要求"每课时自成闭环…独立板书"——于是三课时 board_layout 完全雷同，"独立板书"在
    # 结构化契约里被无声违反且不报错。改为按节内「第N课时」标记定位各自代码块；
    # 源稿未标课时（旧稿）时退回"通用板书填全部"，保证向后兼容。
    b_sec = find_sec(secs, '板书')
    if b_sec:
        _cur, _buf, _inblk = 0, [], False
        for _l in b_sec[2]:
            if _l.strip().startswith('```'):
                if _inblk:
                    _blk = '\n'.join(_buf).strip()
                    if _blk:
                        if _cur:
                            boards[_cur] = _blk
                        else:
                            for _i in range(1, n + 1):
                                boards.setdefault(_i, _blk)
                    _buf, _inblk = [], False
                else:
                    _inblk, _buf = True, []
                continue
            if _inblk:
                _buf.append(_l)
                continue
            _li = lesson_idx(_l)
            if _li:
                _cur = _li

    # ---- LOS 记录表 ----
    los_table = []
    l_sec = None
    for s in secs:
        if 'LOS' in s[1] and ('记录' in s[1] or '变化' in s[1]):
            l_sec = s
            break
    if l_sec:
        for header, rows in table_blocks(l_sec[2]):
            if not header or header[0] != '学生':
                continue
            for r in rows:
                if not r or not r[0].startswith('生'):
                    continue
                recs = []
                pairs = []
                for i in range(1, len(r) - 1):
                    pairs.append(r[i])
                for k in range(0, len(pairs) - 1, 2):
                    recs.append({'课时': k // 2 + 1,
                                 '起始LOS': pairs[k] or '待回填',
                                 '达成LOS': (pairs[k + 1] if k + 1 < len(pairs) else '') or '待回填'})
                los_table.append({'学生代号': r[0], 'records': recs, '备注': r[-1]})

    # ---- 安全替代 ----
    safety = []
    sa = find_sec(secs, '安全替代')
    if sa:
        for header, rows in table_blocks(sa[2]):
            if not header or '安全替代' not in ''.join(header):
                continue
            for r in rows:
                if len(r) >= 3:
                    safety.append({'环节材料': r[0], '风险': r[1], '安全替代': r[2]})

    # ---- 泛化 ----
    gen = {'家庭': [], '学校': [], '社区': []}
    g_sec = find_sec(secs, '生活泛化')
    if g_sec:
        cur = None
        for l in g_sec[2]:
            l = l.strip()
            head = re.match(r'^(家庭|学校|社区)[：:]', l)
            if head:
                cur = head.group(1)
                l = l[len(head.group(0)):].strip()
            if cur and l and not l.startswith('|'):
                gen[cur].append(l)

    # ---- 分层作业 ----
    homework = {}
    h_sec = find_sec(secs, '分层作业')
    if h_sec:
        for header, rows in table_blocks(h_sec[2]):
            # 数据型表格（无语义表头）：表头行本身也是数据，须一并纳入
            for r in [header] + rows:
                if len(r) < 2 or not r[0]:
                    continue
                mm = re.match(r'^(第\s*[0-9０-９一二三四五六七八九十]{1,3}\s*课时)[·・]\s*([ABC])', r[0])
                if mm:
                    _i = lesson_idx(mm.group(1))
                    if _i:
                        homework.setdefault(_i, {})[mm.group(2)] = r[1]
                elif len(r) >= 2 and r[0] in ('A', 'B', 'C'):
                    pass

    # ---- 材料清单 ----
    materials = []
    m_sec = find_sec(secs, '材料清单')
    if m_sec:
        for l in m_sec[2]:
            if l.strip().startswith('\u2610'):
                # 3.12.0：材料清单**一条一项**——与 md_to_docx 的版面规则同源
                # （此前源稿一行串联多个材料 → Word 拼成整段；JSON 亦须同粒度，
                #  否则 machine-readable 与成品两份对不上）
                for seg in re.split(r'(?=[\u2610-\u2612])', l.strip()):
                    seg = seg.strip().strip('；;').strip()
                    if seg:
                        # 同上：勾框与正文之间留半角空格（与成品版面同源）
                        body = seg.lstrip('\u2610\u2611\u2612').strip()
                        materials.append('\u2610' + (' ' + body if body else ''))

    # ---- AAC ----
    aac = []
    ac = find_sec(secs, 'AAC')
    if ac:
        for l in ac[2]:
            l = l.strip()
            if l and not l.startswith('|'):
                aac.append(l)

    # ---- 行为支持卡 + 阈值 ----
    behavior_card, prog, reinf = {}, {}, []
    bc_sec = None
    for s in secs:
        if '行为干预支持卡' in s[1] or '行为支持卡' in s[1]:
            bc_sec = s
            break
    if bc_sec:
        tbls = table_blocks(bc_sec[2])
        for header, rows in tbls:
            if header and header[0] == '要素':
                behavior_card = kv_table(header, rows)
            elif header and header[0] == '情形':
                for r in rows:
                    if len(r) >= 3:
                        prog[r[0]] = r[1] + ' → ' + r[2]
    if '强化计划' in behavior_card:
        rp = behavior_card['强化计划']
        parts = re.split(r'→|->', rp)
        for i, p in enumerate(parts, 1):
            p = p.strip()
            if p:
                reinf.append({'课时': i, '强化方式': p,
                              '轮换清单': ['小星星贴纸', '口头赞美', '优先选择权']})

    # ---- 感官调节与环境安排 ----
    sensory = []
    sn_sec = None
    for s in secs:
        if '感官调节' in s[1]:
            sn_sec = s
            break
    if sn_sec:
        for header, rows in table_blocks(sn_sec[2]):
            if not header or header[0] != '感官/环境维度':
                continue
            for r in rows:
                if len(r) < 4 or not r[0]:
                    continue
                dim = ''
                for key, val in SENSORY_MAP:
                    if key in r[0]:
                        dim = val
                        break
                if not dim:
                    # Single Source 硬要求：md 的每一行都必须落到 JSON，禁在派生途中静默消失。
                    # 映射表未收录的维度按原值保留（去掉括号说明），让它在下游 schema
                    # 校验里显性报错（提示同步 enum），而不是无声蒸发。
                    dim = re.sub(r'（[^）]*）', '', r[0]).strip()
                sensory.append({'维度': dim, '触发信号': r[1], '前置安排': r[2], '降刺激通道': r[3]})

    # ---- IEP 累计追踪 ----
    iep = []
    iep_note = ''
    ie_sec = None
    for s in secs:
        if 'IEP' in s[1] and '追踪' in s[1]:
            ie_sec = s
            break
    if ie_sec:
        for l in ie_sec[2]:
            if '累计口径' in l:
                iep_note = l.strip().lstrip('> ').replace('累计口径：', '').strip()
        for header, rows in table_blocks(ie_sec[2]):
            if not header or '年度长期目标' not in ''.join(header):
                continue
            ix = {h: i for i, h in enumerate(header)}
            i_st = ix.get('学生', 0)
            i_year = next((i for i, h in enumerate(header) if '年度长期目标' in h), None)
            i_short = next((i for i, h in enumerate(header) if '本课短期目标' in h), None)
            reach_cols = [(re.search(r'课时(\d+)达成', h).group(1), i)
                          for i, h in enumerate(header) if re.search(r'课时(\d+)达成', h)]
            for r in rows:
                if len(r) <= i_st or not r[i_st].startswith('生'):
                    continue
                iep.append({
                    '学生代号': r[i_st],
                    '年度长期目标': r[i_year] if i_year is not None and len(r) > i_year else '',
                    '本课短期目标': r[i_short] if i_short is not None and len(r) > i_short else '',
                    '分课时达成': dict([(k, (r[i] if len(r) > i else '')) for k, i in reach_cols]),
                    '累计口径': iep_note,
                })

    # ---- 教材分析 / 学情分析（3.8.0；须 level=3 命中子小节，避开父章节标题）----
    textbook, learner = {}, {}
    tb_sec = find_sec(secs, '教材分析', level=3)
    if tb_sec:
        textbook = parse_bold_kv(tb_sec[2])
    la_sec = find_sec(secs, '学情分析', level=3)
    if la_sec:
        learner = parse_bold_kv(la_sec[2])

    # ---- 教学重难点（3.8.0；每课时三条，落在各课时目标矩阵小节内）----
    keypoints = {}
    for _, t, body in secs:
        idx = lesson_idx(t)
        if not idx:
            continue
        kv = parse_bold_kv(body)
        kp = dict([(k, v) for k, v in kv.items()
                   if k in ('教学重点', '教学难点', '突破策略')])
        if kp:
            keypoints[idx] = kp

    # ---- 人力协同与分工（3.8.0 教学资源要素：主教/助教/家长或陪读）----
    staffing = {}
    hc_sec = find_sec(secs, '人力协同', level=3)
    if hc_sec:
        for header, rows in table_blocks(hc_sec[2]):
            if not header or '角色' not in header[0]:
                continue
            for r in rows:
                if len(r) >= 2 and r[0]:
                    staffing[r[0].strip()] = r[1].strip()
        # 分工以项目符号表述（避免新增表格导致表号级联重排，见 3.8.0）
        staffing.update(parse_bold_kv(hc_sec[2]))

    # ---- 家长记录条（3.10.0 勾勾表制式：家长填写，四档行为锚定对齐 LOS）----
    home_note = {}
    hn_sec = find_sec(secs, '家长记录条', level=3)
    if hn_sec:
        body = hn_sec[2]
        opts = []
        for l in body:
            s = l.strip()
            if not s.startswith('\u2610'):
                continue
            # 五个档位常写在同一行（全角空格分隔）→ 按勾选框切分，逐档去空白
            for seg in s.split('\u2610'):
                seg = seg.strip().strip('\u3000').strip()
                if seg:
                    opts.append(seg)
        if opts:
            home_note['勾选档位'] = opts
        kv = parse_bold_kv(body)
        for k in ('分版与发放', '四档与课堂 LOS 对齐', '回填落点'):
            if k in kv:
                home_note[k] = kv[k]
        for l in body:
            s = l.strip()
            if s.startswith('**条首') and '**：' in s:
                home_note['条首'] = s.split('**：', 1)[1].strip()
            elif s.startswith('**条末') and '**：' in s:
                home_note['条末'] = s.split('**：', 1)[1].strip()
            elif s.startswith('题面：'):
                home_note['题面'] = s.split('：', 1)[1].strip()

    # ---- 组装 lessons ----
    lessons = []
    for i in range(1, n + 1):
        sc = sched[i - 1] if len(sched) >= i else {}
        mx = dict([(k, v) for k, v in matrices]).get(i, [])
        tl = timelines.get(i, [])
        hw = homework.get(i, {})
        lessons.append({
            '课时序号': i,
            '主题': sc.get('主题', '第%d课时' % i),
            '核心目标': sc.get('核心目标', ''),
            '生活化落点': sc.get('生活化落点', ''),
            'timeline': tl,
            '分钟合计校验': sum(x['分钟'] for x in tl),
            'objectives_matrix': mx,
            'inquiry_activities': inquiries.get(i, []),
            'board_layout': boards.get(i, ''),
            '重难点': keypoints.get(i, {}),
            '分层作业': {
                'A': hw.get('A', ''),
                'B': hw.get('B', ''),
                'C': hw.get('C', ''),
                '家长配合': '家校沟通渠道另行通知',
            },
        })

    return {
        'schema_version': ENGINE_VERSION,
        'meta': {
            '课题': title,
            '学科': meta_raw.get('学科', ''),
            '学段年级': '',
            '班级': cls,
            '授课日期': meta_raw.get('授课日期', '{{}}'),
            '执教者': meta_raw.get('执教者', '{{}}'),
            '课时数N': n,
            '课时研判': judge,
            '单课时时长分钟': dur,
            '课型': meta_raw.get('课型', ''),
            '教学方法': meta_raw.get('教学方法', ''),
            '教材分析': textbook,
            '学情分析': learner,
            '教材': {
                '版本': meta_raw.get('教材版本', textbook_note),
                '册次': '',
                '单元': meta_raw.get('课时定位', ''),
                '课': title,
                '确证状态': '未确证' if '未确证' in text else '未确证',
            },
        },
        'anchors': anchors,
        'lessons': lessons,
        'los_table': los_table,
        'support': {
            'aac': aac,
            'behavior_card': behavior_card,
            'reinforcement_schedule': reinf,
            'progression_rules': prog,
            '人力协同': staffing,
            '家长记录条': home_note,
        },
        'generalization': gen,
        'safety_alternatives': safety,
        'sensory_regulation': sensory,
        'iep_tracking': iep,
        'materials': materials,
        'placeholders': sorted(set(re.findall(r'\{\{([^}]*)\}\}', text))),
        'privacy': {
            'red_zone_free': True,
            '学生命名方式': '代号 生N',
            '待替换项来源': '见 md 源稿"附：待替换项与假设清单"',
        },
    }


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    outdir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(root, 'examples')
    wrote = []
    for f in sorted(glob.glob(os.path.join(root, 'examples', '*.md'))):
        text = open(f, encoding='utf-8').read()
        data = derive(text)
        name = '%s_结构化输出样例.json' % data['meta']['课题']
        p = os.path.join(outdir, name)
        # newline='\n'（3.15.0）：Windows 默认会把 '\n' 落成 CRLF，而 .gitattributes 已钉死
        # eol=lf —— 两边不一会导致每次派生后 git 显示"整份 JSON 全变"，且字节数与库中不一致。
        with open(p, 'w', encoding='utf-8', newline='\n') as _f:
            json.dump(data, _f, ensure_ascii=False, indent=2)
        wrote.append((name, len(json.dumps(data, ensure_ascii=False))))
    # 结果写盘（避免 stdout 编码问题）
    rep = ['派生完成：%d 个文件' % len(wrote)]
    for nm, sz in wrote:
        rep.append('  %s（%d 字符）' % (nm, sz))
    open(report_path('md_to_json_report.txt'), 'w', encoding='utf-8').write('\n'.join(rep))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        import traceback
        open(report_path('md_to_json_report.txt'), 'w',
             encoding='utf-8').write('ERROR:\n' + traceback.format_exc())
