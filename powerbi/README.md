# Power BI dashboard

The `.pbix` file is built in Power BI Desktop (Windows) against the dbt models. This folder holds everything
needed to build it in about an hour: the theme, every DAX measure, and the page-by-page layout.

## 1. Connect

1. Run the pipeline so Postgres has data: `docker compose up --build pipeline` (or `make pipeline`).
2. Power BI Desktop → **Get data → PostgreSQL database** → server `localhost:5432`, database `ecommerce`.
3. Mode: **Import** (the data is small; Import is fastest and works offline).
4. Select these tables:
   - `marts`: `fct_orders`, `fct_order_items`, `dim_date`, `dim_customer`, `dim_product`, `dim_seller`
   - `kpi`: `kpi_monthly_sales`, `kpi_category_pareto`, `kpi_rfm_segments`, `kpi_cohort_retention`,
     `kpi_delivery_impact`, `kpi_seller_scorecard`
5. **View → Themes → Browse** → `powerbi/theme.json`.

## 2. Model (star schema)

| From (many) | To (one) | Key |
|---|---|---|
| `fct_order_items[date_key]` | `dim_date[date_key]` | date |
| `fct_order_items[product_id]` | `dim_product[product_id]` | product |
| `fct_order_items[seller_id]` | `dim_seller[seller_id]` | seller |
| `fct_order_items[customer_id]` | `dim_customer[customer_id]` | customer |
| `fct_orders[date_key]` | `dim_date[date_key]` | date |
| `fct_orders[customer_id]` | `dim_customer[customer_id]` | customer |

Both facts share the date and customer dimensions, so one slicer filters revenue (items) and
order-level measures (orders, reviews, lateness) together. Do not relate the two fact tables directly:
that creates an ambiguous filter path.

Mark `dim_date` as the date table on `date_day`. Hide all key columns from report view.
Create an empty `_Measures` table and paste the measures from [`measures.dax`](measures.dax).

## 3. Pages

**1. Executive overview**
- KPI cards: Revenue, Orders, Avg Order Value, Est Margin %, Avg Review Score, Late Delivery %, each with MoM %.
- Line chart: `kpi_monthly_sales` revenue with `revenue_3m_moving_avg` as a second line.
- Bar: revenue by state. Slicers: year, category, state.
- *(Milestone 3)* a card showing the latest AI summary from the `ai_insights` table.

**2. Products**
- Treemap: revenue by category.
- Pareto chart (combo): `kpi_category_pareto` revenue bars + `cumulative_share` line, with an 80% constant line.
- Table: `kpi_top_products` with conditional formatting on review score.
- Drill-through from a category to its product list.

**3. Customers**
- Donut + bar: customers and revenue by `kpi_rfm_segments[segment]`.
- Matrix heatmap: `kpi_cohort_retention`, rows `cohort_month`, columns `months_since_first`,
  values `retention_rate`, background colour scale.
- Filled map: customers by state (`dim_customer[state]`).

**4. Operations**
- Clustered bar: `kpi_delivery_impact` review_on_time vs review_late by state.
- Scatter: `avg_delivery_days` vs `review_late`, bubble size = revenue.
- Table: `kpi_seller_scorecard` filtered to `needs_attention = TRUE`.

## 4. Polish that interviewers notice

- **Bookmarks** to switch the overview between revenue and profit views.
- **Tooltips pages** on the trend chart showing top 3 categories for the hovered month.
- **Row-level security** demo: role `Region SP` with filter `dim_customer[state] = "SP"`.
- Field descriptions on every measure (they show in the field-list tooltip).
- Save screenshots of each page into `docs/screenshots/` and link them from the main README.

Save the report as `powerbi/ecommerce_insights.pbix` and commit it.
