# -*- coding: utf-8 -*-
"""反向变异测试（3.15.0 立，此前每轮临时手写、从未入库，验证不可复现）。

做什么：把**已修复的缺陷逐个注回**代码/源稿，确认回归能真的 FAIL（捕获），
再按原始字节还原。断言"看起来全绿"不等于有效——本项目已出现过五种"虚假的绿"，
其中最典型的一条是：缺陷被断言自身的写法保护（少一条数据，硬相等反而成立）。
只有"注回缺陷 ⇒ 断言变红"才证明这条断言在干活。

工程铁律（踩过坑的，勿删）：
 ① 一律 `try/finally` 兜底还原——中途抛错会把仓库留在变异态；
 ② 改 `.py` 必须 `sys.modules.pop(...)` 清模块缓存，否则断言仍在跑改之前的模块，
    得到一片**虚假的绿**（曾连跑 3 次才真捕获）；
 ③ 变异**必须注入到派生过程并让缺陷落进产物**：只改源稿 md 的守恒断言仍成立
    （md 与 JSON 同步减少，测不出派生丢失）；改了派生器就必须重跑 `md_to_json.py`，
    并把派生出的 examples/*.json 一并纳入还原集；
 ④ probes 跑**全量回归**（直接执行 regression_check.py 整体），
    漏面＝第四种虚假的绿；
 ⑤ 变异强度要够：注回的缺陷必须真的越界/真的丢数据，轻度变异会被判"未捕获"
    而误伤有效断言（本轮 M1 首版就因只加 93 字节未越界而假性未捕获）。

用法：python scripts/mutation_check.py
输出：%TEMP%/peizhi_shuangmai/mutation_report.txt（不进仓库）
"""
import os
import re
import sys
import subprocess
import tempfile

ENGINE_VERSION = '3.21.0'   # 与 SKILL.md frontmatter 同源，回归自动校验（3.19.0 起版本位由九处减为八处）

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
REPORT_DIR = os.path.join(tempfile.gettempdir(), 'peizhi_shuangmai')
REPORT = os.path.join(REPORT_DIR, 'mutation_report.txt')

SKILL = os.path.join(ROOT, 'SKILL.md')
MD_JSON = os.path.join(ROOT, 'scripts', 'md_to_json.py')
MD_DOCX = os.path.join(ROOT, 'scripts', 'md_to_docx.py')
REG = os.path.join(ROOT, 'scripts', 'regression_check.py')
SAMPLE = os.path.join(ROOT, 'examples', '好吃的水果_教学设计方案_3课时.md')
# 3.20.0：第二份基准样例此前**不在备份/还原集里**——变异只敢改好吃的水果，
# 认识5 一侧的缺陷无法用变异验证（"两份基准只验一份"＝第四种虚假的绿的温床）。
SAMPLE2 = os.path.join(ROOT, 'examples', '认识5_教学设计方案_2课时.md')
JSON1 = os.path.join(ROOT, 'examples', '好吃的水果_结构化输出样例.json')
JSON2 = os.path.join(ROOT, 'examples', '认识5_结构化输出样例.json')

# 所有可能被变异写坏的文件，一律纳入备份/还原集
CS = os.path.join(ROOT, 'references', 'curriculum-standards.md')

FILES = [SKILL, MD_JSON, MD_DOCX, REG, SAMPLE, SAMPLE2, JSON1, JSON2, CS]

out = []


def log(s=''):
    out.append(s)
    try:
        print(s)
    except Exception:
        pass


def read(p):
    return open(p, 'rb').read()


def write(p, b):
    open(p, 'wb').write(b)


def rederive():
    """重跑派生，让派生器的缺陷落进 examples/*.json（铁律③）。"""
    subprocess.run([PY, MD_JSON], cwd=ROOT, capture_output=True)


def clear_cache():
    for m in ('md_to_json', 'md_to_docx', 'regression_check'):
        sys.modules.pop(m, None)


def probes():
    """跑一次全量回归，返回 (总项数, FAIL 项列表)。"""
    subprocess.run([PY, os.path.join(ROOT, 'scripts', 'regression_check.py')],
                   cwd=ROOT, capture_output=True)
    rp = os.path.join(REPORT_DIR, 'regression_report.txt')
    if not os.path.exists(rp):
        return 0, ['(无回归报告)']
    txt = open(rp, encoding='utf-8', errors='replace').read()
    total = len([l for l in txt.splitlines() if '[PASS]' in l or '[FAIL]' in l])
    fails = [l.strip().replace('[FAIL]', '').strip() for l in txt.splitlines() if '[FAIL]' in l]
    return total, fails


def run_case(name, why, mutate, keyword, negative=False):
    """negative=False：期望出现含 keyword 的 FAIL（缺陷被捕获）。
       negative=True ：期望**不出现**该 FAIL（用于证明旧写法确实漏判，做对照）。"""
    orig = {p: read(p) for p in FILES if os.path.exists(p)}
    ok, detail = False, ''
    try:
        mutate()
        clear_cache()
        _n, fails = probes()
        hit = [f for f in fails if keyword in f]
        ok = (not hit) if negative else bool(hit)
        if negative:
            detail = ('对照成立：旧写法确实漏判（%d 项全绿）' % _n) if ok else \
                     ('意外捕获：' + '；'.join(hit[:2]))
        else:
            detail = ('捕获：' + '；'.join(hit[:3])) if ok else \
                     ('未捕获（回归仍全绿，共 %d 项）——该断言是装饰性的' % _n)
    except Exception as e:
        detail = '变异执行异常：%s' % str(e)[:90]
    finally:
        for p, b in orig.items():
            if os.path.exists(p):
                write(p, b)
        clear_cache()
    tag = ('对照' if negative else ('捕获' if ok else '未捕获'))
    log('  [%s] %s' % (tag, name))
    log('        缺陷：%s' % why)
    log('        结果：%s' % detail)
    log()
    return ok


def main():
    os.makedirs(REPORT_DIR, exist_ok=True)
    log('反向变异测试 · 引擎 %s' % _engine_ver())
    log('=' * 64)
    log()

    results = []

    # ── M1 主文件换行膨胀导致体积越界（本轮 P0）─────────────────────
    # 先把 SKILL.md 垫到 3.14.0 的真实尺寸（LF 12270），再整篇转 CRLF：
    # 字节数 +行数 → 越过 12288。旧断言用文本模式读（universal newlines 归一回 LF），
    # 算出 12270 判 PASS；新断言按落盘字节判定，应 FAIL。
    def _pad_to(target=12270):
        """垫到指定字节数。填充一律用 ASCII（bytes 字面量不可含非 ASCII，
        且截断绝不能落在多字节汉字中间，否则回归读文件即 UnicodeDecodeError）。"""
        b = read(SKILL)
        need = target - len(b)
        if need > 0:
            tag, tail = b'\n<!-- pad ', b' -->'
            assert need > len(tag) + len(tail), '填充量不足以构成一行'
            b = b + tag + b'x' * (need - len(tag) - len(tail)) + tail
            write(SKILL, b)
        return len(read(SKILL))

    def m1():
        n = _pad_to()
        assert n == 12270, '垫字节失败：%d' % n
        b = read(SKILL)
        write(SKILL, b.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n'))
    results.append(run_case(
        'M1 SKILL.md 换行膨胀为 CRLF（体积口径失真）',
        '断言用文本模式读，CRLF 被归一化，12KB 铁律在上传轨越界却判 PASS',
        m1, '体积≤12KB'))

    def m1b():
        m1()   # 同样的膨胀
        # 同时把断言退回旧写法（文本模式 → 换行被归一化）
        t = read(REG).decode('utf-8')
        assert "size = len(open(p, 'rb').read())" in t
        write(REG, t.replace("size = len(open(p, 'rb').read())",
                             "size = len(text.encode('utf-8'))").encode('utf-8'))
    results.append(run_case(
        'M1b 对照：断言退回文本模式读取（旧写法）',
        '同一份超限文件，旧口径算出 12270 → 漏判；此例期望"不捕获"以证明确有漏判',
        m1b, '体积≤12KB', negative=True))

    # ── M2 板书回退「取第一个复制全部课时」（本轮 P0）──────────────
    def m2():
        t = read(MD_JSON).decode('utf-8')
        i = t.index("    b_sec = find_sec(secs, '板书')")
        j = t.index("    # ---- LOS 记录表 ----")
        legacy = ("    b_sec = find_sec(secs, '板书')\n"
                  "    if b_sec:\n"
                  "        body = '\\n'.join(b_sec[2])\n"
                  "        mm = re.search(r'```\\n(.*?)```', body, re.S)\n"
                  "        if mm:\n"
                  "            for i in range(1, n + 1):\n"
                  "                boards[i] = mm.group(1).strip()\n\n")
        write(MD_JSON, (t[:i] + legacy + t[j:]).encode('utf-8'))
        rederive()
    results.append(run_case(
        'M2 板书回退为「取第一个代码块复制全部课时」',
        '三课时共用一块板书，domain-core「每课时独立板书」被无声违反且不报错',
        m2, '板书互不相同'))

    # ── M3 探究流程回退固定窗口截断 ────────────────────────────────
    # 变异须够狠：样例探究行的教师活动列只有 60~80 字，[:120] 压根截不到，
    # 于是"未捕获"会被误读成断言无效。此处用 [:40] —— 与 [:120] 同属"固定窗口截断"，
    # 只是必然生效，用来验证守恒断言确实拦得住这一类缺陷。
    def m3():
        t = read(MD_JSON).decode('utf-8')
        assert "'流程': teacher," in t
        write(MD_JSON, t.replace("'流程': teacher,", "'流程': teacher[:40],").encode('utf-8'))
        rederive()
    results.append(run_case(
        'M3 探究流程回退固定窗口截断（[:40]，[:120] 的必然生效形态）',
        'JSON 侧探究流程永远缺尾巴，且是本项目反复出事的老写法',
        m3, '探究流程与源稿逐字相等'))

    # ── M4 课时标题解析回退半角数字 ────────────────────────────────
    def m4():
        t = read(MD_JSON).decode('utf-8')
        assert "m = _LESSON_NUM_RE.search(title or '')" in t
        write(MD_JSON, t.replace("m = _LESSON_NUM_RE.search(title or '')",
                                 "m = re.search(r'第(\\\\d+)课时', title or '')").encode('utf-8'))
        rederive()
    results.append(run_case(
        'M4 课时序号解析回退为只认半角阿拉伯数字',
        '教师写「第一课时」时该课时 timeline 与目标矩阵全被静默丢弃',
        m4, '守恒'))

    # ── M5 感官未知维度重新「静默丢弃」─────────────────────────────
    # 注意：3.13.0 的"未知维度兜底保留"已让"删映射表"不再丢数据（那是修复生效的证据），
    # 故此处注入的是真正的丢弃行为——把兜底改回 continue。
    def m5():
        t = read(MD_JSON).decode('utf-8')
        old = "                    dim = re.sub(r'（[^）]*）', '', r[0]).strip()"
        assert old in t
        write(MD_JSON, t.replace(old, "                    continue").encode('utf-8'))
        # 光改 continue 不够：样例六个维度全在映射表里，continue 永远走不到。
        # 必须同时在源稿感官表加一个**映射表未收录**的维度行，缺陷才会真的丢数据。
        s = read(SAMPLE).decode('utf-8')
        i = s.index('| 嗅觉')
        j = s.index('\n', i)
        write(SAMPLE, (s[:j + 1] + '| 温度觉（变异注入的未知维度） | 室温骤变时烦躁 | 课前固定室温 | 加一件外套 |\n'
                       + s[j + 1:]).encode('utf-8'))
        rederive()
    results.append(run_case(
        'M5 感官未知维度回退为静默丢弃（continue）',
        '丢的是气味过敏这类安全项；旧断言 set==五维 硬相等恰恰因此成立',
        m5, '感官'))

    # ── M6 Gate-A 块取段回退固定窗口 ───────────────────────────────
    def m6():
        t = read(REG).decode('utf-8')
        assert "_gb = para_block(_md2, 'Gate-A 确认记录')" in t
        write(REG, t.replace("_gb = para_block(_md2, 'Gate-A 确认记录')",
                             "_gb = _md2.split('Gate-A 确认记录', 1)[1][:1200]").encode('utf-8'))
        s = read(SAMPLE).decode('utf-8')
        i = s.index('- **确认事项**：')
        j = s.index('\n', i)
        # 填充须够长：首版只加约 800 字，四要素仍在 1200 窗口内，于是"未捕获"是假的
        pad = '（变异填充：' + '这段说明用于把后续要素挤出固定窗口之外。' * 90 + '）'
        write(SAMPLE, (s[:j] + pad + s[j:]).encode('utf-8'))
    results.append(run_case(
        'M6 Gate-A 块取段回退固定 1200 字符窗口',
        '窗口外的要素被切走 → 内容完好却误报 FAIL（注释明令禁止却在用）',
        m6, 'Gate-A块含四要素'))

    # ── M7 主文件撑到体积越界（12KB 硬闸的最后一道防线）──────────────
    # 3.19.0 废止打包轨前，这条由"打包器拒绝出包"兜底；打包器删除后，兜底职责
    # 落到回归的**落盘字节**断言上。若它失效，细则会悄悄回流进路由层且无人报警——
    # 故本用例不得随打包器一并删除，只是验证对象从打包器换成回归断言。
    def m7():
        write(SKILL, read(SKILL) + b'\n' + ('fill' * 800).encode('utf-8'))
    results.append(run_case(
        'M7 主文件膨胀到越界（3.19.0 起由回归体积断言兜底）',
        '12KB 是渐进式披露硬闸；打包器删除后若这条断言也不灵，细则回流将毫无阻拦',
        m7, 'SKILL.md 体积≤12KB'))

    # ===== 3.16.0 新增：课标错引（用户实测"备课美术"被引向普校＋聋校拼凑）=====
    # 变异强度核对：注入必须是**真替换**（不是追加），否则原文仍在、白名单与
    # "书名与学科一致"两条会因"真书还在"而放过去，得到"变异太轻"的假性未捕获。
    _BOOK = '《培智学校义务教育生活语文课程标准（2016年版）》'

    def m8():
        t = read(SAMPLE).decode('utf-8')
        assert _BOOK in t
        write(SAMPLE, t.replace(_BOOK, '《聋校义务教育美术课程标准》').encode('utf-8'))
        rederive()
    results.append(run_case(
        'M8 课标错引·换成聋校课标（"美术"实测拼凑源之一）',
        '培智无"美术"这门课，正式科目是绘画与手工；不拦就会顺别名滑向聋校/普校课标',
        m8, '未引用普校2022版/聋校/盲校课标'))

    def m9():
        t = read(SAMPLE).decode('utf-8')
        assert _BOOK in t
        write(SAMPLE, t.replace(_BOOK, '《义务教育艺术课程标准（2022年版）》').encode('utf-8'))
        rederive()
    results.append(run_case(
        'M9 课标错引·套用普校2022版课标',
        '2022 年版是普通学校课标，不可套用于培智学校——这是混淆的头号源头',
        m9, '未引用普校2022版/聋校/盲校课标'))

    def m10():
        t = read(SAMPLE).decode('utf-8')
        assert '| 学科 | 生活语文 |' in t
        write(SAMPLE, t.replace('| 学科 | 生活语文 |', '| 学科 | 美术 |').encode('utf-8'))
        rederive()
    results.append(run_case(
        'M10 教案信息学科写成别名"美术"且未留对齐凭证',
        '学科名不落培智10门＝后续课标引用必然走偏；别名命中还须留"对齐为"凭证',
        m10, '教案信息学科属培智10门课'))

    def m11():
        t = read(SAMPLE).decode('utf-8')
        assert '- 倾听与说话 ｜' in t
        write(SAMPLE, t.replace('- 倾听与说话 ｜', '- 课程总目标 ｜', 1).encode('utf-8'))
        rederive()
    results.append(run_case(
        'M11 锚点第一级用课标篇章名（课程总目标）',
        '认识5 曾把「课程总目标」「教学建议」当锚点一级；篇章名不能充当教学目标依据',
        m11, '锚点第一级非课标篇章名'))

    def m12():
        # 整段摘掉 3.16.0 新增的课标断言，回到"只验锚点里「·」≥2"的旧写法
        t = read(REG).decode('utf-8')
        i = t.index('    # ===== 3.16.0 新增：课标引用口径')
        j = t.index('    return name, r', i)
        write(REG, (t[:i] + t[j:]).encode('utf-8'))
        s = read(SAMPLE).decode('utf-8')
        assert _BOOK in s
        write(SAMPLE, s.replace(_BOOK, '《义务教育艺术课程标准（2022年版）》').encode('utf-8'))
        rederive()
    results.append(run_case(
        'M12 对照：摘掉课标断言、退回只验锚点格式的旧写法',
        '反证新增的书名白名单/黑名单确实在干活：摘掉后再注假课标，回归应重新变绿（＝漏判）',
        m12, '未引用普校2022版/聋校/盲校课标', negative=True))

    # ── M13 课标口径漂移：细则里删掉「绘画与手工」整行 ──────────────────
    # 守恒（不是枚举）的意义：只要细则少记一门，代码表就再也拦不住该科的错引，
    # 而两边都不会报错。故"细则→代码"这一侧也必须能变红。
    def m13():
        t = read(CS).decode('utf-8')
        rows = [l for l in t.split('\n') if l.startswith('| 6 |') and '绘画与手工' in l]
        assert rows, '未定位到绘画与手工行'
        write(CS, t.replace(rows[0] + '\n', '').encode('utf-8'))
    results.append(run_case(
        'M13 课标索引漏记「绘画与手工」（口径双向守恒）',
        '细则少一门 ⇒ 该科错引再也拦不住，且两侧均静默——守恒断言必须当场变红',
        m13, '课标索引科目表'))

    # ── M14 教案信息课标锚点退化为"只写学段＋详见…节"（3.17.0 前的旧写法）────
    # 3.17.0 把正式信息源从被删的归档视图回并到教案信息，最典型的退化就是
    # 又写成"第一学段（详见……节）"——三级全文重新落到别处、教务翻第一页只看到学段。
    def m14():
        t = read(SAMPLE).decode('utf-8')
        m = re.search(r'\|\s*课标锚点\s*\|\s*([^|]+?)\s*\|', t)
        assert m, '未定位到课标锚点行'
        write(SAMPLE, t.replace(
            m.group(0), '| 课标锚点 | 《培智学校义务教育生活语文课程标准（2016年版）》低年级段（详见「课标锚点、教材分析与学情分析」节） |').encode('utf-8'))
        rederive()
    results.append(run_case(
        'M14 教案信息课标锚点退化为只写学段+详见（3.17.0 前的残缺写法）',
        '简式若退回"低年级段（详见…节）"——无领域名无指引，第一页等于只看得到学段',
        m14, '教案信息课标锚点禁只写学段'))

    # ── M15 复活已废止的「教务归档视图」（半截改名的典型残留）──────────────
    # 改名/删节最怕留下半截：细则已改三视图，样例里却还留着归档节。
    # 届时引擎照旧产出一节没人维护的孤儿内容，且无任何断言报错。
    def m15():
        t = read(SAMPLE).decode('utf-8')
        assert '## 二、课标锚点' in t
        write(SAMPLE, t.replace(
            '## 二、课标锚点',
            '## 二、教务归档视图（正式归档，不含假设与批注）\n\n占位。\n\n## 三、课标锚点', 1).encode('utf-8'))
        rederive()
    results.append(run_case(
        'M15 复活已废止的「教务归档视图」（防半截改名残留）',
        '3.17.0 已废止该节；若样例里偷偷复活，元断言必须当场变红而不是静默放行',
        m15, '在效条文无"教务归档'))

    # ── M16 课题列回到"《课题》（册次·单元·课次）"（3.18.0 前的重合写法）────
    # 最典型的退化：写课题顺手把册次带上。两列各写一遍册次＝两份须人工同步的副本。
    def m16():
        t = read(SAMPLE).decode('utf-8')
        m = re.search(r'\|\s*课题\s*\|\s*([^|]+?)\s*\|', t)
        assert m, '未定位到课题行'
        write(SAMPLE, t.replace(
            m.group(0), '| 课题 | 《好吃的水果》（人教版培智《生活语文》二年级上册·第二单元“个人生活”·第4课） |').encode('utf-8'))
        rederive()
    results.append(run_case(
        'M16 课题列带册次括号后缀（与教材版本列重合）',
        '同一册次写两遍＝两份副本，改一处漏一处；教务核对时两处不一致无从判断谁对',
        m16, '教案信息课题列只写《课题》本身'))

    # ── M17 教材版本只写册次、单元课次被课题列"代写"而丢失 ─────────────────
    # 合并字段时最常见的漏：只删了课题列的括号，忘了把单元课次补进教材版本列。
    def m17():
        t = read(SAMPLE).decode('utf-8')
        m = re.search(r'\|\s*教材版本\s*\|\s*([^|]+?)\s*\|', t)
        assert m, '未定位到教材版本行'
        write(SAMPLE, t.replace(
            m.group(0), '| 教材版本 | 人民教育出版社《生活语文》二年级上册（培智学校义务教育实验教科书），已核证 |').encode('utf-8'))
        rederive()
    results.append(run_case(
        'M17 教材版本列漏掉单元与课次（合并时只删未补）',
        '单元课次是本课定位的正式信息，删了课题列括号却不补进教材版本＝信息丢失',
        m17, '教案信息教材版本含册次与单元课次'))

    # ── M18 感官表删掉"未使用"的嗅觉行（3.20.0 前的"不必硬凑"口径）────────
    # 变异刻意打在**不用"闻"的认识5**上：旧口径下"未用到的维度不必硬凑"，
    # 删行完全合法、旧断言「用闻则含嗅觉」根本不会触发——这正是旧口径的漏洞本身。
    def m18():
        t = read(SAMPLE2).decode('utf-8')
        lines = t.split('\n')
        keep = [l for l in lines if not l.startswith('| 嗅觉')]
        assert len(keep) == len(lines) - 1, '未定位到嗅觉行'
        write(SAMPLE2, '\n'.join(keep).encode('utf-8'))
        rederive()
    results.append(run_case(
        'M18 感官表删掉"本课未使用"的嗅觉行（六维恒列）',
        '删行后教师无从判断是"本课不需要"还是"漏了"；且触发源来自环境气味，不只来自教学环节',
        m18, '感官六维恒列齐全'))

    # ── M19 LOS 表起始列预填（证据归属越位）────────────────────────────
    def m19():
        t = read(SAMPLE).decode('utf-8')
        m = re.search(r'(### LOS 变化记录表\n)(.*?)(?=\n### |\Z)', t, re.S)
        assert m, '未定位到 LOS 表'
        body = m.group(2)
        nb = []
        for ln in body.split('\n'):
            if ln.startswith('| 生'):
                cs = ln.strip().strip('|').split('|')
                for i in range(1, len(cs) - 1, 2):
                    cs[i] = ' I '
                ln = '| ' + ' | '.join(c.strip() for c in cs) + ' |'
            nb.append(ln)
        write(SAMPLE, (t[:m.start(2)] + '\n'.join(nb) + t[m.end(2):]).encode('utf-8'))
        rederive()
    results.append(run_case(
        'M19 LOS 表起始列预填预设档',
        '起始 LOS 由 P前 前测实测确定；预填＝教师照抄预设、前测沦为走过场（证据归属越位）',
        m19, 'LOS表起始列禁预填'))

    # ── M20 分层系数不按三档定档（自取"上限"）──────────────────────────
    # 只改系数取值、不动测算式，专测定档断言是否被架空。
    def m20():
        t = read(SAMPLE).decode('utf-8')
        m = re.search(r'\|\s*分层系数\s*\|\s*([^|]+?)\s*\|', t)
        assert m, '未定位到分层系数行'
        write(SAMPLE, t.replace(
            m.group(0), '| 分层系数 | 1.3（C层占比 4/12＝33.3%，取上限） |').encode('utf-8'))
        rederive()
    results.append(run_case(
        'M20 分层系数不按C层占比三档定档（自取上限）',
        '原条文只给上限触发条件、中档无据可依；不定档则测算值可被随意调高调低，出口判定随之摇摆',
        m20, '分层系数按C层占比三档定档'))

    # ── M21 家校反馈删掉"家庭可用的行为一致性做法" ─────────────────────
    def m21():
        t = read(SAMPLE).decode('utf-8')
        i = t.find('**家校一致的一件小事**')
        assert i > 0, '未定位到一致性做法段'
        j = t.find('\n\n', i)
        write(SAMPLE, (t[:i] + t[j + 2:]).encode('utf-8'))
        rederive()
    results.append(run_case(
        'M21 家校反馈删掉家庭可用的行为一致性做法',
        'workflow 硬性要求附 1 条；缺失则家校两张皮，课堂上的替代行为在家得不到延续',
        m21, '家校反馈附1条家庭可用的行为一致性做法'))

    # ── M22 课标索引**自己的示范表**锚点退回"只写学段＋详见…节" ──────────
    # M14 只守住 examples/，守不住 references/ 的示范——3.20.0 前此处正是退化写法。
    def m22():
        t = read(CS).decode('utf-8')
        m = re.search(r'\|\s*课标锚点\s*\|\s*([^|]+?)\s*\|', t)
        assert m, '未定位到示范表课标锚点行'
        write(CS, t.replace(
            m.group(0),
            '| 课标锚点 | 《培智学校义务教育绘画与手工课程标准（2016年版）》第一学段（1~3年级）（详见「课标锚点、教材分析与学情分析」节） |').encode('utf-8'))
    results.append(run_case(
        'M22 课标索引示范表锚点退化为只写学段+详见（校验盲区）',
        '示范件违反自己声明的规则比没有示范更坏——引擎与教师都照抄它，而校验只扫交付样例',
        m22, '课标索引示范表锚点须三级全文'))

    # ── M23 课时时间轴只给时间、不给 LOS 分组任务 ───────────────────────
    def m23():
        t = read(SAMPLE).decode('utf-8')
        i = t.find('**各段 LOS 分组任务**')
        assert i > 0, '未定位到 LOS 分组任务段'
        j = t.find('\n\n', i)
        write(SAMPLE, (t[:i] + t[j + 2:]).encode('utf-8'))
        rederive()
    results.append(run_case(
        'M23 课时时间轴缺 LOS 分组任务',
        'workflow 环节 4 要求时间轴分段标注时间／活动（含步别）／LOS 分组任务；缺 LOS 则助教无从按段切换支持',
        m23, '课时时间轴含时间＋步别＋LOS分组任务'))

    # ── M24 教案信息表行回抄三级全文（3.21.0 前的重复写法）────────────────
    # 3.17.0~3.20.0 表内抄全文：与正文分析节同批锚点两份副本（同课题列病根）。
    # 本版改简式后，此变异防"全文回抄"式回流——引号原文条目一进表内即 FAIL。
    def m24():
        t = read(SAMPLE).decode('utf-8')
        m = re.search(r'\|\s*课标锚点\s*\|\s*([^|]+?)\s*\|', t)
        assert m, '未定位到课标锚点行'
        write(SAMPLE, t.replace(
            m.group(0), '| 课标锚点 | 《培智学校义务教育生活语文课程标准（2016年版）》· 识字与写字 · 低年级段（1~3年级）· “认读生活中常用汉字10～50个”；“能用铅笔描写或抄写生活中常用汉字”；· 倾听与说话 · 低年级段 · “能听懂常用的词语，并作出适当回应”（完整锚点见「课标锚点、教材分析与学情分析」节） |').encode('utf-8'))
        rederive()
    results.append(run_case(
        'M24 教案信息表行回抄三级全文（3.21.0 前的重复写法）',
        '表内与正文各一份全文＝两份须人工同步的副本（与 3.18.0 课题列同病根）；简式口径下引号原文一进表内须当场变红',
        m24, '教案信息课标锚点禁抄录原文条目'))

    total, caught = len(results), sum(1 for x in results if x)
    log('=' * 64)
    log('反向变异：%d/%d 通过' % (caught, total))
    log('（"未捕获"＝该断言是装饰性的，缺陷回归也照绿；"对照"用例则期望旧写法漏判）')
    open(REPORT, 'w', encoding='utf-8', newline='\n').write('\n'.join(out))
    return 0 if caught == total else 1


def _engine_ver():
    m = re.search(r'^version: (.+)$', read(SKILL).decode('utf-8', 'replace'), re.M)
    return m.group(1).strip() if m else '?'


if __name__ == '__main__':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    sys.exit(main())
