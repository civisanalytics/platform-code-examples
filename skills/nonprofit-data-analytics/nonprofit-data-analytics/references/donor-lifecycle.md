# Donor Lifecycle Analysis — Reference Guide

## The Six Lifecycle Segments

Every donor can be classified into exactly one segment at any point in time. This is the foundation of file health analysis.

| Segment | Definition | Typical % of File | Role in Strategy |
|---|---|---|---|
| **New-to-File (NTF)** | First-ever gift was in the past 12 months | 8–15% | Acquisition; focus on 2nd gift conversion |
| **New Prior Year** | First gift was 12–24 months ago; gave again in L12M | 3–6% | Critical retention moment; treat with high-touch |
| **Core** | Gave in each of the past 2 consecutive 12-month periods (not NTF or NPY) | 18–30% | Most valuable and stable revenue base |
| **Reactivated** | Previously lapsed; gave again in L12M | 2–5% | Celebrate the return; prevent re-lapse |
| **Recently Lapsed** | Last gift was 13–24 months ago; no gift in L12M | 15–25% | Re-engagement priority; still winnable |
| **Long-Lapsed** | Last gift was 25+ months ago | 25–45% | Lower priority; targeted win-back or suppression |

**Healthy file signal:** NTF + New Prior Year + Core + Reactivated > 40% of total file
**Warning signal:** Long-Lapsed > 45% of total file (aging faster than acquiring)

---

## Retention Benchmarks by Segment

| Segment | Concerning | Average | Strong |
|---|---|---|---|
| New-to-File | < 12% | 15–20% | > 22% |
| New Prior Year | < 30% | 40–50% | > 55% |
| Core | < 60% | 68–75% | > 78% |
| Reactivated | < 25% | 35–45% | > 50% |

### Revenue Concentration

In most nonprofit files, Core donors account for 70–85% of total active revenue despite being 40–60% of the active file. This is the segment to protect above all others.

---

## 3-Period Comparison: What to Look For

**Positive signals:**
- NTF count growing YoY → healthy acquisition pipeline
- Recently Lapsed count decreasing → retention is working
- Core segment growing → strong multi-year retention
- Overall retention rate trending up 2+ points per year

**Warning signals:**
- Long-Lapsed growing faster than NTF → file is aging
- New Prior Year retention below 40% → failing to convert first-time donors
- Core segment shrinking → attrition outpacing retention
- NTF stable while Long-Lapsed grows → not acquiring enough to offset natural attrition

**Illustrative benchmark (directional reference only):**

| Period | Active Donors | Total Revenue | Retention Rate |
|---|---|---|---|
| 2yr Ago | 3,813 | $1,192,410 | 55.0% |
| 1yr Ago | 4,289 | $1,364,910 | 59.9% |
| Current | 4,824 | $1,583,240 | 64.1% |

---

## SQL Templates

### Classify All Donors into Lifecycle Segments

```sql
WITH gift_windows AS (
  SELECT
    donor_id,
    MAX(gift_date)  AS last_gift_date,
    MIN(gift_date)  AS first_gift_date,
    COUNT(CASE WHEN gift_date >= CURRENT_DATE - INTERVAL '12 months'
               THEN 1 END) AS gifts_l12m,
    COUNT(CASE WHEN gift_date BETWEEN CURRENT_DATE - INTERVAL '24 months'
                               AND   CURRENT_DATE - INTERVAL '13 months'
               THEN 1 END) AS gifts_prior12m
  FROM reporting.gifts
  WHERE gift_status = 'COMPLETED'
    AND gift_type NOT IN ('IN-KIND', 'BEQUEST')   -- direct response gifts only
  GROUP BY donor_id
),
segmented AS (
  SELECT
    donor_id,
    last_gift_date,
    first_gift_date,
    CASE
      WHEN first_gift_date >= CURRENT_DATE - INTERVAL '12 months'
        THEN 'New-to-File'
      WHEN first_gift_date BETWEEN CURRENT_DATE - INTERVAL '24 months'
                                AND CURRENT_DATE - INTERVAL '13 months'
           AND gifts_l12m > 0
        THEN 'New Prior Year'
      WHEN gifts_l12m > 0
           AND last_gift_date < CURRENT_DATE - INTERVAL '12 months'
           AND first_gift_date < CURRENT_DATE - INTERVAL '24 months'
        THEN 'Reactivated'
      WHEN gifts_l12m > 0 AND gifts_prior12m > 0
        THEN 'Core'
      WHEN last_gift_date BETWEEN CURRENT_DATE - INTERVAL '24 months'
                               AND CURRENT_DATE - INTERVAL '13 months'
        THEN 'Recently Lapsed'
      WHEN last_gift_date < CURRENT_DATE - INTERVAL '24 months'
        THEN 'Long-Lapsed'
      ELSE 'Unknown'
    END AS lifecycle_segment
  FROM gift_windows
)
SELECT
  lifecycle_segment,
  COUNT(DISTINCT donor_id) AS donor_count
FROM segmented
GROUP BY lifecycle_segment
ORDER BY
  CASE lifecycle_segment
    WHEN 'New-to-File'     THEN 1
    WHEN 'New Prior Year'  THEN 2
    WHEN 'Core'            THEN 3
    WHEN 'Reactivated'     THEN 4
    WHEN 'Recently Lapsed' THEN 5
    WHEN 'Long-Lapsed'     THEN 6
    ELSE 7
  END;
```

### Revenue by Lifecycle Segment

```sql
-- Same CTE as above; add revenue aggregation
WITH gift_windows AS (
  -- (same as above)
),
segmented AS (
  -- (same as above)
),
gifts_l12m AS (
  SELECT donor_id, SUM(gift_amount) AS revenue_l12m, COUNT(*) AS gift_count_l12m
  FROM reporting.gifts
  WHERE gift_status = 'COMPLETED'
    AND gift_date >= CURRENT_DATE - INTERVAL '12 months'
    AND gift_type NOT IN ('IN-KIND', 'BEQUEST')
  GROUP BY donor_id
)
SELECT
  s.lifecycle_segment,
  COUNT(DISTINCT s.donor_id)       AS donor_count,
  SUM(g.revenue_l12m)              AS total_revenue,
  ROUND(AVG(g.revenue_l12m), 2)    AS avg_revenue_per_donor,
  SUM(g.gift_count_l12m)           AS total_gifts
FROM segmented s
LEFT JOIN gifts_l12m g ON s.donor_id = g.donor_id
GROUP BY s.lifecycle_segment;
```

### Retention Rate (Overall)

```sql
WITH cohort AS (
  SELECT DISTINCT donor_id
  FROM reporting.gifts
  WHERE gift_status = 'COMPLETED'
    AND gift_date BETWEEN CURRENT_DATE - INTERVAL '24 months'
                      AND CURRENT_DATE - INTERVAL '13 months'
    AND gift_type NOT IN ('IN-KIND', 'BEQUEST')
),
returned AS (
  SELECT DISTINCT c.donor_id
  FROM cohort c
  JOIN reporting.gifts g ON c.donor_id = g.donor_id
  WHERE g.gift_status = 'COMPLETED'
    AND g.gift_date >= CURRENT_DATE - INTERVAL '12 months'
    AND g.gift_type NOT IN ('IN-KIND', 'BEQUEST')
)
SELECT
  COUNT(DISTINCT c.donor_id)                                              AS cohort_size,
  COUNT(DISTINCT r.donor_id)                                              AS returned_donors,
  ROUND(
    COUNT(DISTINCT r.donor_id) * 100.0 / NULLIF(COUNT(DISTINCT c.donor_id), 0), 1
  )                                                                        AS retention_rate_pct
FROM cohort c
LEFT JOIN returned r ON c.donor_id = r.donor_id;
```

---

## Strategic Actions by Segment

| Segment | Primary Action | Cadence | Key Message |
|---|---|---|---|
| New-to-File | Thank fast; ask for 2nd gift at 90–120 days | 3–4 touches in year 1 | "Welcome; here's your impact" |
| New Prior Year | Upgrade ask; deepen engagement | 4–6 touches | "You're becoming part of our community" |
| Core | Retain; test upgrades | 6–8 touches/yr | "Your sustained support makes X possible" |
| Reactivated | Recommit messaging; prevent re-lapse | 4–5 touches | "We missed you; welcome back" |
| Recently Lapsed | Win-back series (2–3 touches) | 1–2 efforts | "It's been a while; we need you" |
| Long-Lapsed | Selective reactivation; mail only best RFM cells | 1 effort/yr max | "A lot has changed; reconnect" |
