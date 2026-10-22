# Channel Fundraising Analysis — Reference Guide

## The Six Core Fundraising Channels

These match the `channel` values in `reporting.gifts` and `reporting.campaigns`:

| Channel (DB value) | Typical Role | Strengths | Weaknesses |
|---|---|---|---|
| **DM** (Direct Mail) | Retention + major gift cultivation | High average gift; tangible; strong for older donors | High cost; long lead times; declining volume |
| **EMAIL** | Retention + acquisition + emergency appeals | Low cost; fast; scalable; easy to test | Lower average gift; unsubscribe risk; inbox competition |
| **ONLINE** | Acquisition + emergency response | Growing; 24/7; lower barrier to give | Retention weak without follow-up |
| **PHONE** (Telemarketing) | Retention upgrades + lapsed reactivation | Personal; real-time conversation; good for mid-level | Declining response; regulatory pressure; costly |
| **EVENT** | Cultivation + major gift pipeline | Relationship-building; higher average gift | Seasonal; resource-intensive |
| **Face-to-Face / Canvass** | Acquisition of recurring/sustainer donors | High volume NTF; excellent for sustainer programs | Highest attrition; expensive per-donor |

> Note: Face-to-Face may appear as `F2F`, `CANVASS`, or `FACE TO FACE` depending on CRM configuration — confirm the actual value with the user.

---

## Key Metrics Per Channel

Track these monthly or quarterly per channel:

| Metric | Formula | Notes |
|---|---|---|
| **Donors** | `COUNT(DISTINCT donor_id)` | Unique donors giving via this channel |
| **Gifts** | `COUNT(transaction_id)` | Total transactions; can exceed donors if multi-gift |
| **Revenue** | `SUM(gift_amount)` | Always filter `gift_status = 'COMPLETED'` |
| **Average Gift** | Revenue ÷ Gifts | Varies significantly by channel |
| **Cost per Dollar Raised** | `total_cost ÷ total_gift_amount` from `reporting.campaigns` | Efficiency; compare across channels over time |
| **Retention by Acquisition Channel** | % who gave again next year, grouped by channel of first gift | Quality of donors a channel is producing |

### Typical Average Gift Ranges by Channel

| Channel | Low | Typical | High |
|---|---|---|---|
| Direct Mail | $45 | $75–120 | $300+ |
| Email | $30 | $45–75 | $150 |
| Online | $40 | $55–85 | $500+ |
| Face-to-Face | $20 | $25–40/mo (sustainer) | $80 |
| Telemarketing | $50 | $65–90 | $200 |
| Events | $100 | $150–300 | $5,000+ |

---

## Trend Analysis: What to Look For

**Healthy portfolio signals:**
- Revenue growing in at least 3 of 6 channels YoY
- Online/Email trending up (digital maturity)
- No single channel > 60% of total revenue
- Seasonal peaks align with expectations (year-end = Nov/Dec spike; spring = Q2 bump)

**Warning signals:**
- DM declining > 10% YoY without online offsetting it
- Email donors declining despite list growth (engagement problem, not list problem)
- Events revenue volatile (over-reliance on single events)
- One channel growing while all others shrink (concentration risk)

---

## Seasonal Patterns by Channel

| Channel | Peak Months | Low Months |
|---|---|---|
| Direct Mail | Nov, Dec, Mar | Jun–Aug |
| Email | Nov, Dec, Jun | Jan, Feb |
| Online | Nov, Dec | Jan, Feb |
| Face-to-Face | Mar–Sep | Nov–Feb |
| Telemarketing | Jan–Mar, Sep | Jun–Aug |
| Events | Apr–Jun, Sep–Oct | Dec, Jan |

---

## SQL Templates

### Revenue, Donors, and Gifts by Channel — Monthly

```sql
SELECT
  DATE_TRUNC('month', g.gift_date) AS month,
  g.channel,
  COUNT(DISTINCT g.donor_id)       AS unique_donors,
  COUNT(g.transaction_id)          AS gift_count,
  SUM(g.gift_amount)               AS total_revenue,
  ROUND(SUM(g.gift_amount) / NULLIF(COUNT(g.transaction_id), 0), 2) AS avg_gift
FROM reporting.gifts g
WHERE g.gift_status = 'COMPLETED'
  AND g.gift_type NOT IN ('IN-KIND', 'BEQUEST')
  AND g.gift_date >= CURRENT_DATE - INTERVAL '36 months'
GROUP BY 1, 2
ORDER BY 1, 2;
```

### Channel Share of Revenue — Year-to-Date

```sql
SELECT
  channel,
  COUNT(DISTINCT donor_id) AS unique_donors,
  SUM(gift_amount)         AS total_revenue,
  ROUND(
    SUM(gift_amount) * 100.0 / SUM(SUM(gift_amount)) OVER (), 1
  )                        AS revenue_share_pct,
  ROUND(SUM(gift_amount) / NULLIF(COUNT(transaction_id), 0), 2) AS avg_gift
FROM reporting.gifts
WHERE gift_status = 'COMPLETED'
  AND gift_type NOT IN ('IN-KIND', 'BEQUEST')
  AND gift_date >= DATE_TRUNC('year', CURRENT_DATE)
GROUP BY channel
ORDER BY total_revenue DESC;
```

### YoY Channel Comparison

```sql
WITH current_year AS (
  SELECT
    channel,
    COUNT(DISTINCT donor_id) AS donors_cy,
    SUM(gift_amount)         AS revenue_cy
  FROM reporting.gifts
  WHERE gift_status = 'COMPLETED'
    AND gift_type NOT IN ('IN-KIND', 'BEQUEST')
    AND gift_date BETWEEN CURRENT_DATE - INTERVAL '12 months' AND CURRENT_DATE
  GROUP BY channel
),
prior_year AS (
  SELECT
    channel,
    COUNT(DISTINCT donor_id) AS donors_py,
    SUM(gift_amount)         AS revenue_py
  FROM reporting.gifts
  WHERE gift_status = 'COMPLETED'
    AND gift_type NOT IN ('IN-KIND', 'BEQUEST')
    AND gift_date BETWEEN CURRENT_DATE - INTERVAL '24 months'
                      AND CURRENT_DATE - INTERVAL '13 months'
  GROUP BY channel
)
SELECT
  COALESCE(cy.channel, py.channel)                                 AS channel,
  py.donors_py,
  cy.donors_cy,
  ROUND((cy.donors_cy - py.donors_py) * 100.0
        / NULLIF(py.donors_py, 0), 1)                              AS donor_chg_pct,
  py.revenue_py,
  cy.revenue_cy,
  ROUND((cy.revenue_cy - py.revenue_py) * 100.0
        / NULLIF(py.revenue_py, 0), 1)                             AS revenue_chg_pct
FROM prior_year py
FULL OUTER JOIN current_year cy USING (channel)
ORDER BY COALESCE(cy.revenue_cy, 0) DESC;
```

### Donor Retention Rate by Acquisition Channel

```sql
-- Which channels produce the most loyal donors?
-- Uses acquisition_source_code on donors table joined to campaigns for channel
WITH acquired AS (
  SELECT
    d.donor_id,
    c.channel AS acquisition_channel
  FROM reporting.donors d
  JOIN reporting.campaigns c ON d.acquisition_source_code = c.source_code
  WHERE d.acquisition_date BETWEEN CURRENT_DATE - INTERVAL '24 months'
                                AND CURRENT_DATE - INTERVAL '13 months'
),
retained AS (
  SELECT DISTINCT donor_id
  FROM reporting.gifts
  WHERE gift_status = 'COMPLETED'
    AND gift_date >= CURRENT_DATE - INTERVAL '12 months'
    AND gift_type NOT IN ('IN-KIND', 'BEQUEST')
)
SELECT
  a.acquisition_channel,
  COUNT(DISTINCT a.donor_id)                                       AS acquired_donors,
  COUNT(DISTINCT r.donor_id)                                       AS retained_donors,
  ROUND(COUNT(DISTINCT r.donor_id) * 100.0
        / NULLIF(COUNT(DISTINCT a.donor_id), 0), 1)                AS retention_rate_pct
FROM acquired a
LEFT JOIN retained r ON a.donor_id = r.donor_id
GROUP BY a.acquisition_channel
ORDER BY retention_rate_pct DESC;
```

### Campaign Cost Efficiency by Channel (from Campaign Results)

```sql
-- Uses reporting.campaigns directly — already has pre-aggregated cost and revenue
SELECT
  channel,
  program_type,
  COUNT(DISTINCT campaign_id)                                       AS campaigns,
  SUM(qty_sent)                                                     AS total_pieces,
  SUM(total_gift_amount)                                            AS total_revenue,
  SUM(total_cost)                                                   AS total_cost,
  SUM(net_revenue)                                                  AS net_revenue,
  ROUND(SUM(total_cost) / NULLIF(SUM(total_gift_amount), 0), 4)    AS cost_per_dollar,
  ROUND(AVG(average_gift_amt), 2)                                   AS avg_gift
FROM reporting.campaigns
WHERE campaign_date >= CURRENT_DATE - INTERVAL '12 months'
GROUP BY channel, program_type
ORDER BY channel, cost_per_dollar;
```

---

## Strategic Guidance by Channel Scenario

**If DM is > 50% of revenue:**
Protect it while building email/online. Launch a digital upgrade program to move DM donors to online giving and lower cost-to-raise.

**If Email donors are flat but list is growing:**
Engagement problem, not a list problem. Audit subject lines, from-name, send frequency, and list hygiene. Segment sends by lifecycle segment.

**If Online is growing fast (> 20% YoY):**
Invest in post-gift donor experience (landing pages, thank-you automation, welcome series). Online donors often have weak retention without strong follow-up.

**If Events > 20% of revenue:**
Map event donors to lifecycle segments. Most event donors are one-and-done unless cultivated into the mail/email stream. Build a post-event conversion series.

**If Telemarketing is declining:**
Shift budget toward a mid-level program or personal outreach. Phone still works for high-value retention ($500+ donors) even as mass telemarketing declines.
