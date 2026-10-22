# Sustainer (Monthly Giving) Analytics — Reference Guide

## What Is a Sustainer?

A sustainer is a donor who has committed to an automatically recurring monthly gift.

In the database:
- `reporting.gifts.gift_type = 'RECURRING'`
- Each monthly charge is its own transaction row
- Successful charges: `gift_status = 'COMPLETED'`
- Failed charges: `gift_status = 'DECLINED'` (or check `is_failed = 1` if available as a flag)

Sustainers are the highest-lifetime-value segment in most nonprofit files. A $25/month sustainer giving for 3 years is worth $900 — equivalent to a one-time donor giving $900. Sustainer programs reward investment in both acquisition and retention equally.

---

## The Six Sustainer Acquisition Channels

These map to `channel` values in `reporting.gifts` and `reporting.campaigns`:

| Channel | Typical Acquisition Cost | Avg Monthly Gift | Notes |
|---|---|---|---|
| **DM** (Direct Mail) | Low–Medium | $15–$30 | Older demographic; lower volume but loyal |
| **EMAIL** | Very Low | $15–$25 | Easy to scale; higher early attrition |
| **ONLINE** | Low | $20–$35 | Fastest-growing; strong for younger donors |
| **Face-to-Face / Canvass** | High | $20–$30/mo | Highest volume; highest early attrition; watch months 2–4 |
| **PHONE** (Telemarketing) | Medium | $15–$25 | Upgrade path for existing one-time donors |
| **EVENT** | Low (mostly organic) | $25–$50 | Small volume; high loyalty; warm relationship at signup |

---

## The Sustainer Lifecycle

```
Acquisition → Onboarding (M1–M3) → Stabilization (M4–M12) → Loyal (M13+) → Lapse Risk → Cancelled
```

| Phase | Months | Key Metric | Action |
|---|---|---|---|
| Onboarding | 1–3 | Early attrition rate | Welcome series; set expectations |
| Stabilization | 4–12 | Monthly retention rate | Payment failure recovery; upgrade asks |
| Loyal | 13–24 | Annual upgrade rate | Upgrade ask at anniversary; stewardship |
| Long-term | 25+ | Lifetime value; bequest pipeline | Major gift cultivation |
| Lapse Risk | Any | Payment failure rate | Automated retry + personal outreach |
| Cancelled | — | Reactivation rate | Win-back within 90 days |

---

## Core Sustainer Metrics

### 1. Monthly Retention Rate
Percent of active sustainers who successfully process a payment in a given month.

- **Strong**: > 95%
- **Average**: 91–94%
- **Concerning**: < 90%

Monthly retention compounds heavily: 95%/month = ~54% retained at 12 months. 90%/month = ~28% retained. This is roughly 2× lifetime value difference.

### 2. 12-Month Retention Curve
Percent of sustainers acquired in a cohort who are still active X months later — one curve per channel per cohort year. This is the primary visualization for sustainer health.

**Benchmarks by channel at Month 12:**

| Channel | Concerning | Average | Strong |
|---|---|---|---|
| Online / Digital | < 25% | 30–40% | > 45% |
| Direct Mail | < 35% | 42–52% | > 55% |
| Email | < 22% | 28–38% | > 42% |
| Face-to-Face | < 20% | 25–35% | > 40% |
| Telemarketing | < 30% | 38–48% | > 52% |
| Events | < 40% | 50–62% | > 65% |

**Reading curve shapes:**
- **Steep drop months 1–3, then flattens**: Classic F2F/canvass pattern. Normal; watch early months closely.
- **Gradual consistent decline**: Healthy pattern; no single failure point.
- **Cliff at month 6 or 12**: Often a payment method expiry cluster or anniversary cancellations. Investigate.
- **Outlier cohort staying high**: A specific acquisition period or campaign produced unusually loyal donors. Study and replicate it.

### 3. Payment Failure Rate
Percent of monthly charges that fail (insufficient funds, expired card, etc.).

- **Target**: < 5% per month
- Most payment processors recover 40–60% of soft failures within 30 days with retry logic
- In the database: `gift_status = 'DECLINED'` or `is_failed = 1`

### 4. Average Monthly Gift (AMG)
`SUM(gift_amount) ÷ COUNT(DISTINCT donor_id)` for active sustainers in a given month.

### 5. Sustainer Lifetime Value (LTV)
```
LTV = AMG × (1 ÷ Monthly Attrition Rate)
```
Where Monthly Attrition Rate = 1 − Monthly Retention Rate.

Example: $25 AMG, 94% monthly retention → LTV = $25 × (1 ÷ 0.06) = $417

### 6. Upgrade Rate
Percent of active sustainers who increase their monthly gift in a 12-month period. Target: 5–15% annually. Best moment: month-12 anniversary ask.

### 7. Reactivation Rate (Cancelled Sustainers)
Percent of cancelled sustainers who restart within 90 days. Target: 10–20%. Declines sharply after 90 days — prioritize fast outreach post-cancellation.

---

## SQL Templates

### Active Sustainer Count and Revenue — Current Month

```sql
SELECT
  COUNT(DISTINCT donor_id)     AS active_sustainers,
  SUM(gift_amount)             AS monthly_recurring_revenue,
  ROUND(AVG(gift_amount), 2)   AS avg_monthly_gift
FROM reporting.gifts
WHERE gift_type   = 'RECURRING'
  AND gift_status = 'COMPLETED'
  AND DATE_TRUNC('month', gift_date) = DATE_TRUNC('month', CURRENT_DATE);
```

### Payment Failure Rate — Last 3 Months

```sql
SELECT
  DATE_TRUNC('month', gift_date)                             AS month,
  COUNT(*)                                                   AS total_attempts,
  SUM(CASE WHEN gift_status = 'DECLINED' THEN 1 ELSE 0 END) AS failed_payments,
  SUM(CASE WHEN gift_status = 'COMPLETED' THEN 1 ELSE 0 END) AS successful_payments,
  ROUND(
    SUM(CASE WHEN gift_status = 'DECLINED' THEN 1.0 ELSE 0 END)
    / NULLIF(COUNT(*), 0) * 100, 1
  )                                                          AS failure_rate_pct
FROM reporting.gifts
WHERE gift_type = 'RECURRING'
  AND gift_date >= CURRENT_DATE - INTERVAL '3 months'
GROUP BY 1
ORDER BY 1;
```

### 12-Month Retention Curve by Acquisition Channel

```sql
-- Acquisition channel is on reporting.donors; join to campaigns via acquisition_source_code
WITH first_gift AS (
  SELECT
    g.donor_id,
    c.channel                                AS acquisition_channel,
    MIN(g.gift_date)                         AS first_gift_date,
    DATE_TRUNC('month', MIN(g.gift_date))    AS cohort_month
  FROM reporting.gifts g
  JOIN reporting.donors d ON g.donor_id = d.donor_id
  JOIN reporting.campaigns c ON d.acquisition_source_code = c.source_code
  WHERE g.gift_type   = 'RECURRING'
    AND g.gift_status = 'COMPLETED'
  GROUP BY g.donor_id, c.channel
),
monthly_activity AS (
  SELECT
    fg.donor_id,
    fg.acquisition_channel,
    fg.cohort_month,
    DATEDIFF('month', fg.cohort_month,
             DATE_TRUNC('month', g.gift_date)) AS month_num
  FROM first_gift fg
  JOIN reporting.gifts g ON fg.donor_id = g.donor_id
  WHERE g.gift_type   = 'RECURRING'
    AND g.gift_status = 'COMPLETED'
    AND g.gift_date  >= fg.first_gift_date
)
SELECT
  acquisition_channel,
  month_num,
  COUNT(DISTINCT donor_id)   AS active_sustainers,
  ROUND(
    COUNT(DISTINCT donor_id) * 100.0 /
    NULLIF(
      MAX(COUNT(DISTINCT donor_id)) OVER (
        PARTITION BY acquisition_channel
        ORDER BY month_num
        ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
      ), 0
    ), 1
  )                          AS retention_pct
FROM monthly_activity
WHERE month_num BETWEEN 0 AND 12
GROUP BY acquisition_channel, month_num
ORDER BY acquisition_channel, month_num;
```

### Cohort Retention Curve by Acquisition Year

```sql
WITH first_gift AS (
  SELECT
    donor_id,
    MIN(gift_date)                       AS first_gift_date,
    DATE_TRUNC('year', MIN(gift_date))   AS cohort_year
  FROM reporting.gifts
  WHERE gift_type = 'RECURRING' AND gift_status = 'COMPLETED'
  GROUP BY donor_id
),
monthly_activity AS (
  SELECT
    fg.donor_id,
    fg.cohort_year,
    DATEDIFF('month', fg.first_gift_date, g.gift_date) AS month_num
  FROM first_gift fg
  JOIN reporting.gifts g ON fg.donor_id = g.donor_id
  WHERE g.gift_type   = 'RECURRING'
    AND g.gift_status = 'COMPLETED'
    AND g.gift_date  >= fg.first_gift_date
)
SELECT
  cohort_year,
  month_num,
  COUNT(DISTINCT donor_id)   AS active_sustainers
FROM monthly_activity
WHERE month_num BETWEEN 0 AND 12
GROUP BY cohort_year, month_num
ORDER BY cohort_year, month_num;
```

### Active Sustainer File Growth — Last 24 Months

```sql
SELECT
  DATE_TRUNC('month', gift_date)   AS month,
  COUNT(DISTINCT donor_id)         AS active_sustainers,
  SUM(gift_amount)                 AS monthly_recurring_revenue,
  ROUND(AVG(gift_amount), 2)       AS avg_monthly_gift
FROM reporting.gifts
WHERE gift_type   = 'RECURRING'
  AND gift_status = 'COMPLETED'
  AND gift_date  >= CURRENT_DATE - INTERVAL '24 months'
GROUP BY 1
ORDER BY 1;
```

### Upgrade Rate — Annual

```sql
WITH annual_avg AS (
  SELECT
    donor_id,
    DATE_TRUNC('year', gift_date)   AS gift_year,
    AVG(gift_amount)                AS avg_monthly_gift
  FROM reporting.gifts
  WHERE gift_type   = 'RECURRING'
    AND gift_status = 'COMPLETED'
  GROUP BY donor_id, DATE_TRUNC('year', gift_date)
),
yoy AS (
  SELECT
    a.donor_id,
    a.gift_year                          AS base_year,
    a.avg_monthly_gift                   AS base_amt,
    b.avg_monthly_gift                   AS next_amt
  FROM annual_avg a
  JOIN annual_avg b
    ON  a.donor_id  = b.donor_id
    AND b.gift_year = a.gift_year + INTERVAL '1 year'
)
SELECT
  base_year,
  COUNT(*)                                                       AS sustainers_in_both_years,
  SUM(CASE WHEN next_amt > base_amt THEN 1 ELSE 0 END)          AS upgraded,
  ROUND(
    SUM(CASE WHEN next_amt > base_amt THEN 1.0 ELSE 0 END)
    / NULLIF(COUNT(*), 0) * 100, 1
  )                                                              AS upgrade_rate_pct,
  ROUND(AVG(next_amt - base_amt), 2)                             AS avg_gift_change
FROM yoy
GROUP BY base_year
ORDER BY base_year;
```

---

## Strategic Guidance

### Priority Actions (in order of impact)

1. **Fix payment failures first.** A 1-point reduction in monthly failure rate compounds to ~12% more revenue annually. Implement automated retry logic and a pre-charge reminder email.

2. **Invest in months 1–3 onboarding.** The steepest drop on every retention curve is months 1–3. A strong welcome series (3–5 emails + 1 DM piece) can reduce early attrition by 15–30%.

3. **Anniversary upgrade asks at month 12.** Month 12 is the single best moment to ask for an upgrade. Frame it as: "You've been with us a year — can you increase your impact?"

4. **Reactivate within 90 days of cancellation.** Outreach within 2 weeks recovers 2–3× more sustainers than waiting 60+ days.

5. **Segment by channel for separate benchmarks.** A F2F cohort at 30% Month-12 retention may be fine; a DM cohort at 30% is alarming. Never apply a single benchmark across all channels.

### Reading Retention Curves

- **One cohort outlier staying high**: Identify what was different (campaign, ask, incentive, time of year). Replicate it.
- **All channels declining faster than benchmarks**: Check payment infrastructure first (retry logic, card updater service), then onboarding communications.
- **F2F dragging down the overall average**: Normal — but calculate net revenue per sustainer acquired (acquisition cost ÷ LTV) rather than gross. F2F is often still profitable despite high attrition.
