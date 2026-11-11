# -*- coding: utf-8 -*-
"""导出原理图元件清单：位号、型号、参数、封装、立创料号。

用法:
    python components.py            # 打印到控制台
    python components.py > 清单.txt
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from netlist import build


def main():
    m = build()
    comp = m['comp']
    pins_by_owner = {}
    for p in m['pins']:
        pins_by_owner.setdefault(p['owner'], []).append(p)

    print('%-6s %-22s %-30s %-10s %-14s %s'
          % ('位号', 'LibReference', 'Comment(值)', '立创料号', '封装', '引脚数'))
    print('-' * 110)
    for i in sorted(comp, key=lambda k: comp[k]['des']):
        c = comp[i]
        print('%-6s %-22s %-30s %-10s %-14s %d'
              % (c['des'], c['lib'][:22], c['value'][:30], c['lcsc'] or '—',
                 c['footprint'][:14] or '—', len(pins_by_owner.get(i, []))))

    print()
    print('=== 未绑定立创料号的位号 ===')
    missing = [comp[i]['des'] for i in comp if not comp[i]['lcsc']]
    print(', '.join(sorted(missing)) if missing else '无')

    print()
    print('=== 关键参数（有值的） ===')
    for i in sorted(comp, key=lambda k: comp[k]['des']):
        c = comp[i]
        interesting = {k: v for k, v in c['params'].items()
                       if k.lower() in ('comment', 'value', 'package', 'footprintname',
                                        'voltage rating', 'tolerance', 'current rating',
                                        'current - saturation(isat)', 'dc resistance(dcr)')}
        if interesting:
            print('%s:' % c['des'])
            for k, v in interesting.items():
                print('    %-26s %s' % (k, v))
            if c['lcsc']:
                print('    %-26s %s' % ('SupplierPart', c['lcsc']))


if __name__ == '__main__':
    main()
