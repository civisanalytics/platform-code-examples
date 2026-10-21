# RFM Segmentation Matrix — Reference Guide

## What Is RFM?

RFM stands for **Recency, Frequency, Monetary** — the three dimensions most predictive of future donor behavior. Every donor can be placed in a cell of the matrix at any moment in time. The matrix drives:

- **Campaign selection**: Include or exclude each cell based on expected ROI
- **Revenue forecasting**: Estimate campaign yield before you mail
- **Ask string strategy**: What amounts should you suggest to a donor in this cell?
- **Segment-specific messaging**: Tailor appeal content by RFM profile

RFM is stored in two places in the CRM:
- **Pre-computed** on `reporting.donors` (`donor_segment_code`, `months_since_last_gift`, etc.) — fast for list pulls
- **Real-time** by aggregating `reporting.gifts` — accurate for point-in-time analysis

---

## The Three Dimensions

### Recency — How Recently Did They Give?

The single most predictive variable.

| Recency Band | Definition | Typical Response Rate Index |
|---|---|---|
| 0–6 Months | Gave within past 6 months | 100 (index) |
| 7–12 Months | Gave 7–12 months ago | 75–85 |
| 13–18 Months | Gave 13–18 months ago | 55–65 |
| 19–24 Months | Gave 19–24 months ago | 40–50 |
| 25–36 Months | Gave 25–36 months ago | 25–35 |
| 37–48 Months | Gave 37–48 months ago | 15–22 |
| 49+ Months | Gave 49+ months ago | 5–12 |

Response rate roughly halves with each additional year of lapse.

### Frequency — How Many Times in 18 Months?

| Band | Definition | Why It Matters |
|---|---|---|
| 1 Gift | Single gift in 18-month window | Higher lapse risk; target for upgrade |
| 2+ Gifts | Two or more gifts in 18 months | Multi-gift donors retain at ~2× the rate |

### Monetary — Largest Gift in 18 Months?

| Band | Range | 18-mo $/Name Benchmark | Ask Strategy |
|---|---|---|---|
| M1 | $0–$14.99 | ~$8 | Low-dollar sustainer conversion or suppress |
| M2 | $15–$24.99 | ~$20 | Upgrade to $25–$35 |
| M3 | $25–$49.99 | ~$36 | Upgrade to $50; "round up" ask |
| M4 | $50–$99.99 | ~$72 | Upgrade to $100; celebrate milestone |
| M5 | $100–$249.99 | ~$168 | Mid-level cultivation; upgrade to $250 |
| M6 | $250–$999.99 | ~$520 | Major gift pipeline; personal outreach |
| M7 | $1,000+ | ~$2,200 | Individual major gift strategy — bypass RFM |

---

## The 98-Cell Matrix and Campaign Tiers

The full matrix has **98 cells**: 7 Recency × 2 Frequency × 7 Monetary.

| Tier | Profile | Action |
|---|---|---|
| **Tier 1 — Always Mail** | Recency 0–12 mo + 2+ gifts + $50+ | Highest response, highest avg gift. Suppress only for explicit opt-out. |
| **Tier 2 — Mail with Standard Ask** | Recency 0–18 mo + 1 gift + $25+ OR Recency 13–24 mo + 2+ gifts + $50+ | Good ROI; focus on upgrade messaging. |
| **Tier 3 — Mail Selectively** | Recency 19–36 mo + any + $25+ OR Recency 0–18 mo + $0–$24.99 | Lower response; test ROI before mailing all. |
| **Tier 4 — Suppress / Win-Back Only** | Recency 37+ mo OR any + $0–$14.99 | Cost rarely justifies standard mailing. |

---

## Revenue Forecasting

Estimate campaign revenue before mailing using 18-mo $/Name:

```
Estimated Revenue = Count × (18-mo $/Name × Campaign Revenue Factor)
```

Where **Campaign Revenue Factor** ≈ 0.10–0.20 for a typical appeal. Calibrate using historical campaign data from `reporting.campaigns`.

---

## SQL Templates

### Assign RFM Segments to All Donors

```sql
WITH gift_summary AS (
  SELECT
    donor_id,
    -- Recency: months since last completed gift
    DATEDIFF('month', MAX(gift_date), CURRENT_DATE)  AS months_since_last_gift,

    -- Frequency: gift count in last 18 months
    COUNT(CASE WHEN gift_date >= CURRENT_DATE - INTERVAL '18 months'
               THEN 1 END)                           AS gifts_l18m,

    -- Monetary: largest single gift in last 18 months
    MAX(CASE WHEN gift_date >= CURRENT_DATE - INTERVAL '18 months'
             THEN gift_amount ELSE 0 END)            AS max_gift_l18m,

    -- Context: total revenue in 18 months
    SUM(CASE WHEN gift_date >= CURRENT_DATE - INTERVAL '18 months'
             THEN gift_amount ELSE 0 END)            AS total_rev_l18m
  FROM reporting.gifts
  WHERE gift_status = 'COMPLETED'
    AND gift_type NOT IN ('IN-KIND', 'BEQUEST')
  GROUP BY donor_id
)
SELECT
  donor_id,
  months_since_last_gift,
  gifts_l18m,
  max_gift_l18m,
  total_rev_l18m,

  CASE
    WHEN months_since_last_gift <=  6 THEN 'R1: 0–6 Months'
    WHEN months_since_last_gift <= 12 THEN 'R2: 7–12 Months'
    WHEN months_since_last_gift <= 18 THEN 'R3: 13–18 Months'
    WHEN months_since_last_gift <= 24 THEN 'R4: 19–24 Months'
    WHEN months_since_last_gift <= 36 THEN 'R5: 25–36 Months'
    WHEN months_since_last_gift <= 48 THEN 'R6: 37–48 Months'
    ELSE                                   'R7: 49+ Months'
  END AS recency_band,

  CASE
    WHEN gifts_l18m >= 2 THEN 'F2: 2+ Gifts'
    WHEN gifts_l18m =  1 THEN 'F1: 1 Gift'
    ELSE                      'F0: No Recent Gift'
  END AS frequency_band,

  CASE
    WHEN max_gift_l18m < 15   THEN 'M1: $0–$14.99'
    WHEN max_gift_l18m < 25   THEN 'M2: $15–$24.99'
    WHEN max_gift_l18m < 50   THEN 'M3: $25–$49.99'
    WHEN max_gift_l18m < 100  THEN 'M4: $50–$99.99'
    WHEN max_gift_l18m < 250  THEN 'M5: $100–$249.99'
    WHEN max_gift_l18m < 1000 THEN 'M6: $250–$999.99'
    ELSE                           'M7: $1,000+'
  END AS monetary_band

FROM gift_summary
ORDER BY months_since_last_gift, gifts_l18m DESC, max_gift_l18m DESC;
```

### RFM Matrix Summary for Campaign Planning

```sql
WITH rfm AS (
  -- (paste full RFM assignment query above, or reference as a saved view)
  SELECT ...
)
SELECT
  recency_band,
  frequency_band,
  monetary_band,
  COUNT(*)                             AS record_count,
  ROUND(AVG(total_rev_l18m), 2)        AS avg_18mo_rev_per_name,
  ROUND(SUM(total_rev_l18m), 0)        AS total_18mo_rev
FROM rfm
GROUP BY recency_band, frequency_band, monetary_band
ORDER BY recency_band, frequency_band, monetary_band;
```

### Campaign Selection List with Suppression Applied

```sql
WITH rfm AS (
  -- (RFM assignment CTE)
  SELECT ...
)
SELECT
  d.donor_id,
  d.first_name,
  d.last_name,
  d.address_line_1,
  d.city,
  d.state,
  d.zip_code,
  r.recency_band,
  r.frequency_band,
  r.monetary_band,
  r.total_rev_l18m,
  CASE
    WHEN r.months_since_last_gift <= 24
         AND r.max_gift_l18m >= 25         THEN 'Include'
    WHEN r.months_since_last_gift <= 36
         AND r.gifts_l18m >= 2
         AND r.max_gift_l18m >= 50         THEN 'Include'
    WHEN r.months_since_last_gift > 48     THEN 'Exclude'
    WHEN r.max_gift_l18m < 15             THEN 'Exclude'
    ELSE                                       'Review'
  END AS campaign_selection
FROM rfm r
JOIN reporting.donors d ON r.donor_id = d.donor_id
WHERE d.do_not_mail_flag = FALSE   -- apply suppression
  AND d.deceased_flag    = FALSE
ORDER BY campaign_selection, r.total_rev_l18m DESC;
```

---

## Common RFM Questions

**Q: Should I use the `months_since_last_gift` summary field on donors or calculate from gifts?**
A: Use the summary field on `reporting.donors` for fast list pulls. Use `reporting.gifts` directly when you need point-in-time accuracy (e.g., "what was the RFM profile of donors as of 6 months ago").

**Q: Should monthly sustainers be in the same RFM matrix?**
A: No. Their recency is always fresh, frequency always high — they'll dominate the top tiers and distort analysis. Segment sustainers separately using `gift_type = 'RECURRING'` and analyze them with the sustainer framework.

**Q: M7 ($1,000+) is a tiny segment — do I use RFM for them?**
A: No. Major donors should have individualized strategy and personal outreach. Use RFM to identify them, then hand them to a major gift officer.

**Q: How do I set the include/exclude threshold?**
A: Work backward from your cost per piece (CPP). If CPP = $1.50 and average gift = $30, you need 5% response rate to break even. Use historical response rates from `reporting.campaigns` by recency band to test whether each cell clears your breakeven.
