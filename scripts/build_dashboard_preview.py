"""Render an account-free static preview from the same MySQL aggregates as PBIX."""
from __future__ import annotations

import csv
from pathlib import Path

from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "dashboard" / "data"
OUT = ROOT / "dashboard" / "dashboard_preview.pdf"
W, H = 1280, 720
NAVY = colors.HexColor("#122A43")
TEAL = colors.HexColor("#087F78")
MINT = colors.HexColor("#DDF2EF")
PAPER = colors.HexColor("#F4F7FA")
GRAY = colors.HexColor("#5A6C7E")
GOLD = colors.HexColor("#F0B45A")
WHITE = colors.white


def rows(name):
    with (DATA / f"{name}.csv").open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


overview = rows("overview")[0]
monthly = rows("monthly")
categories = rows("categories")
rfm = rows("rfm")
repeat = rows("repeat")
experiment = rows("experiment")
pdfmetrics.registerFont(TTFont("SimHei", r"C:\Windows\Fonts\simhei.ttf"))


def txt(c, x, y, value, size=15, color=NAVY, align="left"):
    c.setFillColor(color)
    c.setFont("SimHei", size)
    value = str(value).replace("¥", "人民币 ").replace("−", "-")
    if align == "right":
        c.drawRightString(x, y, value)
    elif align == "center":
        c.drawCentredString(x, y, value)
    else:
        c.drawString(x, y, value)


def rounded(c, x, y, w, h, color=WHITE, radius=16):
    c.setFillColor(color)
    c.roundRect(x, y, w, h, radius, stroke=0, fill=1)


def head(c, title, subtitle, number):
    c.setFillColor(PAPER)
    c.rect(0, 0, W, H, stroke=0, fill=1)
    c.setFillColor(NAVY)
    c.rect(0,H-9,W,9,stroke=0,fill=1)
    txt(c, 48, 660, title, 28)
    txt(c, 48, 628, subtitle, 12, GRAY)
    txt(c, 1232, 31, f"{number} / 2  ·  MySQL 8.0 汇总数据  ·  2026-03-05", 11, GRAY,"right")


def card(c, x, y, w, label, value, note=""):
    rounded(c,x,y,w,108)
    txt(c,x+18,y+77,label,13,GRAY)
    txt(c,x+18,y+36,value,26,NAVY)
    if note:
        txt(c,x+w-17,y+22,note,10,TEAL,"right")


def draw_overview(c):
    head(c,"经营概览","成交口径：已付款 / 已发货 / 已收货 / 已完成；GMV 使用实付金额",1)
    cards=[("成交 GMV",f"{float(overview['gmv'])/10000:,.1f} 万","全量有效订单"),
           ("成交订单",f"{int(overview['valid_orders']):,}","剔除 2,235 笔"),
           ("购买用户",f"{int(overview['buyers']):,}","有效下单用户"),
           ("客单价",f"{float(overview['aov']):,.0f} 元","均值")]
    for i,(label,value,note) in enumerate(cards):card(c,48+i*298,490,280,label,value,note)
    rounded(c,48,92,738,376)
    txt(c,70,434,"完整月日均 GMV",19)
    txt(c,70,410,"2025-10 至 2026-02｜单位：万元/天",11,GRAY)
    vals=[float(x['daily_gmv'])/10000 for x in monthly]
    base=182
    for i,(row,v) in enumerate(zip(monthly,vals)):
        x=105+i*132
        bh=205*v/24
        c.setFillColor(TEAL if i<4 else GOLD)
        c.roundRect(x,base,75,bh,7,stroke=0,fill=1)
        txt(c,x+37.5,base+bh+14,f"{v:.1f}",12,NAVY,"center")
        txt(c,x+37.5,base-28,row['month_key'],11,GRAY,"center")
    txt(c,70,112,"2 月整月环比 -13.57%；按 28/31 天归一后日均环比 -4.31%",13,TEAL)
    rounded(c,808,92,424,376)
    txt(c,830,434,"高 GMV 品类",19)
    txt(c,830,410,"前三类合计 60.9%",11,GRAY)
    for i,row in enumerate(categories[:5]):
        y=363-i*55
        txt(c,830,y,row['category'],12)
        c.setFillColor(MINT)
        c.roundRect(925,y-4,230,13,6,stroke=0,fill=1)
        c.setFillColor(TEAL)
        c.roundRect(925,y-4,230*float(row['gmv_share_pct'])/25,13,6,stroke=0,fill=1)
        txt(c,1208,y,f"{float(row['gmv_share_pct']):.1f}%",12,NAVY,"right")
    c.showPage()


def draw_user(c):
    head(c,"用户经营与实验设计","历史分群是观察结果；第二单券尚未实际随机实验",2)
    card(c,48,490,280,"30 天复购基线","34.91%","1,536 / 4,400")
    card(c,346,490,280,"一次性用户","1,006","21.8% 的购买用户")
    card(c,644,490,280,"复购用户 GMV 占比","91.8%","历史贡献")
    card(c,942,490,290,"+20% 目标样本","761 / 组","双侧 α=0.05")
    rounded(c,48,90,570,376)
    txt(c,70,433,"RFM 分群结构",19)
    txt(c,70,408,"人数占比 / GMV 占比",11,GRAY)
    for i,row in enumerate(rfm):
        y=365-i*68
        txt(c,70,y,row['segment'],13)
        c.setFillColor(MINT);c.roundRect(190,y-2,275,15,7,stroke=0,fill=1)
        c.setFillColor(TEAL);c.roundRect(190,y-2,275*float(row['gmv_share_pct'])/70,15,7,stroke=0,fill=1)
        txt(c,580,y,f"{float(row['buyer_share_pct']):.1f}% / {float(row['gmv_share_pct']):.1f}%",11,NAVY,"right")
    txt(c,70,117,"核心价值客户贡献 66.0% GMV；‘流失风险’是规则名称",11,TEAL)
    rounded(c,640,90,592,376)
    txt(c,662,433,"首单后不同观察窗复购",19)
    txt(c,662,408,"仅统计具有完整窗口的用户",11,GRAY)
    for i,row in enumerate(repeat):
        y=365-i*54
        txt(c,662,y,f"{row['window_days']} 天",12)
        c.setFillColor(MINT);c.roundRect(735,y-3,355,15,7,stroke=0,fill=1)
        c.setFillColor(GOLD if row['window_days']=="30" else TEAL)
        c.roundRect(735,y-3,355*float(row['repeat_rate_pct'])/80,15,7,stroke=0,fill=1)
        txt(c,1198,y,f"{float(row['repeat_rate_pct']):.2f}%",12,NAVY,"right")
    txt(c,662,113,"实验待开展：+20% 相对提升需 1,522 人；利润护栏无数据",11,TEAL)
    c.showPage()


def main():
    pdf=canvas.Canvas(str(OUT), pagesize=(W,H), pageCompression=1)
    pdf.setTitle("某电商平台经营与用户分析看板｜MySQL 汇总数据预览")
    draw_overview(pdf)
    draw_user(pdf)
    pdf.save()
    print(OUT)


if __name__=="__main__":
    main()
