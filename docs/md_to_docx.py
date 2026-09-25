# -*- coding: utf-8 -*-
"""教案 md 源稿 → Word(.docx) 成品生成器（零依赖，纯标准库写出 OOXML）。

定位：把 SKILL.md §4「成品格式基线」从**文本描述升级为可执行代码**，
      消除"不同 LLM 生成 Word 时版式不一致"的最后一公里漂移。

设计约束：
  1. 零第三方依赖（仅 zipfile/re/xml），任意 Python 3.8+ 可跑，跨平台，
     不依赖 Word/WPS 安装。
  2. **字节级幂等**：同一 md 输入 → 恒定相同 bytes（zip 时间戳固定、
     rId 顺序确定、无随机序），支持 --check 校验已交付 docx 是否被改动。
  3. **红区零输出**：落盘前做红区扫描（身份证/手机号/长数字串），
     命中即拒绝生成——护栏由代码强制，而非仅靠提示词自觉。
  4. 忠实 Single Source：docx 与 JSON 同源于 md，禁止手改 docx。

用法：
  python docs/md_to_docx.py                 # 输出到 examples/
  python docs/md_to_docx.py <输出目录>      # 指定输出目录
  python docs/md_to_docx.py <输出目录> --check   # 校验已交付 docx 与源稿是否一致
输出：<课题>_教学设计方案_N课时.docx + docs/md_to_docx_report.txt
"""
import re
import os
import sys
import glob
import json
import zipfile
import hashlib
import datetime

ENGINE_VERSION = '2.4.0'

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
CT = 'http://schemas.openxmlformats.org/package/2006/content-types'
PR = 'http://schemas.openxmlformats.org/package/2006/relationships'

# A4 纵向 twips（1cm = 567twips）；页边距按 §4：上下 2.54cm、左右 3.18cm
PAGE_W, PAGE_H = 11906, 16840
MARGIN_TB, MARGIN_LR = 1440, 1803
BODY_W = PAGE_W - 2 * MARGIN_LR          # 8300 twips 可用版心
ZIP_STAMP = (2020, 1, 1, 0, 0, 0)        # 固定时间戳 → 字节幂等

# ---------- 红区扫描（与引擎铁律 1 一致） ----------
RED_RULES = [
    ('疑似身份证', re.compile(r'\d{17}[\dXx]')),
    ('疑似手机号', re.compile(r'(?<!\d)1[3-9]\d{9}(?!\d)')),
    ('长数字串', re.compile(r'\d{11,}')),
    ('疑似病历号', re.compile(r'(病历|住院号|诊断书)[^\n]{0,10}\d{4,}')),
]


def red_scan(text):
    hits = [n for n, r in RED_RULES if r.search(text)]
    return hits


# ---------- XML 工具 ----------
def esc(s):
    return (s.replace('&', '&amp;').replace('<', '&lt;')
             .replace('>', '&gt;').replace('"', '&quot;'))


def rpr(sz=None, bold=None, ea=None, west=None, fill=None):
    p = []
    if ea or west:
        p.append('<w:rFonts w:ascii="%s" w:hAnsi="%s" w:eastAsia="%s" w:cs="%s"/>' % (
            west or 'Times New Roman', west or 'Times New Roman',
            ea or '宋体', west or 'Times New Roman'))
    if bold:
        p.append('<w:b/><w:bCs/>')
    if sz:
        p.append('<w:sz w:val="%d"/><w:szCs w:val="%d"/>' % (sz, sz))
    if fill:
        p.append('<w:shd w:val="clear" w:color="auto" w:fill="%s"/>' % fill)
    return '<w:rPr>%s</w:rPr>' % ''.join(p) if p else ''


BOLD_RE = re.compile(r'\*\*(.+?)\*\*')


def runs(text, sz=None, bold=None, ea=None, west=None):
    """行内 **加粗** 解析 → rPr 分段"""
    out, pos = [], 0
    for m in BOLD_RE.finditer(text):
        pre = text[pos:m.start()]
        if pre:
            out.append('<w:r>%s<w:t xml:space="preserve">%s</w:t></w:r>' % (rpr(sz, bold, ea, west), esc(pre)))
        out.append('<w:r>%s<w:t xml:space="preserve">%s</w:t></w:r>' % (rpr(sz, True, ea, west), esc(m.group(1))))
        pos = m.end()
    tail = text[pos:]
    if tail:
        out.append('<w:r>%s<w:t xml:space="preserve">%s</w:t></w:r>' % (rpr(sz, bold, ea, west), esc(tail)))
    if not out:
        out.append('<w:r>%s<w:t xml:space="preserve"></w:t></w:r>' % rpr(sz, bold, ea, west))
    return ''.join(out)


def ppr(align=None, style=None, left=None, hang=None, first_chars=None,
        before=None, after=None, line=None, keep_next=False, fill=None):
    p = []
    if style:
        p.append('<w:pStyle w:val="%s"/>' % style)
    if keep_next:
        p.append('<w:keepNext/>')
    if fill:      # CT_PPr 序列：shd 在 spacing / ind / jc 之前
        p.append('<w:shd w:val="clear" w:color="auto" w:fill="%s"/>' % fill)
    sp = []
    if before is not None:
        sp.append('w:before="%d"' % before)
    if after is not None:
        sp.append('w:after="%d"' % after)
    if line is not None:
        sp.append('w:line="%d" w:lineRule="auto"' % line)
    if sp:
        p.append('<w:spacing %s/>' % ' '.join(sp))
    if left is not None or hang is not None or first_chars is not None:
        p.append('<w:ind %s/>' % ' '.join(filter(None, [
            ('w:left="%d"' % left) if left is not None else '',
            ('w:hanging="%d"' % hang) if hang is not None else '',
            ('w:firstLineChars="%d"' % first_chars) if first_chars is not None else ''])))
    if align:
        p.append('<w:jc w:val="%s"/>' % align)
    return '<w:pPr>%s</w:pPr>' % ''.join(p) if p else ''


def para(text='', align=None, style=None, sz=None, bold=None, ea=None, west=None,
         left=None, hang=None, first_chars=None, before=None, after=None,
         line=None, keep_next=False, fill=None):
    return '<w:p>%s%s</w:p>' % (
        ppr(align, style, left, hang, first_chars, before, after, line, keep_next, fill),
        runs(text, sz, bold, ea, west))


# ---------- 列宽策略（§4 五列表比例 + 常见表型） ----------
def col_widths(ncols, header):
    h0 = header[0] if header else ''
    joined = ''.join(header)
    if ncols == 5 and h0 == '教学环节':
        return [14, 26, 20, 24, 16]
    if ncols == 2 and h0 == '项目':
        return [22, 78]
    if ncols == 2:
        return [28, 72]
    if ncols == 3 and '风险' in joined:
        return [22, 24, 54]
    if ncols == 3:
        return [20, 30, 50]
    if h0 == '学生':
        rest = 88.0 / (ncols - 1)
        return [12] + [round(rest, 2)] * (ncols - 1)
    return [round(100.0 / ncols, 2)] * ncols


SEP_ROW = re.compile(r'^[\s\-:|]+$')


def is_sep(row):
    return bool(SEP_ROW.match(row.replace('|', '').strip()))


def cells(row):
    return [c.strip() for c in row.strip().strip('|').split('|')]


def table_xml(lines):
    rows = [cells(l) for l in lines if not is_sep(l) and l.strip()]
    if not rows:
        return ''
    ncols = max(len(r) for r in rows)
    rows = [r + [''] * (ncols - len(r)) for r in rows]
    header, body = rows[0], rows[1:]
    ws = col_widths(ncols, header)
    tw = [int(BODY_W * w / 100.0) for w in ws]
    tw[-1] = BODY_W - sum(tw[:-1])            # 尾差归末列，保证合计=版心
    grid = ''.join('<w:gridCol w:w="%d"/>' % w for w in tw)
    borders = ''.join('<w:%s w:val="single" w:sz="4" w:space="0" w:color="auto"/>' % s
                      for s in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'))
    # CT_TblPrBase 序列：tblW → jc → tblBorders → shd → tblLayout → tblCellMar → tblLook
    tblpr = ('<w:tblPr><w:tblW w:w="5000" w:type="pct"/><w:jc w:val="center"/>'
             '<w:tblBorders>%s</w:tblBorders>'
             '<w:tblLayout w:type="fixed"/>'
             '<w:tblCellMar><w:top w:w="40" w:type="dxa"/><w:left w:w="80" w:type="dxa"/>'
             '<w:bottom w:w="40" w:type="dxa"/><w:right w:w="80" w:type="dxa"/></w:tblCellMar>'
             '</w:tblPr>' % borders)

    def tc(txt, w, is_header=False):
        fill = '<w:shd w:val="clear" w:color="auto" w:fill="F2F2F2"/>' if is_header else ''
        return ('<w:tc><w:tcPr><w:tcW w:w="%d" w:type="dxa"/>%s<w:vAlign w:val="center"/></w:tcPr>'
                '<w:p>%s%s</w:p></w:tc>' % (
                    w, fill,
                    ppr(align='center' if is_header else 'left', line=240),
                    runs(txt, 18, is_header, '宋体')))   # 18 半点 = 9pt ≥ 小五基线

    out = ['<w:tbl>', tblpr, '<w:tblGrid>%s</w:tblGrid>' % grid]
    # CT_TrPr 序列：cantSplit 在 tblHeader 之前
    out.append('<w:tr><w:trPr><w:cantSplit/><w:tblHeader/></w:trPr>%s</w:tr>'
               % ''.join(tc(c, tw[i], True) for i, c in enumerate(header)))
    for r in body:
        out.append('<w:tr>%s</w:tr>' % ''.join(tc(c, tw[i]) for i, c in enumerate(r)))
    out.append('</w:tbl>')
    # 表后留一个空段落，避免表格成为文档最后一个元素导致 Word 报错
    out.append(para('', after=0))
    return ''.join(out)


def code_xml(text):
    """板书版式代码块：等宽＋浅底＋保留空格"""
    lines = text.split('\n')
    out = []
    for i, l in enumerate(lines):
        body = '<w:r>%s<w:t xml:space="preserve">%s</w:t></w:r>' % (
            rpr(21, False, '宋体', 'Consolas'), esc(l)) if l else '<w:r>%s</w:r>' % rpr(21, False, '宋体', 'Consolas')
        out.append('<w:p>%s%s</w:p>' % (ppr(None, None, 240, None, None, None, 0, 240, False, 'F7F7F7'), body))
    return ''.join(out)


# ---------- md 解析 ----------
def flush(buf, blocks):
    text = ''.join(buf).strip()
    if not text:
        return
    m = re.match(r'^\*\*(.+?)\*\*$', text)
    if m:
        blocks.append(('caption', m.group(1).strip()))
    else:
        blocks.append(('p', text))


def parse_md(text):
    lines = text.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    i, cover, blocks = 0, [], []
    while i < len(lines) and lines[i].startswith('# '):
        cover.append(lines[i][2:].strip())
        i += 1
    buf = []
    while i < len(lines):
        s = lines[i].strip()
        if s.startswith('```'):
            flush(buf, blocks)
            buf = []
            j, code = i + 1, []
            while j < len(lines) and not lines[j].strip().startswith('```'):
                code.append(lines[j].rstrip())
                j += 1
            blocks.append(('code', '\n'.join(code)))
            i = j + 1
            continue
        if s.startswith('|'):
            flush(buf, blocks)
            buf = []
            tbl = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                tbl.append(lines[i].strip())
                i += 1
            blocks.append(('table', tbl))
            continue
        m = re.match(r'^(#{1,6}) +(.+)$', s)
        if m:
            flush(buf, blocks)
            buf = []
            blocks.append(('h%d' % len(m.group(1)), m.group(2).strip()))
            i += 1
            continue
        if re.match(r'^(-{3,}|\*{3,}|_{3,})$', s):
            flush(buf, blocks)
            buf = []
            i += 1
            continue
        if not s:
            flush(buf, blocks)
            buf = []
            i += 1
            continue
        if s.startswith('- ') or s.startswith('* '):
            flush(buf, blocks)
            buf = []
            blocks.append(('li', s[2:].strip()))
            i += 1
            continue
        buf.append(s)
        i += 1
    flush(buf, blocks)
    return cover, blocks


# ---------- 渲染 ----------
HEAD_STYLE = {'h1': 'Heading1', 'h2': 'Heading2', 'h3': 'Heading3',
              'h4': 'Heading3', 'h5': 'Heading3', 'h6': 'Heading3'}
CAP_STYLE = re.compile(r'^(表\d+|附)')


def sect_pr(with_footer, start_page=False):
    """节属性。CT_SectPr 序列严格：
    headerReference / footerReference → … → pgSz → pgMar → pgNumType → cols → docGrid"""
    ref = '<w:footerReference w:type="default" r:id="rId2"/>' if with_footer else ''
    pgn = '<w:pgNumType w:start="1"/>' if start_page else ''
    return ('%s<w:pgSz w:w="%d" w:h="%d"/>'
            '<w:pgMar w:top="%d" w:right="%d" w:bottom="%d" w:left="%d" '
            'w:header="851" w:footer="992" w:gutter="0"/>'
            '%s<w:cols w:space="425"/><w:docGrid w:linePitch="312"/>'
            % (ref, PAGE_W, PAGE_H, MARGIN_TB, MARGIN_LR, MARGIN_TB, MARGIN_LR, pgn))


def render_body(cover, blocks):
    out = []
    for c in cover:
        out.append(para(c, align='center', sz=44, bold=True, ea='黑体',
                        line=480, after=0, keep_next=True))     # 二号=22pt=44半点
    if cover:
        # 封面独立成节（段落级 sectPr），且不含页脚引用 → 封面不出现页码
        out.append('<w:p><w:pPr><w:sectPr>%s</w:sectPr></w:pPr></w:p>' % sect_pr(False))
    for kind, val in blocks:
        if kind == 'h1':
            out.append(para(val, style='Heading1'))
        elif kind == 'h2':
            out.append(para(val, style='Heading2'))
        elif kind in HEAD_STYLE:
            out.append(para(val, style=HEAD_STYLE[kind]))
        elif kind == 'caption':
            out.append(para(val, align='center', sz=18, bold=True, ea='黑体',
                            before=120, after=60, keep_next=True))
        elif kind == 'li':
            out.append(para('· ' + val, left=420, hang=420, line=360, after=60))
        elif kind == 'code':
            out.append(code_xml(val))
        elif kind == 'table':
            out.append(table_xml(val))
        else:
            out.append(para(val, first_chars=200, after=60))
    # 正文节属性作为 body 的最后一个直接子元素由 build_docx_bytes 追加
    return ''.join(out)


DOC_HEAD = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="%s" xmlns:r="http://schemas.openxmlformats.org/'
            'officeDocument/2006/relationships"><w:body>' % W)

STYLES = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<w:styles xmlns:w="%s">'
          '<w:docDefaults>'
          '<w:rPrDefault><w:rPr>'
          '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="宋体" w:cs="Times New Roman"/>'
          '<w:sz w:val="24"/><w:szCs w:val="24"/>'
          '<w:lang w:val="en-US" w:eastAsia="zh-CN"/>'
          '</w:rPr></w:rPrDefault>'
          '<w:pPrDefault><w:pPr><w:spacing w:line="360" w:lineRule="auto"/></w:pPr></w:pPrDefault>'
          '</w:docDefaults>'
          '<w:style w:type="paragraph" w:default="1" w:styleId="Normal">'
          '<w:name w:val="Normal"/><w:qFormat/></w:style>'
          '%s'
          '</w:styles>')


def styles_xml():
    return STYLES % (W, style_def('Heading1', 'heading 1', 32, 0) +
                     style_def('Heading2', 'heading 2', 24, 1) +
                     style_def('Heading3', 'heading 3', 21, 2))


def style_def(sid, name, sz, outline):
    return ('<w:style w:type="paragraph" w:styleId="%s"><w:name w:val="%s"/>'
            '<w:basedOn w:val="Normal"/><w:qFormat/>'
            '<w:pPr><w:keepNext/><w:spacing w:before="240" w:after="120"/>'
            '<w:outlineLvl w:val="%d"/></w:pPr>'
            '<w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="黑体"/>'
            '<w:b/><w:bCs/><w:sz w:val="%d"/><w:szCs w:val="%d"/></w:rPr></w:style>'
            % (sid, name, outline, sz, sz))


CONTENT_TYPES = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                 '<Types xmlns="%s">'
                 '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                 '<Default Extension="xml" ContentType="application/xml"/>'
                 '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
                 '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
                 '<Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>'
                 '<Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>'
                 '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
                 '</Types>' % CT)

ROOT_RELS = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             '<Relationships xmlns="%s">'
             '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
             '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
             '</Relationships>' % PR)

# 文档属性：只写课题标题，**不写作者/引擎/版本/生成工具**（成品零引擎元信息，见 SKILL.md §3.5）
# 时间戳固定常量 → 保证同一 md 生成的 docx 逐字节幂等
CORE_STAMP = '2020-01-01T00:00:00Z'
CORE_PROPS = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
              '<cp:coreProperties'
              ' xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"'
              ' xmlns:dc="http://purl.org/dc/elements/1.1/"'
              ' xmlns:dcterms="http://purl.org/dc/terms/"'
              ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
              '<dc:title>%s</dc:title>'
              '<dcterms:created xsi:type="dcterms:W3CDTF">%s</dcterms:created>'
              '<dcterms:modified xsi:type="dcterms:W3CDTF">%s</dcterms:modified>'
              '</cp:coreProperties>')


def core_xml(title):
    safe = re.sub(r'[<>&]', '', title)[:120]
    return CORE_PROPS % (esc(safe), CORE_STAMP, CORE_STAMP)

DOC_RELS = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="%s">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/>'
            '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/>'
            '</Relationships>' % PR)

SETTINGS = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:settings xmlns:w="%s">'
            '<w:zoom w:percent="100"/>'
            '<w:defaultTabStop w:val="420"/>'
            '<w:characterSpacingControl w:val="doNotCompress"/>'
            '</w:settings>' % W)


def footer_xml():
    """页脚：居中「第 X 页 共 Y 页」，纯字段（Word 自动计页）"""
    def fld(instr):
        return ('<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
                '<w:r><w:instrText xml:space="preserve"> %s </w:instrText></w:r>'
                '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
                '<w:r><w:t>1</w:t></w:r>'
                '<w:r><w:fldChar w:fldCharType="end"/></w:r>' % instr)

    inner = ('<w:r><w:rPr><w:sz w:val="18"/><w:szCs w:val="18"/></w:rPr>'
             '<w:t xml:space="preserve">第 </w:t></w:r>'
             + fld('PAGE') +
             '<w:r><w:rPr><w:sz w:val="18"/><w:szCs w:val="18"/></w:rPr>'
             '<w:t xml:space="preserve"> 页 共 </w:t></w:r>'
             + fld('SECTIONPAGES') +
             '<w:r><w:rPr><w:sz w:val="18"/><w:szCs w:val="18"/></w:rPr>'
             '<w:t xml:space="preserve"> 页</w:t></w:r>')
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:ftr xmlns:w="%s"><w:p><w:pPr><w:jc w:val="center"/></w:pPr>%s</w:p></w:ftr>' % (W, inner))


def build_docx_bytes(text):
    """md 文本 → docx 二进制（确定性）"""
    hits = red_scan(text)
    if hits:
        raise ValueError('红区命中，拒绝生成：%s' % ','.join(hits))
    cover, blocks = parse_md(text)
    # 最终节 <w:sectPr> 必须是 <w:body> 的直接最后一个子元素（兼容 python-docx / 各阅读器）
    document = (DOC_HEAD + render_body(cover, blocks)
                + '<w:sectPr>%s</w:sectPr></w:body></w:document>' % sect_pr(True, start_page=True))
    styles = styles_xml()
    parts = [
        ('[Content_Types].xml', CONTENT_TYPES),
        ('_rels/.rels', ROOT_RELS),
        ('docProps/core.xml', core_xml(plan_title(text))),
        ('word/document.xml', document),
        ('word/styles.xml', styles),
        ('word/settings.xml', SETTINGS),
        ('word/footer1.xml', footer_xml()),
        ('word/_rels/document.xml.rels', DOC_RELS),
    ]
    bio = __import__('io').BytesIO()
    with zipfile.ZipFile(bio, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, data in parts:
            zi = zipfile.ZipInfo(name, date_time=ZIP_STAMP)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o600 << 16
            z.writestr(zi, data.encode('utf-8'))
    return bio.getvalue()


# ---------- 派生文件名 ----------
def plan_title(md_text):
    """取教案头课题列作文档标题（去书名号与括号后缀）"""
    m = re.search(r'^\|\s*课题\s*\|\s*(.+?)\s*\|', md_text, re.M)
    title = m.group(1) if m else '教学设计方案'
    t = re.match(r'^《(.+?)》', title)
    return t.group(1) if t else title.split('（')[0].strip()


def plan_name(md_text, fallback):
    title = plan_title(md_text) if re.search(
        r'^\|\s*课题\s*\|\s*(.+?)\s*\|', md_text, re.M) else fallback
    m2 = re.search(r'共(\d+)课时', md_text)
    n = m2.group(1) if m2 else '1'
    return '%s_教学设计方案_%s课时.docx' % (title, n)


def export_pdf(docx_path, pdf_path):
    """尽力而为的 PDF 导出（Word COM → docx2pdf → LibreOffice）。
    三者皆不可用时返回 None，脚本退化为"仅 docx + 另存为 PDF 指令"，不阻断交付。"""
    import subprocess
    try:
        import win32com.client as win32
        word = win32.Dispatch('Word.Application')
        word.Visible = False
        d = word.Documents.Open(docx_path)
        d.SaveAs(pdf_path, FileFormat=17)      # 17 = wdFormatPDF，中文字体内嵌
        d.Close()
        word.Quit()
        return 'Word COM'
    except Exception:
        pass
    try:
        import docx2pdf
        docx2pdf.convert(docx_path, pdf_path)
        return 'docx2pdf'
    except Exception:
        pass
    for exe in ('soffice', 'libreoffice'):
        try:
            subprocess.run([exe, '--headless', '--convert-to', 'pdf',
                            '--outdir', os.path.dirname(pdf_path), docx_path],
                           check=True, timeout=180)
            base = os.path.splitext(os.path.basename(docx_path))[0] + '.pdf'
            cand = os.path.join(os.path.dirname(pdf_path), base)
            if os.path.exists(cand):
                return 'LibreOffice'
        except Exception:
            continue
    return None


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    check = '--check' in sys.argv
    want_pdf = '--pdf' in sys.argv
    outdir = args[0] if args else os.path.join(root, 'examples')
    rep = []
    okeds, fails = 0, 0
    for f in sorted(glob.glob(os.path.join(root, 'examples', '*.md'))):
        nm = os.path.basename(f)
        text = open(f, encoding='utf-8').read()
        out_name = plan_name(text, nm[:-3])
        dest = os.path.join(outdir, out_name)
        try:
            data = build_docx_bytes(text)
        except ValueError as e:
            fails += 1
            rep.append('  [RED-ZONE] %s → %s' % (nm, e))
            continue
        digest = hashlib.sha256(data).hexdigest()[:16]
        if check:
            same = os.path.exists(dest) and hashlib.sha256(
                open(dest, 'rb').read()).hexdigest()[:16] == digest
            rep.append('  [%s] %s ← %s  sha256=%s' % ('SAME' if same else 'DIFF', out_name, nm, digest))
            okeds += 1 if same else 0
            fails += 0 if same else 1
        else:
            open(dest, 'wb').write(data)
            okeds += 1
            rep.append('  [OK] %s ← %s  %d bytes  sha256=%s' % (out_name, nm, len(data), digest))
            if want_pdf:
                pdest = os.path.splitext(dest)[0] + '.pdf'
                how = export_pdf(os.path.abspath(dest), os.path.abspath(pdest))
                rep.append('       PDF：%s' % (how if how else '未导出（本机无 Word/LibreOffice，请在 Word 或 WPS 中「另存为 PDF」，中文字体内嵌）'))
    head = ['生成器版本 %s（%s）' % (ENGINE_VERSION, datetime.date.today().isoformat()),
            '模式：%s' % ('一致性校验' if check else '生成'),
            '结果：成功 %d / 失败 %d' % (okeds, fails), '']
    open(os.path.join(root, 'docs', 'md_to_docx_report.txt'), 'w',
         encoding='utf-8').write('\n'.join(head + rep))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        import traceback
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        open(os.path.join(root, 'docs', 'md_to_docx_report.txt'), 'w',
             encoding='utf-8').write('ERROR:\n' + traceback.format_exc())
