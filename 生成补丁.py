# -*- coding: utf-8 -*-
"""
Termius 简体中文补丁 · 构建脚本

作用：
  1. 读取词典.txt（英文|中文，可自行编辑）
  2. 从原始 app.asar / Termius.exe 生成汉化版本：
       - 注入运行时界面翻译层 termius-zh.js（只翻译界面，不碰终端输出）
       - 精确替换原生菜单/表单标签等属性位置的文案
       - 重算所有被修改文件的 SHA256 完整性记录
       - 重算 asar 头部 SHA256 并原位修补 exe 中的校验值
  3. 输出到 output/ 目录并自检

用法： python 生成补丁.py
原始文件优先取自 original/（首次运行自动从 Termius.zip 或安装目录提取），
因此可以随时改词典后反复重建，不会累积修改。
"""
import hashlib
import json
import os
import re
import shutil
import struct
import sys
import zipfile
from copy import deepcopy
from pathlib import Path

BASE = Path(__file__).resolve().parent   # 补丁工作目录（词典、模板、original、output）
ORIG = BASE / 'original'
OUT = BASE / 'output'


def find_termius_root():
    """定位 Termius 安装目录：环境变量 > 系统默认路径 > 脚本所在目录附近"""
    candidates = []
    env = os.environ.get('TERMIUS_DIR')
    if env:
        candidates.append(Path(env))
    local_appdata = os.environ.get('LOCALAPPDATA')
    if local_appdata:
        candidates.append(Path(local_appdata) / 'Programs' / 'Termius')
    candidates += [BASE, BASE.parent, BASE.parent.parent]
    for c in candidates:
        if (c / 'resources' / 'app.asar').exists():
            return c
    sys.exit('找不到 Termius 安装目录，请设置环境变量 TERMIUS_DIR 指向安装目录')


ROOT = find_termius_root()
ZIP = ROOT.parent / 'Termius.zip'

ASAR_REL = Path('resources') / 'app.asar'
EXE_NAME = 'Termius.exe'
INJECT_JS = '/ui-process/assets/termius-zh.js'
HTML_FILES = [
    '/ui-process/src/ui-process/main.html',
    '/ui-process/src/settings-process/main.html',
]
BLOCK_SIZE = 4 * 1024 * 1024


def log(msg):
    print('[补丁] ' + msg, flush=True)


# ---------------------------------------------------------------- 词典
def load_dict():
    path = BASE / '词典.txt'
    if not path.exists():
        sys.exit('找不到词典.txt：' + str(path))
    exact, prefix, ci = {}, [], {}
    for line in path.read_text(encoding='utf-8').splitlines():
        if not line.strip() or line.lstrip().startswith('#') or '|' not in line:
            continue
        raw_key, val = line.split('|', 1)
        val = val.strip()
        if not raw_key.strip() or not val:
            continue
        if raw_key.endswith(' '):                    # 以空格结尾 = 组合短语前缀
            prefix.append([raw_key.rstrip() + ' ', val])
        exact[raw_key.strip()] = val
    for k, v in exact.items():
        if len(k) >= 4:                              # 短词不做大小写模糊，避免误伤
            ci.setdefault(k.lower(), v)
    return exact, prefix, ci


# ---------------------------------------------------------------- 原始文件
def is_patched_asar(path):
    """判断 app.asar 是否已被本补丁注入，避免把补丁版误当成原版缓存"""
    try:
        with open(path, 'rb') as f:
            head = f.read(16)
            if len(head) < 16:
                return False
            n = struct.unpack('<I', head[12:16])[0]
            f.seek(16)
            hdr = json.loads(f.read(n).decode('utf-8'))
        node = hdr['files']
        for part in ('ui-process', 'assets', 'termius-zh.js'):
            node = node['files'][part]
        return True
    except Exception:
        return False


def prepare_original():
    a, e = ORIG / 'app.asar', ORIG / EXE_NAME
    ORIG.mkdir(parents=True, exist_ok=True)
    cur_a, cur_e = ROOT / ASAR_REL, ROOT / EXE_NAME

    # Termius 更新后安装目录里是全新的原版：只要它不是补丁版且与缓存不一致，就刷新缓存。
    # 这样升级后直接重跑本脚本即可，不必手动清理 original/。
    if cur_a.exists() and cur_e.exists() and not is_patched_asar(cur_a):
        stale = (not a.exists() or not e.exists() or
                 a.stat().st_size != cur_a.stat().st_size or
                 e.stat().st_size != cur_e.stat().st_size)
        if stale:
            log('检测到 Termius 新版本，刷新原始文件缓存…')
            shutil.copy2(cur_a, a)
            shutil.copy2(cur_e, e)
        return a, e

    if a.exists() and e.exists():
        return a, e

    # 兜底：安装目录已是补丁版且无缓存时，尝试从完整安装备份 zip 取原版
    if ZIP.exists():
        log('从 Termius.zip 提取原始文件（约 400MB，稍候）…')
        with zipfile.ZipFile(ZIP) as z:
            for member, target in [('resources/app.asar', a), (EXE_NAME, e)]:
                with z.open(member) as src, open(target, 'wb') as dst:
                    shutil.copyfileobj(src, dst, 4 * 1024 * 1024)
        return a, e
    sys.exit('找不到未打补丁的原始文件：请先运行 还原补丁.bat，或提供 Termius.zip')


# ---------------------------------------------------------------- asar 读写
def open_asar(path):
    f = open(path, 'rb')
    head = f.read(16)
    if len(head) < 16 or struct.unpack('<I', head[:4])[0] != 4:
        sys.exit('app.asar 格式异常')
    json_len = struct.unpack('<I', head[12:16])[0]
    jb = f.read(json_len)
    hdr = json.loads(jb.decode('utf-8'))
    data_start = 8 + struct.unpack('<I', head[4:8])[0]
    return f, hdr, jb, data_start


def list_files(node, prefix=''):
    for name, meta in node.get('files', {}).items():
        p = prefix + '/' + name
        if 'files' in meta:
            yield from list_files(meta, p)
        else:
            yield p, meta


def get_entry(hdr, path):
    node = hdr['files']
    for part in path.strip('/').split('/'):
        node = node['files'][part]
    return node


def ensure_entry(hdr, path):
    parts = path.strip('/').split('/')
    node = hdr['files']
    for part in parts[:-1]:
        child = node.setdefault(part, {'files': {}})
        if 'files' not in child:
            child['files'] = {}
        node = child['files']
    return node.setdefault(parts[-1], {})


def read_at(f, offset, size):
    f.seek(offset)
    return f.read(size)


def make_integrity(data):
    whole = hashlib.sha256(data).hexdigest()
    blocks = [hashlib.sha256(data[i:i + BLOCK_SIZE]).hexdigest()
              for i in range(0, len(data), BLOCK_SIZE)]
    if not blocks:
        blocks = [hashlib.sha256(b'').hexdigest()]
    return {'algorithm': 'SHA256', 'hash': whole,
            'blockSize': BLOCK_SIZE, 'blocks': blocks}


# ---------------------------------------------------------------- 内容改写
UI_HINT = re.compile(
    r'\b(?:children|placeholder|label|title|helperText|tooltip|defaultMessage)\s*:\s*["\']'
    r'|\.jsx\(|\.jsxs\(|createElement\(')
ATTR_RE = re.compile(
    r'\b(label|title|placeholder|aria-label|text|message|header|subtitle|tooltip|helperText|alt)'
    r'\s*:\s*(["\'])((?:\\.|(?!\2)[^\\\n])*?)\2')


def is_ui_chunk(data):
    t = data.decode('utf-8', 'ignore')
    a = len(UI_HINT.findall(t))
    d = t.count('description:') + t.count('description":')
    return (a >= 3 and d < a * 2) or (a >= 1 and d == 0)


def static_replace(text, exact):
    hits = [0]

    def repl(m):
        s = m.group(3)
        if s in exact and s.isascii() and re.match(r'^[A-Za-z]', s):
            hits[0] += 1
            return m.group(1) + ':' + json.dumps(exact[s], ensure_ascii=False)
        return m.group(0)

    return ATTR_RE.sub(repl, text), hits[0]


def make_runtime_js(exact, prefix, ci):
    tpl = (BASE / 'termius-zh.tpl.js').read_text(encoding='utf-8')
    return (tpl.replace('__DICT_JSON__', json.dumps(exact, ensure_ascii=False))
               .replace('__DICT_CI_JSON__', json.dumps(ci, ensure_ascii=False))
               .replace('__PREFIX_JSON__', json.dumps(prefix, ensure_ascii=False)))


# ---------------------------------------------------------------- 主流程
def main():
    exact, prefix, ci = load_dict()
    log('词典条目：%d（含 %d 条组合短语）' % (len(exact), len(prefix)))

    asar_path, exe_path = prepare_original()
    f, hdr, jb_orig, data_start = open_asar(asar_path)
    entries = dict((p, m) for p, m in list_files(hdr))
    total_size = f.seek(0, 2)
    f.seek(0)

    mods = {}
    static_hits = 0
    touched = 0

    # 1) 精确替换 UI 组件 / 主进程里属性位置的文案
    for path, meta in entries.items():
        if meta.get('unpacked'):
            continue
        is_ui = path.startswith('/ui-process/assets/') and path.endswith('.js')
        is_main = path == '/main-process/main-process.js'
        if not (is_ui or is_main):
            continue
        raw = read_at(f, data_start + int(meta['offset']), meta['size'])
        if is_ui and not is_ui_chunk(raw):
            continue
        text = raw.decode('utf-8')
        new_text, n = static_replace(text, exact)
        if n:
            mods[path] = new_text.encode('utf-8')
            static_hits += n
            touched += 1

    # 2) 两个页面 HTML 注入翻译层
    for path in HTML_FILES:
        if path not in entries:
            log('警告：未找到 ' + path + '（版本差异，跳过）')
            continue
        meta = entries[path]
        text = read_at(f, data_start + int(meta['offset']), meta['size']).decode('utf-8')
        if 'termius-zh.js' not in text:
            text = text.replace(
                '</head>',
                '    <script type="module" src="../../assets/termius-zh.js"></script>\n  </head>')
        text = text.replace('<html lang="en"', '<html lang="zh-CN"')
        mods[path] = text.encode('utf-8')
        touched += 1

    # 3) 新增运行时翻译脚本
    runtime = make_runtime_js(exact, prefix, ci)
    if not runtime or '__DICT_JSON__' in runtime:
        sys.exit('翻译层模板缺失或占位符未替换')
    mods[INJECT_JS] = runtime.encode('utf-8')
    log('静态替换 %d 处（%d 个文件），注入翻译层 %d KB'
        % (static_hits, touched, len(mods[INJECT_JS]) // 1024))

    # 4) 重建 asar：原数据区原样保留，新内容追加到末尾
    new_hdr = deepcopy(hdr)
    orig_data_len = total_size - data_start
    tail = bytearray()
    for path, content in mods.items():
        node = ensure_entry(new_hdr, path)
        node.pop('unpacked', None)
        node['offset'] = str(orig_data_len + len(tail))
        node['size'] = len(content)
        node['integrity'] = make_integrity(content)
        tail += content

    jb = json.dumps(new_hdr, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    jb += b' ' * ((-len(jb)) % 4)                    # 4 字节对齐，避免 Pickle padding 歧义
    n = len(jb)
    header_bytes = struct.pack('<IIII', 4, 8 + n, 4 + n, n) + jb
    new_hash = hashlib.sha256(jb).hexdigest()
    old_hash = hashlib.sha256(jb_orig).hexdigest()

    OUT.mkdir(parents=True, exist_ok=True)
    out_asar = OUT / 'app.asar'
    with open(out_asar, 'wb') as o:
        o.write(header_bytes)
        f.seek(data_start)
        shutil.copyfileobj(f, o, 4 * 1024 * 1024)
        o.write(tail)
    f.close()

    # 5) 修补 exe 中内嵌的 asar 头部校验值（同为 64 位 hex，原位替换）
    exe = bytearray(exe_path.read_bytes())
    pos = exe.find(old_hash.encode('ascii'))
    if pos < 0:
        sys.exit('未在 Termius.exe 中找到原始校验值，可能版本不匹配')
    exe[pos:pos + 64] = new_hash.encode('ascii')
    patch_meta = {
        'exe_offset': pos,
        'old_hash': old_hash,
        'new_hash': new_hash,
        'old_data_start': data_start,
        'new_data_start': 16 + n,
        'asar_entries': len(list(list_files(new_hdr))),
        'asar_size': out_asar.stat().st_size,
    }
    (OUT / 'patch.json').write_text(
        json.dumps(patch_meta, ensure_ascii=False, indent=2), encoding='utf-8')
    log('exe 校验值已定位：偏移 %d，%s… -> %s…' % (pos, old_hash[:12], new_hash[:12]))

    (OUT / '词典.json').write_text(
        json.dumps(exact, ensure_ascii=False, indent=2), encoding='utf-8')

    # 6) 自检
    verify(out_asar, patch_meta, exe, mods, new_hash)
    log('完成：%s' % OUT)
    log('运行「安装补丁.bat」即可应用（只需替换 app.asar 与 exe 中的 64 字节）。')


def verify(out_asar, meta, exe, mods, new_hash):
    f, hdr, jb, ds = open_asar(out_asar)
    assert hashlib.sha256(jb).hexdigest() == new_hash, '头部 hash 不匹配'
    assert ds == meta['new_data_start'], '数据区起点不匹配'
    pos = meta['exe_offset']
    assert bytes(exe[pos:pos + 64]) == meta['new_hash'].encode('ascii'), 'exe 校验值未写入'
    entries = dict((p, m) for p, m in list_files(hdr))
    for path, content in mods.items():
        m = entries[path]
        got = read_at(f, ds + int(m['offset']), m['size'])
        assert got == content, '文件内容校验失败: ' + path
        assert hashlib.sha256(got).hexdigest() == m['integrity']['hash'], 'integrity 不匹配: ' + path
    # 抽查 3 个未修改文件，确保原始数据区未被破坏
    unchanged = [p for p in entries if p not in mods and not entries[p].get('unpacked')][:3]
    for path in unchanged:
        m = entries[path]
        assert len(read_at(f, ds + int(m['offset']), m['size'])) == m['size'], '原始数据损坏: ' + path
    f.close()
    log('自检通过：%d 个改动文件、%d 个 asar 条目、头部与 exe 校验一致'
        % (len(mods), len(entries)))


if __name__ == '__main__':
    main()
