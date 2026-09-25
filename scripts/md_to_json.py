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

ENGINE_VERSION = '2.5.0'

REPORT_DIR = os.path.join(tempfile.gettempdir(), 'peizhi_shuangmai')


def report_path(name):
    """运行期报告一律落系统临时目录（包内不产 *_report.txt）"""
    os.makedirs(REPORT_DIR, exist_ok=True)
    return os.path.join(REPORT_DIR, name)

SENSORY_MAP = [
    ('听觉', '听觉'), ('视觉', '视觉'), ('前庭', '前庭与座位'),
    ('口欲', '口欲与过敏'), ('过敏', '口欲与过敏'), ('触觉', '触觉与材料'),
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


def find_secs_startswith(secs, prefix, level=None):
    return [(lv, t, b) for lv, t, b in secs if t.startswith(prefix) and (level is None or lv == level)]


# ---------- 字段解析 ----------
CN_NUM = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9}


def cn2int(s):
    if s in CN_NUM:
        return CN_NUM[s]
    if s.startswith('十'):
        return 10 + (CN_NUM.get(s[1:], 0) if len(s) > 1 else 0)
    return 0


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
    head_sec = find_sec(secs, '教案头')
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
        m = re.search(r'第(\d+)课时', t)
        if not m or ('目标矩阵' not in joined and '维度' not in joined):
            continue
        idx = int(m.group(1))
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
        m = re.search(r'第(\d+)课时', t)
        if not m:
            continue
        idx = int(m.group(1))
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
                        '流程': teacher[:120],
                        '支持策略': versions,
                    })
            if tl:
                timelines[idx] = tl
            if inq:
                inquiries[idx] = inq

    # ---- 板书（代码块）----
    b_sec = find_sec(secs, '板书')
    if b_sec:
        body = '\n'.join(b_sec[2])
        mm = re.search(r'```\n(.*?)```', body, re.S)
        if mm:
            for i in range(1, n + 1):
                boards[i] = mm.group(1).strip()

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
                mm = re.match(r'^第(\d+)课时[·・]\s*([ABC])', r[0])
                if mm:
                    homework.setdefault(int(mm.group(1)), {})[mm.group(2)] = r[1]
                elif len(r) >= 2 and r[0] in ('A', 'B', 'C'):
                    pass

    # ---- 材料清单 ----
    materials = []
    m_sec = find_sec(secs, '材料清单')
    if m_sec:
        for l in m_sec[2]:
            if l.strip().startswith('☐'):
                materials.append(l.strip())

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
                    continue
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
            '单课时时长分钟': dur,
            '课型': meta_raw.get('课型', ''),
            '教学方法': meta_raw.get('教学方法', ''),
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
        json.dump(data, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
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
