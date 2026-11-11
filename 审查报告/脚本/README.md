# 审查脚本说明

这套脚本是当初做 `Power.SchDoc` 审查时用的全部代码，从临时目录搬进来了。
不依赖 Altium、不依赖第三方库（只有导出图片那一步要 Pillow），全部跑在本工作区内。

目录关系：

```
D:\ADproject\FOC\
├─ project\FOC\Power.SchDoc        ← 被审查的原理图（只读，脚本不改它）
└─ 审查报告\
   ├─ 原理图审查报告.md             ← 报告正文
   ├─ 资料\                         ← 手册、截图、网表
   └─ 脚本\                         ← 本目录
```

## 文件

| 文件 | 作用 |
|---|---|
| `cfb.py` | OLE 复合文档（CFB）解析，读 `.SchDoc` 里的数据流 |
| `schdoc.py` | SchDoc 记录解析：`FileHeader` → 560 条 `\|RECORD=...\|` 记录；处理 GBK/UTF-8 混排 |
| `netlist.py` | 由导线/节点/引脚热点/电源端口重建网络表，做连通性体检，刷新 `资料\网表.csv` |
| `components.py` | 导出元件清单：位号、型号、Comment、封装、立创料号，并列出没绑料号的位号 |
| `images.py` | 从 `__Previews\Power.SchDocPreview` 还原原理图位图，裁出报告用的 4 张局部图 |
| `download_datasheets.py` | 重新下载 TI / AMS 手册到 `资料\`（已有文件会跳过） |

## 怎么跑

在 `D:\ADproject\FOC\审查报告\脚本` 目录下：

```powershell
python netlist.py          # 打印网络表 + 悬空引脚/重名网络检查，并写出 资料\网表.csv
python components.py       # 打印元件清单
python images.py           # 重新生成 资料\ 里的整页图与局部图
python schdoc.py           # 只统计记录类型（排查用）
python download_datasheets.py
```

脚本里的路径都按“脚本所在位置”推算，不写死盘符，整个 `审查报告` 文件夹挪到别处也能跑。

## 关键实现点（复核别人的解析结果时看这里）

1. **引脚热点在哪**：Altium 的引脚记录里 `Location` 是**贴着元件本体那一端**，
   真正的电气连接点在 `Location + PinLength × 朝向` 处。朝向取 `PinConglomerate` 低两位
   （0=右 1=上 2=左 3=下），文件坐标里 **+Y 是“上”**。这三点如果搞错，整张网表会全错，
   当时是用全部 41 个引脚反向验证过的。
2. **交叉要不要连**：Altium 里两条导线十字交叉、交点不是端点、又没有 Junction，是不连的。
   所以先按“端点落在别人身上”和“Junction”两种情形合并，再做引脚和端口。
3. **导线折点**：一根 `RECORD=27` 可能有多段（`LocationCount` > 2，坐标是 `X1/Y1...Xn/Yn`），
   必须逐段拆开，不能只取首尾两点。
4. **电源端口**：`RECORD=17` 的 `Text` 就是网络名（PGND、+12V…），同名全局合并。
   本图 `VBUS` 和 `+12V` 接在同一根线上，合并后这个网络有两个名字——报告 6.5 就是这么发现的。
