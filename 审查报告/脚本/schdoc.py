# -*- coding: utf-8 -*-
"""Altium SchDoc 记录解析。

SchDoc 的 FileHeader 流里是一条条以空字符结尾的竖线分隔记录，
形如 |RECORD=2|OwnerIndex=28|PinLength=20|Location.X=100|...
每条记录里中文可能以 GBK 存放（同时有 %UTF8% 前缀的 UTF-8 副本），
所以逐条先试 UTF-8 再退 GBK。

用法:
    from schdoc import load_records
    records = load_records(r'...\\Power.SchDoc')   # list[dict]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cfb import CFB

# 记录类型（本工程用到的）
T_COMPONENT = '1'
T_PIN = '2'
T_LABEL = '4'
T_POLYLINE = '6'
T_POWERPORT = '17'
T_PORT = '18'
T_WIRE = '27'
T_JUNCTION = '29'
T_DESIGNATOR = '34'
T_PARAMETER = '41'
T_IMPLEMENTATION = '45'


def _decode(raw):
    for enc in ('utf-8', 'gbk', 'latin-1'):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode('latin-1', 'replace')


def split_record(text):
    """把 |k=v|k="v|v" 拆成 dict，跳过 %UTF8% 副本键。"""
    parts, cur, inq = [], '', False
    for ch in text:
        if ch == '"':
            inq = not inq
            cur += ch
        elif ch == '|' and not inq:
            parts.append(cur)
            cur = ''
        else:
            cur += ch
    parts.append(cur)

    out = {}
    for p in parts:
        if not p or p.startswith('%UTF8%'):
            continue
        if '=' in p:
            k, v = p.split('=', 1)
        else:
            k, v = p, ''
        if len(v) >= 2 and v[0] == '"' and v[-1] == '"':
            v = v[1:-1]
        out[k.upper()] = v
    return out


def load_records(path):
    """读取 SchDoc，返回记录字典列表（顺序即文件内顺序，索引用于 OwnerIndex 引用）。"""
    data = Path(path).read_bytes()
    fh = CFB(data).stream('FileHeader')
    if fh is None:
        raise RuntimeError('没有 FileHeader 流，不是原理图文件？')

    records, pos = [], 0
    while True:
        start = fh.find(b'|RECORD=', pos)
        if start < 0:
            break
        end = fh.find(b'\x00', start)
        if end < 0:
            end = len(fh)
        records.append(split_record(_decode(fh[start:end])))
        pos = end + 1
    return records


def num(rec, key, default=0):
    try:
        return int(rec.get(key, default))
    except (TypeError, ValueError):
        return default


if __name__ == '__main__':
    import collections
    p = sys.argv[1] if len(sys.argv) > 1 else None
    if not p:
        p = str(Path(__file__).resolve().parents[2] / 'project' / 'FOC' / 'Power.SchDoc')
    recs = load_records(p)
    print('文件:', p)
    print('记录数:', len(recs))
    for k, v in sorted(collections.Counter(r.get('RECORD', '?') for r in recs).items(),
                       key=lambda kv: int(kv[0]) if kv[0].isdigit() else 999):
        print('  RECORD=%s  %d 条' % (k, v))
