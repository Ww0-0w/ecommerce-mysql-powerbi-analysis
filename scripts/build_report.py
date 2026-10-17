"""Build the corrected Chinese analysis report from MySQL aggregate exports."""
from __future__ import annotations

import csv
from datetime import datetime
from decimal import Decimal
import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, KeepTogether, PageBreak,
                                PageTemplate, Paragraph, Spacer, Table, TableStyle)


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "dashboard" / "data"
REPORT = ROOT / "report"
RESULTS = json.loads((REPORT / "analysis_results.json").read_text(encoding="utf-8"))


def records(name: str) -> list[dict[str, str]]:
    with (DATA / f"{name}.csv").open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


O = records("overview")[0]
MONTHS = records("monthly")
CATS = records("categories")
RFM = records("rfm")
REPEAT = records("repeat")
EXPERIMENT = records("experiment")
EXTRA = RESULTS["extras"]


def d(value: str | int | float) -> Decimal:
    return Decimal(str(value))


def money(value: str | int | float, decimals: int = 0) -> str:
    return f"¥{d(value):,.{decimals}f}"


def pct(value: str | int | float, decimals: int = 2) -> str:
    return f"{d(value):.{decimals}f}%"


def pp(value: str | int | float) -> str:
    return f"{d(value):+.2f}%"


gmv = d(O["gmv"])
aov = d(O["aov"])
median = d(EXTRA["median_order_payment"][0][0])
one_time = int(EXTRA["one_time_buyers"][0][0])
repeat_gmv_pct = d(EXTRA["repeat_buyer_gmv_pct"][0][0])
top3 = sum(d(row["gmv_share_pct"]) for row in CATS[:3])
jan, feb = MONTHS[-2:]
base30 = next(row for row in REPEAT if row["window_days"] == "30")
base = d(base30["repeat_rate_pct"])
target5 = d(one_time) * Decimal("0.05") * aov
target10 = target5 * 2
missing_reviews = 10777
miss_rate = d(missing_reviews) / d(O["source_orders"]) * 100
excluded_pct = d(O["excluded_orders"]) / d(O["source_orders"]) * 100


def build_markdown() -> None:
    monthly_rows = "\n".join(
        f"| {r['month_key']} | {r['calendar_days']} | {money(r['gmv'])} | "
        f"{money(r['daily_gmv'])} | "
        f"{pp(r['monthly_gmv_mom_pct']) if r['monthly_gmv_mom_pct'] else '—'} | "
        f"{pp(r['daily_gmv_mom_pct']) if r['daily_gmv_mom_pct'] else '—'} |" for r in MONTHS)
    rfm_rows = "\n".join(
        f"| {r['segment']} | {r['buyers']} | {pct(r['buyer_share_pct'],1)} | "
        f"{pct(r['gmv_share_pct'],1)} | {money(r['avg_spend'])} | "
        f"{d(r['avg_orders']):.2f} |" for r in RFM)
    repeat_rows = "\n".join(
        f"| {r['window_days']} | {r['eligible_buyers']} | {r['repeat_buyers']} | "
        f"{pct(r['repeat_rate_pct'])} |" for r in REPEAT)
    exp_rows = "\n".join(
        f"| +{r['relative_lift_pct']}% | {pct(r['target_pct'])} | "
        f"{d(r['absolute_lift_pp']):.2f} pp | {int(r['sample_per_arm']):,} | "
        f"{int(r['sample_total']):,} |" for r in EXPERIMENT)
    text = f"""# 某电商平台用户消费数据分析报告（可复现版）

> 数据运营作品集｜分析引擎：MySQL 8.0｜数据截至 {EXTRA['asof_ts'][0][0]}｜基于脱敏合成数据，非真实业务业绩。

## 执行摘要

15,000 笔原始订单中有 {O['excluded_orders']} 笔处于已取消、已退款或待付款状态；成交订单 {O['valid_orders']} 笔，涉及 {O['buyers']} 名购买用户，实付 GMV **{money(gmv,2)}**，客单价 **{money(aov,2)}**。复购用户贡献 **{pct(repeat_gmv_pct,1)}** GMV；{one_time:,} 名用户仅有一笔成交订单。以完整 30×24 小时观察窗衡量，首单后复购基线为 **{base30['repeat_buyers']}/{base30['eligible_buyers']} = {pct(base)}**。

2026 年 2 月整月 GMV 相对 1 月为 **{pp(feb['monthly_gmv_mom_pct'])}**，按 28/31 个日历天归一后为 **{pp(feb['daily_gmv_mom_pct'])}**。仅凭五个月数据，不能把该变动判为“正常波动”或因果性下滑。

## 1. 数据、清洗与分析边界

数据由 users（5,000）、products（2,000）、orders（15,000）、user_behaviors（30,000）、user_features（5,000）和 product_features（2,000）六张 CSV 构成。所有字段先原样装入 MySQL；分析指标只从订单及基础维表重新计算，合成特征表用于审计，不作为可信结果源。

- 成交订单：排除“已取消、已退款、待付款”，剔除率 **{pct(excluded_pct,1)}**。
- 金额：15,000 笔均满足 `total_amount - discount = actual_payment`（容差 ¥0.01）；只有 **{EXTRA['quantity_price_matches'][0][0]}** 笔满足 `quantity × unit_price ≈ total_amount`，因此不能用数量乘单价重算 GMV。
- `user_features.days_since_last_order` 在 5,000 行中全部为 999；R 指标从成交订单时间重算。评价分缺失 {missing_reviews:,} 笔（{pct(miss_rate,1)}），不据此作全体用户满意度结论。
- 原始订单覆盖 2025-09-06 至 2026-03-05。2025-09 与 2026-03 均为残月，整体统计纳入，月度环比只比较 2025-10 至 2026-02。

## 2. 经营现状与待诊断问题

成交 GMV **{money(gmv,2)}**，平均每单 **{d(O['units_per_order']):.2f}** 件。客单价均值 {money(aov,2)}，中位数 {money(median,2)}，均值约为中位数的 **{aov/median:.2f} 倍**；典型订单金额宜同时看中位数。

| 月份 | 天数 | 整月 GMV | 日均 GMV | 整月环比 % | 日均环比 % |
|---|---:|---:|---:|---:|---:|
{monthly_rows}

看到的问题依次是：① 2 月整月下滑是否主要来自月长；② 高价品类集中是否放大波动；③ 均值是否高估典型订单；④ 如何验证一次性用户的第二单增长方案。

## 3. 诊断：月长、品类和用户结构

1 月 GMV {money(jan['gmv'])}、日均 {money(jan['daily_gmv'])}；2 月 GMV {money(feb['gmv'])}、日均 {money(feb['daily_gmv'])}。整月 **{pp(feb['monthly_gmv_mom_pct'])}** 与日均 **{pp(feb['daily_gmv_mom_pct'])}** 相差约 **{abs(d(feb['monthly_gmv_mom_pct'])-d(feb['daily_gmv_mom_pct'])):.2f} 个百分点**，主要是 2 月比 1 月少 3 天。日均 GMV 仍有下降，需继续观察，不能直接判定策略应对强度。

恒等式 `日均 GMV = (月购买人数/日历天数) × 人均订单数 × 客单价` 可重构两个自然月的日均 GMV；这里“月购买人数/天数”仅是代数分解，不等同逐日去重购买人数。

手机数码、家用电器和汽车用品依次贡献 {pct(CATS[0]['gmv_share_pct'],1)}、{pct(CATS[1]['gmv_share_pct'],1)}、{pct(CATS[2]['gmv_share_pct'],1)} GMV，合计 **{pct(top3,1)}**。集中度提示风险假设，但尚无价格、毛利和需求冲击数据证明风险已发生。

仅下过一笔成交订单的用户为 **{one_time:,}/{O['buyers']} = {pct(d(one_time)/d(O['buyers'])*100,1)}**；有两笔及以上成交订单的用户贡献 **{pct(repeat_gmv_pct,1)}** GMV。这是用户结构描述，不等同留存因果分析。

## 4. RFM 分层

基准时点为数据中最大的订单时间 {EXTRA['asof_ts'][0][0]}，对象为 {O['buyers']} 名成交用户。R = 距最近一次成交的天数，F = 成交订单数，M = 实付累计额。各维按排序分三组：R 从久到近为 1–3 分，F/M 从低到高为 1–3 分；并列值按 `user_id` 稳定排序，确保每次运行一致。核心：R/F/M 均 ≥2；流失风险：R<2 且 F/M≥2；成长潜力：R≥2 且非核心；其余为一般。

| 分群 | 人数 | 人数占比 | GMV 占比 | 人均累计消费 | 人均订单数 |
|---|---:|---:|---:|---:|---:|
{rfm_rows}

RFM 仅说明历史购买特征；“流失风险”是规则名称，并未建立真实流失预测模型。

## 5. 首单后复购基线与策略测算

首单由 `(order_date, order_id)` 确定；后续成交订单须在首单之后、且不晚于首单后 `N×24` 小时。仅纳入距数据截止时点至少有 N 天完整观察窗的用户。同一时间戳的不同订单用订单 ID 排序。30 天口径纳入 **{base30['eligible_buyers']}** 人，排除 **{int(O['buyers'])-int(base30['eligible_buyers'])}** 人。

| 窗口（天） | 有完整观察窗人数 | 窗内再次成交人数 | 复购率 |
|---:|---:|---:|---:|
{repeat_rows}

建议把“一次性用户第二单券”作为待检验策略。以当前 {one_time:,} 名一次性用户为示意规模、假设绝对复购率增加 5/10 个百分点，并把增量订单按历史均值 {money(aov,2)} 估算，增量**毛 GMV**约为 **{money(target5)} / {money(target10)}**。该估算未扣券成本、替代购买、退款和毛利，不能称为净收益或最高性价比。

## 6. A/B 实验设计（尚未实际开展）

实验单位为 `user_id`，对照组维持原策略，实验组发第二单券；同时期随机分流。主要指标是首单后 30 天复购率，另监控退款率、客单价与实际毛利。双侧 α=0.05、功效 80%；以本项目可复现的 **{pct(base)}** 为初步对照率，按两比例正态近似公式重新计算：

| 目标相对提升 | 目标率 | 绝对差 | 每组样本 | 合计样本 |
|---:|---:|---:|---:|---:|
{exp_rows}

正式实验若只在首单后 7 天仍未复购的人群发券，须重算该合格人群的对照基线和样本量；不能直接把全体首单用户基线套到已筛选人群。只有达到预设显著性和至少 3 个百分点绝对提升，且护栏未恶化，才考虑推广。当前数据没有优惠券曝光、随机分组或成本记录，因此无法评价真实策略效果与利润。

原报告的 735 人/组示例仅是**模拟演示**。若按其四舍五入比率对应的 267/735 与 303/735 计算，双侧比例检验 p≈0.054，95% 置信区间约为 [-0.08, +9.87] 个百分点，未达到 0.05 显著性。频率学置信区间表示构造方法在重复抽样中的覆盖率，并非“固定真实效果有 95% 概率落在本次区间”。

## 7. 与原报告的主要差异

| 项目 | 原报告 | 本次可复算结果 | 处理 |
|---|---:|---:|---|
| 剔除订单比例 | 15.1% | {pct(excluded_pct,1)} | 纠正分母计算 |
| 数量×单价约等于总金额 | 3/15,000 | {EXTRA['quantity_price_matches'][0][0]}/15,000（¥0.01 容差） | 明确比较容差 |
| 30 天首单复购 | 1,569/4,400 = 35.66% | {base30['repeat_buyers']}/{base30['eligible_buyers']} = {pct(base)} | 明确时间戳、并列订单与成交状态 |
| +20% 相对提升每组样本 | 735 | {next(r['sample_per_arm'] for r in EXPERIMENT if r['relative_lift_pct']=='20.00')} | 随新基线重算 |
| 2 月整月/日均环比 | −13.6% / −4.3% | {pp(feb['monthly_gmv_mom_pct'])} / {pp(feb['daily_gmv_mom_pct'])} | 数值基本一致；不推断“正常” |

## 8. 结论与局限

优先建立按月长归一化的经营监控，并将复购基线与 RFM 分群作为周度观察指标。第二单券可进入实验设计，但效果、利润和最优投入尚未经验证。数据为脱敏合成集；评价缺失较高、特征表含失效字段，且缺少成本、曝光和随机实验日志。所有数字可从仓库 SQL 与汇总 CSV 追溯；公开 PBIX 只包含聚合结果。
"""
    (REPORT / "analysis_report.md").write_text(text, encoding="utf-8")


NAVY = colors.HexColor("#17314C")
TEAL = colors.HexColor("#07857D")
PALE = colors.HexColor("#EFF6F5")
GRAY = colors.HexColor("#526477")
LIGHT = colors.HexColor("#F5F7FA")


def pdf_styles() -> dict[str, ParagraphStyle]:
    pdfmetrics.registerFont(TTFont("SimHei", r"C:\Windows\Fonts\simhei.ttf"))
    pdfmetrics.registerFontFamily("SimHei", normal="SimHei", bold="SimHei",
                                  italic="SimHei", boldItalic="SimHei")
    return {
        "title": ParagraphStyle("title", fontName="SimHei", fontSize=22, leading=30,
                                textColor=NAVY, spaceAfter=14),
        "subtitle": ParagraphStyle("subtitle", fontName="SimHei", fontSize=9,
                                   leading=15, textColor=GRAY, spaceAfter=18),
        "h1": ParagraphStyle("h1", fontName="SimHei", fontSize=13, leading=20,
                             textColor=NAVY, spaceBefore=17, spaceAfter=8),
        "h2": ParagraphStyle("h2", fontName="SimHei", fontSize=10.5, leading=17,
                             textColor=TEAL, spaceBefore=10, spaceAfter=5),
        "body": ParagraphStyle("body", fontName="SimHei", fontSize=8.6, leading=15,
                               textColor=NAVY, wordWrap="CJK", spaceAfter=7),
        "small": ParagraphStyle("small", fontName="SimHei", fontSize=7.3, leading=11,
                                textColor=NAVY, wordWrap="CJK"),
        "card": ParagraphStyle("card", fontName="SimHei", fontSize=9.2, leading=16,
                               textColor=NAVY, wordWrap="CJK"),
    }


def table(headers: list[str], lines: list[list[str]], widths: list[float], styles) -> Table:
    safe = lambda x: str(x).replace("¥", "人民币 ").replace("−", "-")
    cells = [[Paragraph(safe(x), styles["small"]) for x in headers]]
    cells += [[Paragraph(safe(x), styles["small"]) for x in row] for row in lines]
    t = Table(cells, colWidths=widths, repeatRows=1, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), PALE),
        ("TEXTCOLOR", (0,0), (-1,0), NAVY),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white,LIGHT]),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("LEFTPADDING", (0,0), (-1,-1), 7),
        ("RIGHTPADDING", (0,0), (-1,-1), 7),
        ("LINEBELOW", (0,0), (-1,0), 0.8, TEAL),
    ]))
    return t


def build_pdf() -> None:
    styles = pdf_styles()
    output = REPORT / "analysis_report.pdf"
    doc = BaseDocTemplate(str(output), pagesize=A4, leftMargin=18*mm,
                          rightMargin=18*mm, topMargin=19*mm, bottomMargin=17*mm,
                          title="某电商平台用户消费数据分析报告｜可复现版")
    frame = Frame(doc.leftMargin,doc.bottomMargin,doc.width,doc.height,
                  leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)
    def decorate(canvas, document):
        canvas.saveState()
        canvas.setStrokeColor(TEAL)
        canvas.setLineWidth(1)
        canvas.line(18*mm,15*mm,A4[0]-18*mm,15*mm)
        canvas.setFont("SimHei",7)
        canvas.setFillColor(GRAY)
        canvas.drawString(18*mm,10*mm,"MySQL 8.0 · 脱敏合成数据 · 可复现分析")
        canvas.drawRightString(A4[0]-18*mm,10*mm,f"{document.page}")
        canvas.restoreState()
    doc.addPageTemplates(PageTemplate(id="main",frames=frame,onPage=decorate))
    story = []
    P=lambda text,kind="body": Paragraph(text.replace("¥", "人民币 ").replace("−", "-"),styles[kind])
    H=lambda text: story.append(P(text,"h1"))
    B=lambda text: story.append(P(text))
    story += [P("某电商平台用户消费<br/>数据分析报告","title"),
              P(f"可复现版 · MySQL 8.0 · 数据截至 {EXTRA['asof_ts'][0][0]} · 作品集项目","subtitle")]
    story.append(table(["成交 GMV","成交订单","购买用户","30 天复购基线"],
                       [[money(gmv),O['valid_orders'],O['buyers'],pct(base)]],
                       [41*mm,39*mm,39*mm,39*mm],styles))
    H("执行摘要")
    B(f"按实付金额计算，{O['valid_orders']} 笔成交订单产生 {money(gmv,2)} GMV。"
      f"复购用户贡献 {pct(repeat_gmv_pct,1)} GMV，但 {one_time:,} 名购买用户仅有一笔成交订单。"
      f"首单后完整 30 天观察窗的自然复购率为 {base30['repeat_buyers']}/{base30['eligible_buyers']} = {pct(base)}。")
    B(f"2 月整月 GMV 环比 {pp(feb['monthly_gmv_mom_pct'])}；按 28/31 天归一后，"
      f"日均 GMV 环比 {pp(feb['daily_gmv_mom_pct'])}。这说明月长解释了大部分表面跌幅，"
      "剩余变化仍需更多月份和业务信息验证。")
    H("01  数据处理与可信口径")
    story.append(table(["检查","结果","分析处理"],[
        ["原始/成交订单",f"15,000 / {O['valid_orders']}",f"剔除 {O['excluded_orders']} 笔（{pct(excluded_pct,1)}）"],
        ["金额恒等式","15,000/15,000 成立","以实付金额为成交 GMV"],
        ["数量×单价",f"仅 {EXTRA['quantity_price_matches'][0][0]}/15,000 相符","不用于推算 GMV"],
        ["最近购买间隔","5,000 行均为 999","由成交订单时间重算"],
        ["评价分缺失",f"{missing_reviews:,} 笔（{pct(miss_rate,1)}）","不外推总体满意度"],
    ],[37*mm,48*mm,73*mm],styles))
    B("六张源 CSV 全部装入独立数据库；特征表用于审计。整体统计含首尾残月，月度环比只用 2025-10 至 2026-02。")
    H("02  规模与分布")
    B(f"客单价均值 {money(aov,2)}，中位数 {money(median,2)}，均值为中位数的 {aov/median:.2f} 倍；"
      f"平均每单 {d(O['units_per_order']):.2f} 件。单看均值会高估典型订单金额。")
    story.append(PageBreak())
    H("03  月度趋势：先处理月长")
    story.append(table(["月份","天数","整月 GMV","日均 GMV","整月环比","日均环比"],[
        [r["month_key"],r["calendar_days"],money(r["gmv"]),money(r["daily_gmv"]),
         pp(r["monthly_gmv_mom_pct"]) if r["monthly_gmv_mom_pct"] else "—",
         pp(r["daily_gmv_mom_pct"]) if r["daily_gmv_mom_pct"] else "—"] for r in MONTHS
    ],[24*mm,16*mm,34*mm,34*mm,25*mm,25*mm],styles))
    B(f"1 月与 2 月的整月环比为 {pp(feb['monthly_gmv_mom_pct'])}，日均环比为"
      f" {pp(feb['daily_gmv_mom_pct'])}，相差约"
      f" {abs(d(feb['monthly_gmv_mom_pct'])-d(feb['daily_gmv_mom_pct'])):.2f} 个百分点。"
      "恒等式为：日均 GMV = (月购买人数÷日历天数)×人均订单数×客单价。"
      "五个月不足以断言 2 月的日均变动属于正常波动。")
    H("04  品类与用户结构")
    story.append(table(["品类","成交 GMV","GMV 占比"],[
        [r["category"],money(r["gmv"]),pct(r["gmv_share_pct"],1)] for r in CATS[:6]
    ],[53*mm,56*mm,49*mm],styles))
    B(f"前三大高价品类合计占 {pct(top3,1)} GMV。集中度值得监控，但需毛利、价格和需求数据才能测算风险。"
      f"仅有一笔成交订单的用户 {one_time:,} 人（{pct(d(one_time)/d(O['buyers'])*100,1)}）；"
      f"复购用户贡献 {pct(repeat_gmv_pct,1)} GMV。")
    H("05  RFM 分群")
    B("R 按距最近成交的天数从久到近评分；F 按成交订单数、M 按累计实付从低到高评分。"
      "各维用 NTILE(3)，并列值用 user_id 稳定排序。分群规则详见可编辑报告与 SQL。")
    story.append(table(["分群","人数","人数占比","GMV 占比","人均消费"],[
        [r["segment"],r["buyers"],pct(r["buyer_share_pct"],1),
         pct(r["gmv_share_pct"],1),money(r["avg_spend"])] for r in RFM
    ],[46*mm,23*mm,30*mm,30*mm,29*mm],styles))
    story.append(PageBreak())
    H("06  首单后复购基线")
    B("首单按订单时间与订单 ID 排序。只统计成交订单；后续订单须在首单之后、且不晚于 N×24 小时。"
      f"30 天观察窗纳入 {base30['eligible_buyers']} 人，排除"
      f" {int(O['buyers'])-int(base30['eligible_buyers'])} 人。")
    story.append(table(["观察窗","完整观察人数","再次成交人数","复购率"],[
        [r["window_days"]+" 天",r["eligible_buyers"],r["repeat_buyers"],pct(r["repeat_rate_pct"])]
        for r in REPEAT
    ],[31*mm,43*mm,43*mm,41*mm],styles))
    B(f"以 {one_time:,} 名一次性用户为示意规模、假设绝对复购率上升 5/10 个百分点，"
      f"按历史 AOV 估计增量毛 GMV 约 {money(target5)} / {money(target10)}。"
      "缺少券成本、替代购买与毛利，不能写成净收益。")
    H("07  A/B 实验：设计与可行性")
    B("按 user_id 随机分流，同期比较对照组与第二单券组。主要指标为首单后 30 天复购率；"
      "护栏为退款率、AOV 与真实毛利。双侧 α=0.05，功效 80%。以下样本量基于本次 34.91% 初步基线。")
    story.append(table(["相对提升","目标率","绝对差","每组样本","总样本"],[
        ["+"+r["relative_lift_pct"]+"%",pct(r["target_pct"]),
         f"{d(r['absolute_lift_pp']):.2f} pp",f"{int(r['sample_per_arm']):,}",
         f"{int(r['sample_total']):,}"] for r in EXPERIMENT
    ],[30*mm,30*mm,31*mm,34*mm,33*mm],styles))
    B("若在首单后第 7 天仅向尚未复购者发券，正式实验须对该合格人群重算基线和样本量。"
      "没有发券日志、随机分组与成本记录，本项目不能评估真实因果效果或利润。")
    B("原报告 735 人/组的 36.33% 对 41.22% 仅为模拟教学示例；"
      "以 267/735 与 303/735 近似，双侧检验 p≈0.054，95% 区间约 [-0.08,+9.87] pp，"
      "未达到 0.05 阈值。")
    story.append(PageBreak())
    H("08  原报告差异与修正")
    story.append(table(["项目","原报告","本次复算","处理"],[
        ["剔除订单比例","15.1%",pct(excluded_pct,1),"纠正分母"],
        ["数量×单价吻合","3/15,000",f"{EXTRA['quantity_price_matches'][0][0]}/15,000","注明 ¥0.01 容差"],
        ["30 天复购","1,569/4,400；35.66%",
         f"{base30['repeat_buyers']}/{base30['eligible_buyers']}；{pct(base)}","确定完整时间规则"],
        ["+20% 效果每组样本","735",next(r['sample_per_arm'] for r in EXPERIMENT if r['relative_lift_pct']=='20.00'),"按新基线重算"],
        ["2 月整月/日均环比","−13.6% / −4.3%",
         f"{pp(feb['monthly_gmv_mom_pct'])} / {pp(feb['daily_gmv_mom_pct'])}","数值相符；不推断正常"],
    ],[34*mm,43*mm,49*mm,32*mm],styles))
    H("结论与下一步")
    B("优先把月长归一化趋势、30 天复购基线与 RFM 结构纳入固定看板。"
      "第二单券可进入正式实验设计；需先定义合格人群和触达时点，再重算样本量。"
      "在收集毛利和成本前，不宣称最高性价比或实际增量收益。")
    H("数据边界与复现")
    B("六张 CSV 为脱敏合成数据；评价分缺失较高，现有特征表含失效字段。"
      "SQL 与汇总数据可在仓库中逐步复现；公开 PBIX 仅含汇总表，不含用户级记录。"
      "原始 CSV 不公开，面试官可审阅来源清单、质量检查和全部计算代码。")
    B("置信区间反映方法在重复抽样下的覆盖率，不表示固定真实效果有 95% 的概率位于本次区间。")
    doc.build(story)
    print(output)


if __name__ == "__main__":
    REPORT.mkdir(parents=True,exist_ok=True)
    build_markdown()
    build_pdf()
