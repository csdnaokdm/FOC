# -*- coding: utf-8 -*-
"""从 SchDoc 重建网络表，并做连通性体检。

判定规则（与 Altium 一致）:
  * 一根导线的各个折点互连；
  * 导线端点落在另一条导线内部 -> T 型连接，连通；
  * 两条导线交叉且交点不是任何一条的端点、也没有 Junction -> 不连通；
  * 有 Junction 的点，所有经过该点的导线连在一起；
  * 引脚电气热点 = 引脚坐标 + 引脚长度 × 朝向（由 PinConglomerate 低两位给出，
    0=右 1=上 2=左 3=下，文件坐标里 +Y 为“上”）；
  * 同名电源端口（RECORD=17）全图合并。

用法:
    python netlist.py            # 打印网络表 + 体检结论，并刷新 资料/网表.csv
"""

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from schdoc import (load_records, num, T_COMPONENT, T_PIN, T_WIRE, T_JUNCTION,
                    T_POWERPORT, T_PORT, T_DESIGNATOR, T_PARAMETER, T_IMPLEMENTATION)

HERE = Path(__file__).resolve().parent
REPORT_DIR = HERE.parent                       # ...\审查报告
DATA_DIR = REPORT_DIR / '资料'
PROJECT_DIR = REPORT_DIR.parent / 'project' / 'FOC'
DEFAULT_SCH = PROJECT_DIR / 'Power.SchDoc'

DIRS = [(1, 0), (0, 1), (-1, 0), (0, -1)]      # 右 上 左 下


class UnionFind:
    def __init__(self):
        self.p = {}

    def find(self, a):
        self.p.setdefault(a, a)
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[ra] = rb


def on_seg(p, a, b):
    """点 p 是否落在线段 ab 上（含端点）。"""
    (px, py), (ax, ay), (bx, by) = p, a, b
    if (bx - ax) * (py - ay) - (by - ay) * (px - ax) != 0:
        return False
    return min(ax, bx) <= px <= max(ax, bx) and min(ay, by) <= py <= max(ay, by)


def build(path=DEFAULT_SCH):
    recs = load_records(path)

    # ---- 元件 ----
    comp = {}
    for i, r in enumerate(recs):
        if r.get('RECORD') == T_COMPONENT:
            comp[i] = {'i': i, 'lib': r.get('LIBREFERENCE', ''), 'des': '',
                       'value': '', 'params': {}, 'footprint': '', 'lcsc': ''}
    for r in recs:
        if r.get('RECORD') == T_DESIGNATOR:
            o = num(r, 'OWNERINDEX', -1)
            if o in comp:
                comp[o]['des'] = r.get('TEXT', '')
        elif r.get('RECORD') == T_PARAMETER:
            o = num(r, 'OWNERINDEX', -1)
            if o in comp:
                name = r.get('NAME', '')
                text = r.get('TEXT', '')
                comp[o]['params'][name] = text
                low = name.lower()
                if low == 'comment':
                    comp[o]['value'] = text
                elif low == 'supplierpart':
                    comp[o]['lcsc'] = text
                elif low in ('footprintname', 'package'):
                    comp[o]['footprint'] = comp[o]['footprint'] or text

    # 封装：优先取实现模型（RECORD=45 ModelName，经 RECORD=44 挂到元件上）
    for r in recs:
        if r.get('RECORD') != T_IMPLEMENTATION:
            continue
        list_idx = num(r, 'OWNERINDEX', -1)
        if list_idx < 0 or list_idx >= len(recs):
            continue
        owner = num(recs[list_idx], 'OWNERINDEX', -1)
        if owner in comp and r.get('MODELNAME'):
            comp[owner]['footprint'] = r['MODELNAME']

    # ---- 引脚 ----
    pins = []
    for r in recs:
        if r.get('RECORD') != T_PIN:
            continue
        rot = num(r, 'PINCONGLOMERATE') & 3
        length = num(r, 'PINLENGTH')
        x, y = num(r, 'LOCATION.X'), num(r, 'LOCATION.Y')
        dx, dy = DIRS[rot]
        owner = num(r, 'OWNERINDEX', -1)
        pins.append({
            'owner': owner,
            'des': comp[owner]['des'] if owner in comp else '',
            'num': r.get('DESIGNATOR', ''),
            'name': r.get('NAME', ''),
            'loc': (x, y),
            'hot': (x + dx * length, y + dy * length),
            'hidden': bool(num(r, 'PINCONGLOMERATE') & 8),
        })

    # ---- 导线 / 节点 / 电源端口 ----
    segs = []
    for r in recs:
        if r.get('RECORD') == T_WIRE:
            n = num(r, 'LOCATIONCOUNT', 2)
            pts = [(num(r, 'X%d' % (k + 1)), num(r, 'Y%d' % (k + 1))) for k in range(n)]
            segs.extend(zip(pts, pts[1:]))

    juncs = [(num(r, 'LOCATION.X'), num(r, 'LOCATION.Y'))
             for r in recs if r.get('RECORD') == T_JUNCTION]

    ports = []
    for r in recs:
        if r.get('RECORD') == T_POWERPORT:
            ports.append({'name': r.get('TEXT', ''),
                          'loc': (num(r, 'LOCATION.X'), num(r, 'LOCATION.Y'))})
        elif r.get('RECORD') == T_PORT:
            ports.append({'name': r.get('NAME', ''),
                          'loc': (num(r, 'LOCATION.X'), num(r, 'LOCATION.Y'))})

    # ---- 连通性 ----
    uf = UnionFind()
    for a, b in segs:
        uf.union(a, b)

    for p in {p for seg in segs for p in seg}:          # 端点压在别人身上
        for a, b in segs:
            if p not in (a, b) and on_seg(p, a, b):
                uf.union(p, a)
    for j in juncs:                                      # 节点
        for a, b in segs:
            if on_seg(j, a, b):
                uf.union(j, a)
    for o in pins:                                       # 引脚
        for a, b in segs:
            if on_seg(o['hot'], a, b):
                uf.union(o['hot'], a)
    for p in ports:                                      # 端口位置
        for a, b in segs:
            if on_seg(p['loc'], a, b):
                uf.union(p['loc'], a)
    by_name = {}
    for p in ports:                                      # 同名端口全局合并
        by_name.setdefault(p['name'], []).append(p['loc'])
    for name, locs in by_name.items():
        for l in locs[1:]:
            uf.union(l, locs[0])

    # ---- 命名 / 归并 ----
    root_names = {}
    for p in ports:
        root_names.setdefault(uf.find(p['loc']), [])
        if p['name'] not in root_names[uf.find(p['loc'])]:
            root_names[uf.find(p['loc'])].append(p['name'])

    nets = {}
    for o in pins:
        rt = uf.find(o['hot'])
        nets.setdefault(rt, {'names': root_names.get(rt, []), 'pins': []})
        nets[rt]['pins'].append(o)
    # 没被电源端口命名的网络：优先用该网络上第一个“有名字的引脚”当网络名
    # （本图即 SW / FB / CB 三个内部节点），实在没有就给 NET_xx
    auto = 0
    for rt, d in nets.items():
        if d['names']:
            continue
        cand = [p['name'] for p in sorted(d['pins'], key=lambda p: (p['des'], p['num']))
                if p['name'] and not p['name'].isdigit()]
        if cand:
            d['names'] = [cand[0]]
        else:
            auto += 1
            d['names'] = ['NET_%02d' % auto]

    # ---- 体检 ----
    dangling = [o for o in pins
                if not any(on_seg(o['hot'], a, b) for a, b in segs)]

    return {'records': recs, 'comp': comp, 'pins': pins, 'nets': nets,
            'segs': segs, 'juncs': juncs, 'ports': ports, 'dangling': dangling}


def main():
    m = build()
    nets = m['nets']
    print('记录 %d 条，元件 %d 个，引脚 %d 个，导线 %d 段，节点 %d 个，网络 %d 个'
          % (len(m['records']), len(m['comp']), len(m['pins']),
             len(m['segs']), len(m['juncs']), len(nets)))
    print()

    order = sorted(nets.items(), key=lambda kv: (-len(kv[1]['pins']), str(kv[1]['names'])))
    for _root, d in order:
        name = ' / '.join(d['names'])
        print('[%s]  %d 脚' % (name, len(d['pins'])))
        for o in sorted(d['pins'], key=lambda o: (o['des'], o['num'])):
            print('    %-5s %-4s %-6s %s' % (o['des'], o['num'], o['name'], o['hot']))
        print()

    print('=== 体检 ===')
    print('悬空引脚: %d 个' % len(m['dangling']))
    for o in m['dangling']:
        print('    %-5s 脚 %-4s %-6s @%s' % (o['des'], o['num'], o['name'], o['hot']))
    multi = [n for n in nets.values() if len(n['names']) > 1]
    print('多名称网络: %d 个' % len(multi))
    for n in multi:
        print('    ' + ' / '.join(n['names']))

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out = DATA_DIR / '网表.csv'
    rows = []
    for _root, d in nets.items():
        name = '/'.join(d['names'])
        for o in d['pins']:
            rows.append([name, o['des'], o['num'], o['name'], '%d,%d' % o['hot']])
    rows.sort(key=lambda r: (r[0], r[1]))
    with open(out, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['网络', '位号', '引脚号', '引脚名', '引脚坐标(文件单位)'])
        w.writerows(rows)
    print()
    print('已写出:', out, '(%d 行)' % len(rows))


if __name__ == '__main__':
    main()
