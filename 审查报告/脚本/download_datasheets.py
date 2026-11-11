# -*- coding: utf-8 -*-
"""下载本次审查用到的芯片手册到 资料\\ 目录（可选，文件已存在则跳过）。

说明:
  * LMR51430 用 TI 原厂 PDF（与立创商城 C5185863 商品页提供的是同一份）。
  * AMS1117 用 Advanced Monolithic Systems 原厂 PDF。
  * 本机 schannel 对 ti.com 握手失败，所以这里用 Python 自带的 OpenSSL 栈。

用法:
    python download_datasheets.py
"""

import ssl
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE.parent / '资料'

URLS = {
    'TI-LMR51430.pdf': 'https://www.ti.com/lit/ds/symlink/lmr51430.pdf',
    'AMS1117-AMS.pdf': 'http://www.advanced-monolithic.com/pdf/ds1117.pdf',
}

# 立创商城商品页（备查）
LCSC_PAGES = {
    'LMR51430XDDCR (C5185863)': 'https://item.szlcsc.com/5856347.html',
    'AMS1117-3.3': 'https://item.szlcsc.com/420485.html',
}


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    for name, url in URLS.items():
        out = DATA_DIR / name
        if out.exists() and out.stat().st_size > 10000:
            print('已存在，跳过:', name)
            continue
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            data = urllib.request.urlopen(req, timeout=60, context=ctx).read()
            if data[:5] != b'%PDF-':
                print('不是 PDF，放弃:', name)
                continue
            out.write_bytes(data)
            print('已下载:', name, len(data), '字节')
        except Exception as e:                          # noqa: BLE001
            print('下载失败:', name, type(e).__name__, e)

    print()
    print('立创商城对应页面（备查）:')
    for k, v in LCSC_PAGES.items():
        print('  %-26s %s' % (k, v))


if __name__ == '__main__':
    main()
