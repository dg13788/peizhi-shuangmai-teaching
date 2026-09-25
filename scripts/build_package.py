# -*- coding: utf-8 -*-
"""技能包打包器：从 GitHub 仓库一键产出符合上传规范的 skill zip（双轨制的技能轨出口）。

背景（2.5.0 双轨制）：仓库根保留 README/CHANGELOG/CONTRIBUTING/LICENSE 等 GitHub 治理文件，
     豆包/千问/WorkBuddy 等技能平台的上传包则不应包含它们。本脚本从仓库抽取技能运行必需文件，
     产出干净的 dist/<name>.zip —— 仓库是开发态，zip 是上传态，二者同源不双维护。

打包内容（对照火山引擎 AgentKit / 豆包技能规范）：
  <name>/                    zip 顶层为技能名目录（取 SKILL.md frontmatter 的 name）
  ├── SKILL.md               主文件（frontmatter 必检 name+description）
  ├── scripts/               md_to_docx.py / md_to_json.py / regression_check.py / build_package.py
  ├── references/            output-schema.json / format-baseline.md / release-checklist.md
  │   └── LICENSE.md         由仓库根 LICENSE 复制（许可随包分发，根目录不另放 LICENSE）
  └── examples/              基准 md 与派生 JSON（不含 docx/pdf 等二进制成品）

硬性排除：README/CHANGELOG/CONTRIBUTING/.gitignore/.git/.workbuddy/dist、*_report.txt、
          *.docx/*.pdf、锚定单/内容提取卡等会话产物。
防呆：打包前校验 frontmatter 必填字段、对全部入包文本做红区扫描（命中即拒绝打包）、
     固定 zip 时间戳保证同一仓库状态产出逐字节恒定。

用法：python scripts/build_package.py
输出：dist/<name>.zip + %TEMP%/peizhi_shuangmai/build_package_report.txt
"""
import os
import re
import sys
import glob
import zipfile
import tempfile
import hashlib

ENGINE_VERSION = '2.5.0'
ZIP_STAMP = (2020, 1, 1, 0, 0, 0)   # 固定时间戳 → 字节幂等

REPORT_DIR = os.path.join(tempfile.gettempdir(), 'peizhi_shuangmai')

# 红区扫描（与引擎铁律 1 一致）
RED_RULES = [
    ('疑似身份证', re.compile(r'\d{17}[\dXx]')),
    ('疑似手机号', re.compile(r'(?<!\d)1[3-9]\d{9}(?!\d)')),
    ('长数字串', re.compile(r'\d{11,}')),
    ('疑似病历号', re.compile(r'(病历|住院号|诊断书)[^\n]{0,10}\d{4,}')),
]

INCLUDE_SCRIPTS = ('md_to_docx.py', 'md_to_json.py', 'regression_check.py', 'build_package.py')
INCLUDE_REFERENCES = ('output-schema.json', 'format-baseline.md', 'release-checklist.md')


def report_path(name):
    os.makedirs(REPORT_DIR, exist_ok=True)
    return os.path.join(REPORT_DIR, name)


def read_frontmatter(text):
    m = re.match(r'^---\n(.*?)\n---\n', text, re.S)
    return m.group(1) if m else ''


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    rep = ['打包器版本 %s' % ENGINE_VERSION, '']

    # ① frontmatter 必检：name + description（平台校验口径）
    skill = open(os.path.join(root, 'SKILL.md'), encoding='utf-8').read()
    head = read_frontmatter(skill)
    nm = re.search(r'^name: (.+)$', head, re.M)
    ds = re.search(r'^description: (.+)$', head, re.M)
    if not nm or not ds:
        rep.append('拒绝打包：SKILL.md frontmatter 缺少必填 name 或 description')
        open(report_path('build_package_report.txt'), 'w', encoding='utf-8').write('\n'.join(rep))
        return 1
    name = nm.group(1).strip()
    if not re.match(r'^[a-z0-9]+(-[a-z0-9]+)*$', name) or len(name) > 64 or 'agentkit' in name:
        rep.append('拒绝打包：name 不合规（须小写字母/数字/连字符，≤64，不含 agentkit）：%s' % name)
        open(report_path('build_package_report.txt'), 'w', encoding='utf-8').write('\n'.join(rep))
        return 1
    if not (0 < len(ds.group(1).strip()) <= 1024) or re.search(r'<[A-Za-z/!]', ds.group(1)):
        rep.append('拒绝打包：description 须非空、≤1024 字符、不含 XML 标签')
        open(report_path('build_package_report.txt'), 'w', encoding='utf-8').write('\n'.join(rep))
        return 1

    # ② 收集入包文件（arcname → 绝对路径）
    files = {'%s/SKILL.md' % name: os.path.join(root, 'SKILL.md'),
             '%s/references/LICENSE.md' % name: os.path.join(root, 'LICENSE')}
    for f in INCLUDE_SCRIPTS:
        files['%s/scripts/%s' % (name, f)] = os.path.join(root, 'scripts', f)
    for f in INCLUDE_REFERENCES:
        files['%s/references/%s' % (name, f)] = os.path.join(root, 'references', f)
    for p in sorted(glob.glob(os.path.join(root, 'examples', '*.md'))) + \
            sorted(glob.glob(os.path.join(root, 'examples', '*.json'))):
        files['%s/examples/%s' % (name, os.path.basename(p))] = p

    missing = [a for a, p in files.items() if not os.path.exists(p)]
    if missing:
        rep.append('拒绝打包：入包源文件缺失：%s' % ','.join(missing))
        open(report_path('build_package_report.txt'), 'w', encoding='utf-8').write('\n'.join(rep))
        return 1

    # ③ 红区扫描（全部入包文本文件，命中即拒绝）
    hits = []
    for arc, p in files.items():
        text = open(p, encoding='utf-8').read()
        for rule, rx in RED_RULES:
            if rx.search(text):
                hits.append('%s ← %s' % (rule, arc))
    if hits:
        rep.append('拒绝打包：红区扫描命中（铁律 1 不豁免）：')
        rep += ['  %s' % h for h in hits]
        open(report_path('build_package_report.txt'), 'w', encoding='utf-8').write('\n'.join(rep))
        return 1

    # ④ 确定性写出（排序 + 固定时间戳）
    outdir = os.path.join(root, 'dist')
    os.makedirs(outdir, exist_ok=True)
    dest = os.path.join(outdir, '%s.zip' % name)
    with zipfile.ZipFile(dest, 'w', zipfile.ZIP_DEFLATED) as z:
        for arc in sorted(files):
            zi = zipfile.ZipInfo(arc, date_time=ZIP_STAMP)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o600 << 16
            z.writestr(zi, open(files[arc], 'rb').read())

    digest = hashlib.sha256(open(dest, 'rb').read()).hexdigest()[:16]
    rep.append('打包完成：%s' % dest)
    rep.append('技能名目录：%s/　文件数：%d　sha256=%s' % (name, len(files), digest))
    rep.append('')
    rep.append('入包清单：')
    rep += ['  %s' % a for a in sorted(files)]
    rep.append('')
    rep.append('未入包（按规范排除）：README.md / CHANGELOG.md / CONTRIBUTING.md / .gitignore / '
               '.git / .workbuddy / dist / *_report.txt / *.docx / *.pdf')
    open(report_path('build_package_report.txt'), 'w', encoding='utf-8').write('\n'.join(rep))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception:
        import traceback
        open(report_path('build_package_report.txt'), 'w',
             encoding='utf-8').write('ERROR:\n' + traceback.format_exc())
        sys.exit(1)
