# 电商用户消费分析｜MySQL 8.0 复现作品集

这是对一份既有电商分析报告的**可复算重建**。从 6 个 CSV 开始，在独立数据库 `ecommerce_portfolio_v2` 中完成导入、质量核对、经营分析、RFM、首单后复购和模拟 A/B 样本量测算。新版报告保留原报告的分析主线，并逐项解释复算差异。数据为合成数据，不代表真实平台业绩。

## 面试官快速查看

1. [优化后的分析报告 PDF](report/analysis_report.pdf)｜[可编辑 Markdown](report/analysis_report.md)
2. [Power BI 看板 PBIX 下载](dashboard/ecommerce_analysis.pbix)｜[看板静态预览 PDF](dashboard/dashboard_preview.pdf)｜[第 1 页](dashboard/preview-1.png)｜[第 2 页](dashboard/preview-2.png)
3. [核心 SQL](sql/03_analysis.sql)｜[复购与实验](sql/04_retention_experiment.sql)｜[质量检查](sql/02_quality.sql)

**核心结论：**15,000 笔原始订单中，成交订单 12,765 笔，实付 GMV ¥39,026,323.87；剔除率 14.9%。以完整 30×24 小时观察窗计算，首单后复购为 1,536/4,400 = 34.91%。2026 年 2 月整月 GMV 环比 −13.57%，按日历天数归一后日均环比 −4.31%。

## 数据来源与公开边界

本地复跑需把以下 **6 个原始文件**放在同一目录；原始文件不进入公开仓库。文件行数和 SHA-256 见 [source_manifest.json](source_manifest.json)。公开 `dashboard/data/` 只有 MySQL 生成的汇总表，未包含订单级记录、用户 ID、商品 ID、账户字段或评论文本。

| 文件 | 行数 | 主键/关联 | 字段含义 |
|---|---:|---|---|
| `users.csv` | 5,000 | `user_id` | 用户年龄、性别、地区、注册时间、会员等级、账户余额、信用分 |
| `products.csv` | 2,000 | `product_id` | 商品名称、品类、品牌、标价、源销售数 |
| `orders.csv` | 15,000 | `order_id`; `user_id`, `product_id` | 数量、下单时间、状态、支付方式、价格、总额、折扣、实付、配送/收货时间、评分与评论 |
| `user_behaviors.csv` | 30,000 | `behavior_id`; `user_id`, `product_id` | 浏览、点击、收藏、加购等行为及时间、时长 |
| `user_features.csv` | 5,000 | `user_id` | 来源提供的消费/行为派生特征；仅用于审计，不作为分析真值 |
| `product_features.csv` | 2,000 | `product_id` | 来源提供的商品派生特征；仅用于审计，不作为分析真值 |

逐字段名称、SQL 类型和可空性以 [建库脚本](sql/00_schema.sql) 为准。金额字段采用 `DECIMAL`，源特征表保留其原始数值形式。字段字典与源文件并非下载链接；要复跑需自行持有这六个 CSV。

## 分阶段复跑

要求：MySQL 8.0、Python 3.10+、MySQL 命令行客户端。无需 Power BI 账号。导入脚本按 UTF-8 读取 CSV，通过 MySQL 客户端批量写入；分析定义全部位于 SQL 文件中。密码由运行时交互输入，或通过本机 `MYSQL_PASSWORD` 环境变量提供，不应提交到版本控制。若 MySQL 客户端不在常见路径或 `PATH` 中，可设置 `MYSQL_BIN`。

```powershell
# 在仓库根目录执行。--fresh 仅重建 ecommerce_portfolio_v2，请先确认其中没有需保留的数据。
python scripts/import_csv.py --data-dir 'D:\实验\电商' --fresh
python scripts/export_aggregates.py --data-dir 'D:\实验\电商'
python scripts/verify_results.py --data-dir 'D:\实验\电商'
python scripts/build_report.py
python scripts/build_dashboard_preview.py
# 首次生成 Power BI 原生项目时运行；已提供生成好的 dashboard/powerbi_project/
python scripts/build_pbip.py
```

`build_report.py` 和 `build_dashboard_preview.py` 需要 `reportlab`；后者生成无需账号的静态预览。重新执行 SQL 视图而不重新导入时，运行 `python scripts/import_csv.py --analyze-only`。

面试官可直接下载并用 Power BI Desktop 打开 [单文件 PBIX](dashboard/ecommerce_analysis.pbix)，无需 Power BI 账号、CSV 路径或数据库凭据。若要修改看板结构，可打开 `dashboard/powerbi_project/EcommerceMySQL.pbip`；PBIP 项目文件夹须完整下载，首次打开后点“主页 → 刷新”填充本地模型。详见 [看板说明](dashboard/BUILD_POWER_BI.md)。

| 阶段 | 文件 | 产出 |
|---|---|---|
| 01 建库装载 | [00_schema.sql](sql/00_schema.sql), [import_csv.py](scripts/import_csv.py) | 六张原始表、行数核对 |
| 02 指标定义 | [01_views.sql](sql/01_views.sql) | 成交订单、用户消费等基础视图 |
| 03 质量门槛 | [02_quality.sql](sql/02_quality.sql) | 16 项行数、键、关联、金额和缺失检查 |
| 04 经营诊断 | [03_analysis.sql](sql/03_analysis.sql) | 总览、月度、品类、RFM |
| 05 复购与实验 | [04_retention_experiment.sql](sql/04_retention_experiment.sql) | 完整观察窗复购、模拟 A/B 样本量 |
| 06 看板汇总 | [05_dashboard.sql](sql/05_dashboard.sql), [export_aggregates.py](scripts/export_aggregates.py) | 7 张公开汇总表 |
| 07 交付核验 | [verify_results.py](scripts/verify_results.py) | 独立复算与公开字段检查 |

## 分析口径和已纠正的差异

- 成交订单排除“已取消、已退款、待付款”；GMV 取 `actual_payment`，**不**用数量×单价重算。
- 月度环比只比较 2025 年 10 月至 2026 年 2 月五个完整月，同时展示整月和日均 GMV。
- 首单按 `(order_date, order_id)` 定序；后续成交须落在完整的 `N×24` 小时观察窗内；不满观察窗的用户从该窗口分母排除。
- RFM 的并列值按 `user_id` 固定排序；A/B 为**模拟教学示例**，未真实发券，缺少成本数据时不报告利润结论。
- 原报告写“剔除 15.1%”，复算是 2,235/15,000 = **14.9%**；原报告的 30 天复购 1,569 人不能按明确首单口径复现，本项目为 **1,536 人**。详细差异见报告第 8 节。

## 项目局限

数据是合成数据，覆盖时间不足以判断季节性；订单金额字段与数量×单价几乎均不吻合；评价分大量缺失；源特征表存在失效字段。建议只把这里的策略作为待验证假设，并在真实业务中补充毛利、发券成本、曝光与触达、长期留存等数据。
