# -*- coding: utf-8 -*-
"""从 Altium 预览文件还原原理图位图，并裁出报告用的局部图。

原理：__Previews\\<sheet>.SchDocPreview 是 INI 文本头 + 十六进制串，
十六进制解出来是 zlib 流，解压后是 1000x662 的 32 位位图（RGBA）。
注意原始位图是上下翻转存放的，这里统一翻正后再输出。

用法:
    python images.py
"""

import re
import sys
import zlib
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
REPORT_DIR = HERE.parent
DATA_DIR = REPORT_DIR / '资料'
PREVIEW = REPORT_DIR.parent / 'project' / 'FOC' / '__Previews' / 'Power.SchDocPreview'

# (输出文件名, 裁切框 left, top, right, bottom)  —— 坐标为翻正后的像素
CROPS = [
    ('图1_输入与母线电容.png', (40, 45, 350, 205)),
    ('图2_5V降压主回路.png', (355, 45, 725, 205)),
    ('图3_反馈分压与输出.png', (645, 55, 905, 285)),
    ('图4_3V3_LDO.png', (145, 275, 460, 415)),
]


def read_hex_value(blob, key):
    i = blob.find(key.encode() + b'=')
    if i < 0:
        return None
    j = blob.find(b'=', i) + 1
    k = blob.find(b'\r\n', j)
    if k < 0:
        k = len(blob)
    return blob[j:k].strip()


def main():
    if not PREVIEW.exists():
        print('找不到预览文件:', PREVIEW)
        return 1

    blob = PREVIEW.read_bytes()
    hexdata = read_hex_value(blob, 'LargeImage')
    if hexdata is None:
        print('预览文件里没有 LargeImage 字段')
        return 1

    raw = zlib.decompress(bytes.fromhex(hexdata.decode('ascii')))
    w = int(read_hex_value(blob, 'LargeImageWidth') or 1000)
    h = int(read_hex_value(blob, 'LargeImageHeight') or len(raw) // 4 // 1000)
    print('位图 %dx%d，解压 %d 字节' % (w, h, len(raw)))

    im = Image.frombytes('RGBA', (w, h), raw).convert('RGB').transpose(Image.FLIP_TOP_BOTTOM)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    im.save(DATA_DIR / '原理图预览.png')
    im.resize((w * 2, h * 2), Image.LANCZOS).save(DATA_DIR / '原理图全页.png')
    print('已写出: 原理图预览.png / 原理图全页.png')

    for name, box in CROPS:
        c = im.crop(box)
        c.resize((c.width * 3, c.height * 3), Image.LANCZOS).save(DATA_DIR / name)
        print('已写出: %s  %dx%d' % (name, c.width * 3, c.height * 3))
    return 0


if __name__ == '__main__':
    sys.exit(main())
