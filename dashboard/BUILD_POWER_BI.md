# Power BI Desktop 离线看板说明

数据源是 `dashboard/data/` 下的七张 MySQL 汇总 CSV。全部表均由 [05_dashboard.sql](../sql/05_dashboard.sql) 及 [export_aggregates.py](../scripts/export_aggregates.py) 产生。面试官可直接下载并用 Desktop 打开 [单文件 PBIX](ecommerce_analysis.pbix)。它包含四页报表及已加载的汇总数据，无需 Power BI 账号、CSV 路径或数据库凭据。项目仅包含汇总行，不含六张原始 CSV 或逐行用户资料。

可编辑的 [PBIP 源项目](powerbi_project/EcommerceMySQL.pbip)由 [build_pbip.py](../scripts/build_pbip.py)生成。脚本只读取七张汇总 CSV；输出目录若已存在会停止，避免覆盖手动编辑的看板。PBIP 需要完整文件夹，首次在 Desktop 打开后点“主页 → 刷新”加载数据；随后可用“文件 → 另存为 → 浏览此设备”，在 Windows 保存对话框的“保存类型”中选择“Power BI 文件 (*.pbix)”重新生成单文件。

## 表与建议视觉对象

| 表 | 粒度 | 建议视觉对象 |
|---|---|---|
| `overview.csv` | 全期 1 行 | 成交 GMV、订单数、购买人数、客单价 KPI 卡片 |
| `monthly.csv` | 完整月 1 行 | 整月 GMV 与日均 GMV 双趋势；2 月解释文本 |
| `categories.csv` | 品类 1 行 | 品类 GMV 排名与占比 |
| `rfm.csv` | 分群 1 行 | 人数、GMV 占比组合图 |
| `repeat.csv` | 观察窗 1 行 | 7/15/30/60/90 天复购率 |
| `experiment.csv` | 相对提升假设 1 行 | 每组样本量；明确标注模拟 |
| `quality.csv` | 检查项目 1 行 | 质量检查状态表 |

建议至少四页：经营概览、月度与品类、RFM 与复购、实验设计与数据质量。`monthly.csv` 中 `month_key` 应按年月文本升序；百分比字段是数值形式的百分点（例如 34.9091 表示 34.9091%），不要再次乘 100。全部货币字段使用人民币显示格式。页脚注明“合成数据、非实际投放”。

面试官无需 Power BI 账号即可查看 [静态预览 PDF](dashboard_preview.pdf)。原生项目在 Power Query 中直接内置汇总数据，因此离线打开后无需 CSV 路径或数据库密码。
