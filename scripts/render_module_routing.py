#!/usr/bin/env python3
"""Render the versioned, presentation-sized routing figures; no runtime changes.

SVG needs only Python; PNG export uses the system rsvg-convert when available.
These are a briefing view of docs/design/module-routing-v1.md, not executable
configuration or a replacement for the planner's method applicability checks.
"""
from html import escape
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/design/figures"
INK = "#152f50"
MUTED = "#58718d"
BLUE = "#245bd6"
TEAL = "#147d83"
LINE = "#d8e3ef"


class Figure:
    def __init__(self, title, subtitle):
        self.items = [f'''<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080">
<title>{escape(title)}</title><desc>{escape(subtitle)}</desc>
<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0L8 4L0 8" fill="none" stroke="#7894b5" stroke-width="1.4"/></marker></defs>
<rect width="1920" height="1080" fill="#f7f9fc"/>
<g font-family="Noto Sans CJK SC, sans-serif">''']
        self.text(80, 68, "DBCI-QC  /  模块化设计", 20, BLUE, 600)
        self.text(80, 128, title, 42, INK, 700)
        self.text(80, 166, subtitle, 24, MUTED)

    def text(self, x, y, value, size=26, color=INK, weight=400):
        self.items.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" font-weight="{weight}">{escape(value)}</text>')

    def rect(self, x, y, w, h, fill="white", stroke=LINE, radius=18):
        self.items.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')

    def arrow(self, points):
        self.items.append(f'<path d="{points}" fill="none" stroke="#7894b5" stroke-width="2.5" marker-end="url(#arrow)"/>')

    def module(self, x, y, w, h, code, title, lines, conditional=False):
        color = TEAL if conditional else BLUE
        self.rect(x, y, w, h, "#f0f9f9" if conditional else "#f3f7ff", "#c5e3e4" if conditional else "#d0def7", 14)
        self.text(x+22, y+33, code, 19, color, 600)
        self.text(x+22, y+72, title, 29, INK, 600)
        for i, value in enumerate(lines):
            self.text(x+22, y+108+i*31, value, 22, MUTED)

    def save(self, name):
        self.text(80, 1044, "模块路由 v1.0  ·  2026-11-06  ·  工程设计基线", 18, MUTED)
        self.items.append("</g></svg>")
        OUT.mkdir(parents=True, exist_ok=True)
        path = OUT / (name+".svg")
        path.write_text("\n".join(self.items), encoding="utf-8")
        if shutil.which("rsvg-convert"):
            subprocess.run(["rsvg-convert", "-o", str(path.with_suffix(".png")), str(path)], check=True)


def overview():
    f = Figure("质控模块与数据流", "统一读入与确认；每份记录做信号检查，数据包增加完整性与一致性核对。")
    f.rect(80, 210, 330, 112)
    f.text(106, 256, "一份记录 / 一组记录", 29, INK, 600)
    f.text(106, 296, "保留原始文件与配套资料", 23, MUTED)
    f.rect(470, 210, 500, 112)
    f.text(498, 249, "M01  文件读取", 29, BLUE, 600)
    f.text(498, 293, "格式、通道、时长、采样率、单位", 24, MUTED)
    f.rect(1030, 210, 810, 112)
    f.text(1058, 249, "M02  信息确认与检查方案", 29, BLUE, 600)
    f.text(1058, 293, "确认模态、分析通道与范围；按技术条件选择方法", 24, MUTED)
    f.arrow("M410 266H457")
    f.arrow("M970 266H1017")
    f.arrow("M1435 322V351H295V380")
    f.arrow("M1435 351V380")

    f.rect(80, 390, 430, 466)
    f.text(106, 433, "数据包核对", 29, INK, 600)
    f.text(106, 470, "有应有清单与核对方案时", 23, MUTED)
    for y, code, title, detail in [
        (497, "D01", "文件完整性", "应到 / 实到、缺件与结构"),
        (607, "D02", "个体及文件对应", "编号、通道、单位、事件"),
        (717, "D03", "同组一致性", "采集配置、表结构、重复线索"),
    ]:
        f.rect(103, y, 384, 97, "#f5f8fc", LINE, 12)
        f.text(122, y+36, code, 20, BLUE, 600)
        f.text(181, y+36, title, 27, INK, 600)
        f.text(122, y+75, detail, 23, MUTED)

    f.rect(550, 390, 1290, 466)
    f.text(578, 433, "每份记录的信号检查", 29, INK, 600)
    f.text(578, 470, "头皮 EEG / ECoG / sEEG / Neuropixels 电压：框架相同，内部方法不同", 23, MUTED)
    f.module(578, 494, 398, 132, "M03 · 默认推荐", "信号完整性", ["缺失、恒值、异常区间"])
    f.module(996, 494, 398, 132, "M04 · 默认推荐", "频谱与干扰", ["PSD、可测频率的工频观察"])
    f.module(1414, 494, 398, 132, "M05 · 默认推荐", "通道质量", ["逐道指标；满足条件再判候选"])
    f.arrow("M777 626V656")
    f.module(578, 670, 606, 154, "M06 · 条件检查", "伪迹线索", ["EEG：辅助导联 / 可用高频带", "ECoG、sEEG：手动研究扩展"], True)
    f.module(1206, 670, 606, 154, "M07 · 条件检查", "事件与时间", ["已有登记的事件表或睡眠分期", "核对位置与覆盖范围"], True)
    f.arrow("M295 856V895")
    f.arrow("M1195 856V895")

    f.rect(80, 908, 430, 98, "#eaf1ff", "#c6d6f5", 14)
    f.text(106, 949, "数据集总览", 29, BLUE, 600)
    f.text(106, 984, "资料问题 + 各份信号报告", 23, MUTED)
    f.rect(550, 908, 1290, 98, "#eaf1ff", "#c6d6f5", 14)
    f.text(578, 949, "M08 分项汇总  →  M09 单份报告", 29, BLUE, 600)
    f.text(578, 984, "候选位置、分项结果、已评范围、未评原因；EEG 满足评分条件时提供试行分数", 23, MUTED)
    f.arrow("M550 957H519")
    f.text(1130, 1044, "逻辑数据流；数据集批量启动信号检查尚未接入", 18, MUTED)
    f.save("module-routing-v1")


def conditions():
    f = Figure("数据条件与启用方法", "基础方法随模态切换；辅助导联、参考比较组与事件表，决定增加哪些检查。")
    f.rect(80, 215, 1760, 610)
    f.rect(80, 215, 1760, 65, "#eaf1ff", "#eaf1ff", 16)
    xs = [108, 445, 975, 1510]
    for x, t in zip(xs, ["输入数据", "默认检查", "按条件增加", "结果"]):
        f.text(x, 258, t, 25, BLUE, 600)
    rows = [
        (["人类连续头皮 EEG"], ["M03 完整性 · M04 PSD / 工频", "M05 PREP 非空间分项"],
         ["M06 辅助导联 / 高频线索", "M07 已登记事件 / 分期"], ["分项与候选", "符合条件时试行评分"]),
        (["连续 ECoG / sEEG"], ["M03 完整性 · M04 描述性频谱", "M05 逐触点统计"],
         ["M07 已登记事件", "FieldTrip 差分候选（手选）"], ["基础描述报告", "不套头皮判坏与评分"]),
        (["Neuropixels 电压", "连续 AP / LF 单流"], ["M03 完整性 · M04 描述性频谱", "M05 逐通道统计"],
         ["AP：SpikeInterface（手选）", "M07 已登记事件"], ["电压层报告", "不含分选单元质控"]),
        (["数据集"], ["D01 文件 · D02 个体对应", "D03 同组配置与重复线索"],
         ["各记录按已确认模态运行", "需要清单、映射与比较组"], ["总览 + 单份报告", "不平均不同模态分数"]),
    ]
    for n, cols in enumerate(rows):
        top = 280+n*136
        if n:
            f.items.append(f'<path d="M108 {top}H1812" stroke="{LINE}"/>')
        for c, lines in enumerate(cols):
            for i, t in enumerate(lines):
                f.text(xs[c], top+52+i*38, t, 24 if c != 3 else 22, INK if i == 0 else MUTED, 600 if c == 0 and i == 0 else 400)

    f.text(80, 876, "三个最直观的触发条件", 27, INK, 600)
    cards = [
        (80, "比较组有依据、默认 ≥4 道", "启用 PREP 组内相对判坏"),
        (680, "ECG / EOG 已确认且同钟", "启用相应导联锁时检查"),
        (1280, "事件 / 分期表已登记", "启用 M07 时间与覆盖核对"),
    ]
    for x, first, second in cards:
        f.rect(x, 899, 560, 102, "#f0f9f9", "#c5e3e4", 14)
        f.text(x+22, 937, first, 25, TEAL, 600)
        f.text(x+22, 975, second, 24, MUTED)
    f.text(930, 1044, "疾病标签不单独改阈值；缺条件仅影响对应方法，未评不记作满分", 18, MUTED)
    f.save("module-conditions-v1")


if __name__ == "__main__":
    overview()
    conditions()
    print(OUT)
