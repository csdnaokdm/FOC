# -*- coding: utf-8 -*-
"""Altium 原理图文件（OLE 复合文档 / CFB）解析器。

只依赖标准库。用于打开 .SchDoc / .PcbDoc 这类 Windows 复合文档，
按流名读取内部的 FileHeader 等数据流。

用法:
    from cfb import CFB
    c = CFB(open(path, 'rb').read())
    c.names()            # 列出所有流
    c.stream('FileHeader')
"""

import struct

FREE = 0xFFFFFFFF
END = 0xFFFFFFFE


class CFB:
    def __init__(self, data):
        self.d = data
        assert data[:8] == bytes.fromhex('D0CF11E0A1B11AE1'), '不是 OLE 复合文档'
        self.sector_size = 1 << struct.unpack_from('<H', data, 30)[0]
        self.mini_sector_size = 1 << struct.unpack_from('<H', data, 32)[0]
        self.num_fat = struct.unpack_from('<I', data, 44)[0]
        self.first_dir = struct.unpack_from('<I', data, 48)[0]
        self.mini_cutoff = struct.unpack_from('<I', data, 56)[0]
        self.first_minifat = struct.unpack_from('<I', data, 60)[0]
        self.num_minifat = struct.unpack_from('<I', data, 64)[0]
        self.first_difat = struct.unpack_from('<I', data, 68)[0]
        self.num_difat = struct.unpack_from('<I', data, 72)[0]

        # --- DIFAT -> FAT 扇区列表 ---
        difat = list(struct.unpack_from('<109I', data, 76))
        sect = self.first_difat
        for _ in range(self.num_difat):
            if sect >= 0xFFFFFFFA:
                break
            off = self.sector_offset(sect)
            entries = list(struct.unpack_from('<%dI' % (self.sector_size // 4), data, off))
            difat.extend(entries[:-1])
            sect = entries[-1]
        fat_sectors = [s for s in difat if s < 0xFFFFFFFA][:self.num_fat]

        self.fat = []
        for s in fat_sectors:
            off = self.sector_offset(s)
            self.fat.extend(struct.unpack_from('<%dI' % (self.sector_size // 4), data, off))

        # --- 目录项 ---
        self.dir_stream = self.read_chain(self.first_dir)
        self.entries = []
        for i in range(len(self.dir_stream) // 128):
            e = self.dir_stream[i * 128:(i + 1) * 128]
            if len(e) < 128:
                break
            nlen = struct.unpack_from('<H', e, 64)[0]
            name = e[:max(0, nlen - 2)].decode('utf-16-le', 'replace') if 2 <= nlen <= 64 else ''
            self.entries.append({
                'name': name,
                'type': e[66],
                'start': struct.unpack_from('<I', e, 116)[0],
                'size': struct.unpack_from('<I', e, 120)[0],
                'index': i,
            })

        root = self.entries[0]
        self.mini_stream = (self.read_chain(root['start'])[:root['size']]
                            if root['start'] < 0xFFFFFFFA else b'')
        self.minifat = []
        if self.num_minifat:
            mf = self.read_chain(self.first_minifat)
            self.minifat = list(struct.unpack_from('<%dI' % (len(mf) // 4), mf, 0))

    def sector_offset(self, s):
        return 512 + s * self.sector_size

    def read_chain(self, start):
        out, s, guard = [], start, 0
        while s < 0xFFFFFFFA and guard < 1000000:
            off = self.sector_offset(s)
            out.append(self.d[off:off + self.sector_size])
            s = self.fat[s] if s < len(self.fat) else END
            guard += 1
        return b''.join(out)

    def read_mini_chain(self, start, size):
        out, s, guard = [], start, 0
        while s < 0xFFFFFFFA and guard < 1000000:
            out.append(self.mini_stream[s * self.mini_sector_size:(s + 1) * self.mini_sector_size])
            s = self.minifat[s] if s < len(self.minifat) else END
            guard += 1
        return b''.join(out)[:size]

    def names(self):
        return [(e['name'], e['type'], e['size']) for e in self.entries]

    def stream(self, name):
        for e in self.entries:
            if e['name'] == name and e['type'] == 2:
                if e['size'] < self.mini_cutoff:
                    return self.read_mini_chain(e['start'], e['size'])
                return self.read_chain(e['start'])[:e['size']]
        return None
