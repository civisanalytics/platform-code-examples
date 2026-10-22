# CRM Data Structure & Campaign Attribution — Reference Guide

## Overview

The fundraising CRM is organized around four primary relational tables that together capture the full lifecycle of a donor relationship — from first contact through every gift and every outreach effort.

| Table | Primary Key | One Row Per |
|---|---|---|
| `reporting.donors` | `donor_id` | Donor (master record) |
| `reporting.gifts` | `transaction_id` | Gift transaction |
| `reporting.promotion_history` | `promotion_id` | Donor × campaign contact |
| `reporting.campaigns` | `campaign_id` | Campaign / source code variant |

---

## The Source Code: Central Attribution Key

**The source code is the most important linking field in the schema.** It is an alphanumeric code (typically 8–20 characters) that identifies a specific campaign mailing or digital campaign variant — the unique combination of list, offer, and package for a given effort.

**How it flows:**
1. A campaign is produced; each unique mailing variant gets its own source code
2. The source code is printed on the reply envelope or embedded in a URL
3. When a donor responds with a gift, the source code is captured in `reporting.gifts.source_code`
4. That code is matched back to `reporting.campaigns.source_code` to attribute the gift to the campaign

This process is called **campaign match-back or response attribution**. Without it, you cannot calculate cost-per-dollar-raised or ROI at the campaign level.

**Source code hierarchy:** One campaign typically contains multiple source codes — one per unique combination of list, offer, and package. A spring appeal mailed to three lists with two ask string variants = six source codes under one `campaign_id`.

---

## Table: `reporting.donors` — Donor Master

One record per donor. The central hub; every other table links here via `donor_id`.

### Two Functions
1. **Static descriptive fields**: identity, contact info, demographics
2. **Calculated summary fields**: pre-aggregated giving history (recalculated nightly from `reporting.gifts`) — used for fast segmentation without querying millions of transaction rows

### Key Fields for Analytics

**Identity & Contact**
- `donor_id` — primary key; join key across all tables
- `donor_type` — `I` = Individual, `O` = Organization, `F` = Foundation
- `acquisition_date` — date of first gift or sign-up
- `acquisition_source_code` — which campaign originally acquired this donor

**Calculated Giving Summaries** *(pre-computed; fast for segmentation)*
- `first_gift_date` / `first_gift_amount`
- `last_gift_date` / `last_gift_amount`
- `largest_gift_amount`
- `total_gift_amount` — cumulative lifetime giving
- `total_number_of_gifts` — lifetime gift count
- `months_since_last_gift` — use for recency segmentation when speed matters

**Suppression Flags** *(must always be applied before any campaign)*
- `do_not_mail_flag` — exclude from all DM
- `do_not_email_flag` — exclude from all email
- `do_not_call_flag` — exclude from phone/telemarketing
- `deceased_flag` — exclude from all outreach

> **Important:** Calculated summary fields in this table are derived from `reporting.gifts`. For historical or point-in-time analysis, always aggregate from `reporting.gifts` directly rather than relying on summary fields, which reflect current state only.

---

## Table: `reporting.gifts` — Donation Gift

One record per gift transaction. The financial heart of the CRM.

### Key Fields for Analytics

| Column | Values / Notes |
|---|---|
| `transaction_id` | Primary key |
| `donor_id` | FK to `reporting.donors` |
| `gift_date` | Date received or processed |
| `gift_amount` | Dollar value |
| `channel` | `DM`, `EMAIL`, `ONLINE`, `PHONE`, `EVENT`, `MAJOR GIFT` |
| `source_code` | Attribution bridge to `reporting.campaigns` |
| `campaign_id` | FK to `reporting.campaigns` |
| `gift_type` | `OUTRIGHT`, `PLEDGE`, `PLEDGE PAYMENT`, `RECURRING`, `IN-KIND`, `BEQUEST` |
| `gift_status` | `COMPLETED`, `PENDING`, `REVERSED`, `DECLINED` |
| `payment_type` | `CHECK`, `CREDIT CARD`, `ACH`, `PAYPAL`, `STOCK`, `CRYPTO` |
| `designation_code` | Fund/program (e.g., `GENERAL`, `SCHOLARSHIP`, `CAPITAL`) |

### Critical Filters

```sql
-- Standard revenue query filter
WHERE gift_status = 'COMPLETED'   -- exclude reversals, declines, chargebacks

-- Sustainer query filter
WHERE gift_status = 'COMPLETED'
  AND gift_type   = 'RECURRING'

-- Exclude non-cash gifts when reporting on direct response revenue
WHERE gift_type NOT IN ('IN-KIND', 'BEQUEST')
```

### Gift Types Explained

- **OUTRIGHT** — Standard one-time gift; the most common type
- **PLEDGE** — A commitment to give; the pledge itself is not revenue until payments arrive
- **PLEDGE PAYMENT** — Installment against a pledge; this is the revenue record
- **RECURRING** — Monthly/annual sustainer gift; each charge is its own transaction row
- **IN-KIND** — Non-cash donation (goods, services); exclude from standard revenue reporting
- **BEQUEST** — Planned/estate gift; track separately for major gift reporting

### Reversals and Adjustments

Returned checks, credit card chargebacks, and data entry corrections appear as `gift_status = 'REVERSED'`. Always filter `gift_status = 'COMPLETED'` for revenue figures to avoid overstating income.

---

## Table: `reporting.promotion_history` — Outreach Contacts

One record per donor per campaign contact. The "sent" ledger.

### Key Fields for Analytics

| Column | Notes |
|---|---|
| `promotion_id` | Primary key |
| `donor_id` | FK to `reporting.donors` |
| `campaign_id` | FK to `reporting.campaigns` |
| `source_code` | Specific mailing variant |
| `promotion_date` | Date mailed or deployed |
| `channel` | `DM`, `EMAIL`, `PHONE`, `DIGITAL`, `EVENT` |
| `segment_code` | Segmentation code applied to this donor for this mailing |
| `ask_amount_1/2/3` | Suggested gift amounts in the ask string |
| `suppress_flag` | TRUE = selected but not mailed (retain in analysis for accurate universe counts) |
| `response_flag` | TRUE = donor gave in response to this promotion |
| `response_amount` | Dollar amount of matched-back response gift |

### Two Core Uses

**1. Suppression:** Ensures donors already mailed in a campaign aren't mailed again in the same effort. Never exclude suppressed records from universe counts — they were selected and considered.

**2. Response analysis:** Comparing promoted universe to responders to compute response rates and identify which donor segments perform best for a given campaign type.

### Ask String Personalization

The `ask_amount_1/2/3` fields record the actual dollar amounts suggested to each donor. Most programs personalize the ask string based on previous giving (e.g., last gift $35 → asks of $25 / $50 / $100). Recording the actual amounts enables analysis of whether ask string strategy influenced gift size.

---

## Table: `reporting.campaigns` — Campaign Results

One record per source code variant. The performance ledger.

### Key Fields for Analytics

| Column | Notes |
|---|---|
| `campaign_id` | Primary key |
| `source_code` | Attribution bridge to `reporting.gifts` |
| `campaign_name` | e.g., "2026 Spring Annual Fund" |
| `campaign_date` | Mail/launch date |
| `channel` | `DM`, `EMAIL`, `DIGITAL`, `PHONE`, `EVENT`, `INTEGRATED` |
| `program_type` | `ACQUISITION`, `RENEWAL`, `UPGRADE`, `LAPSED REACTIVATION`, `MAJOR GIFTS`, `SUSTAINER` |
| `list_type` | `HOUSE`, `ACQUISITION`, `LAPSED`, `SWAP`, `RENTAL` |
| `qty_sent` | Pieces mailed or contacts attempted |
| `num_responses` | Gifts attributed to this campaign |
| `total_gift_amount` | Sum of attributed gift dollars |
| `total_cost` | Production + fulfillment cost |
| `net_revenue` | `total_gift_amount − total_cost` |
| `response_rate` | `num_responses ÷ qty_sent` |
| `average_gift_amt` | `total_gift_amount ÷ num_responses` |
| `cost_per_dollar` | `total_cost ÷ total_gift_amount`; target < $0.25 for renewal |
| `return_on_investment` | `net_revenue ÷ total_cost` |

### Program Type Benchmarks

| Program Type | Expected Cost/$ | Interpretation |
|---|---|---|
| Acquisition | > $1.00 (runs at a loss) | Normal — evaluate on 3-year net value, not first-campaign ROI |
| Renewal | $0.15–$0.35 | Core profitability driver |
| Upgrade | $0.10–$0.25 | High ROI if targeted correctly |
| Lapsed Reactivation | $0.40–$0.80 | Higher cost than renewal; justified by win-back value |
| Sustainer | Varies | Measure on LTV, not campaign cost |

---

## SQL Templates

### Campaign ROI Summary

```sql
-- Overall performance by program type and channel for a given year
SELECT
  c.program_type,
  c.channel,
  COUNT(DISTINCT c.campaign_id)    AS campaigns,
  SUM(c.qty_sent)                  AS total_pieces,
  SUM(c.num_responses)             AS total_responses,
  ROUND(SUM(c.num_responses) * 100.0 / NULLIF(SUM(c.qty_sent), 0), 2)
                                   AS overall_response_rate_pct,
  SUM(c.total_gift_amount)         AS total_revenue,
  SUM(c.total_cost)                AS total_cost,
  SUM(c.net_revenue)               AS net_revenue,
  ROUND(SUM(c.total_cost) / NULLIF(SUM(c.total_gift_amount), 0), 4)
                                   AS cost_per_dollar,
  ROUND(AVG(c.average_gift_amt), 2) AS avg_gift
FROM reporting.campaigns c
WHERE c.campaign_date >= DATE_TRUNC('year', CURRENT_DATE)   -- YTD
GROUP BY c.program_type, c.channel
ORDER BY net_revenue DESC;
```

### Campaign Match-Back: Attribute Gifts to Campaigns

```sql
-- Links gifts back to their originating campaign via source code
SELECT
  c.campaign_id,
  c.campaign_name,
  c.program_type,
  c.channel,
  c.campaign_date,
  c.qty_sent,
  COUNT(g.transaction_id)          AS gifts_received,
  ROUND(COUNT(g.transaction_id) * 100.0 / NULLIF(c.qty_sent, 0), 2)
                                   AS response_rate_pct,
  SUM(g.gift_amount)               AS total_revenue,
  ROUND(AVG(g.gift_amount), 2)     AS avg_gift,
  c.total_cost,
  SUM(g.gift_amount) - c.total_cost AS net_revenue,
  ROUND(c.total_cost / NULLIF(SUM(g.gift_amount), 0), 4)
                                   AS cost_per_dollar
FROM reporting.campaigns c
LEFT JOIN reporting.gifts g
  ON c.source_code = g.source_code
  AND g.gift_status = 'COMPLETED'
  AND g.gift_date BETWEEN c.campaign_date AND c.campaign_date + INTERVAL '90 days'
GROUP BY c.campaign_id, c.campaign_name, c.program_type,
         c.channel, c.campaign_date, c.qty_sent, c.total_cost
ORDER BY c.campaign_date DESC;
```

### Suppression-Safe Campaign List Selection

```sql
-- Pull active donors for a direct mail renewal campaign
-- Applies all required suppression flags
SELECT
  d.donor_id,
  d.first_name,
  d.last_name,
  d.address_line_1,
  d.city,
  d.state,
  d.zip_code,
  d.last_gift_date,
  d.last_gift_amount,
  d.largest_gift_amount,
  d.months_since_last_gift
FROM reporting.donors d
WHERE d.do_not_mail_flag = FALSE
  AND d.deceased_flag    = FALSE
  AND d.last_gift_date  >= CURRENT_DATE - INTERVAL '24 months'  -- active or recently lapsed only
  AND d.donor_type      IN ('I', 'O')                           -- individuals and orgs; adjust as needed
ORDER BY d.months_since_last_gift ASC, d.last_gift_amount DESC;
```

### Promotion Response Analysis: Which Segments Responded Best?

```sql
-- For a given campaign, compare response rates by segment code
SELECT
  ph.segment_code,
  COUNT(DISTINCT ph.donor_id)          AS promoted,
  SUM(CASE WHEN ph.suppress_flag = TRUE THEN 1 ELSE 0 END)
                                        AS suppressed,
  COUNT(DISTINCT ph.donor_id)
    - SUM(CASE WHEN ph.suppress_flag = TRUE THEN 1 ELSE 0 END)
                                        AS mailed,
  SUM(CASE WHEN ph.response_flag = TRUE THEN 1 ELSE 0 END)
                                        AS responses,
  ROUND(
    SUM(CASE WHEN ph.response_flag = TRUE THEN 1.0 ELSE 0 END)
    / NULLIF(
        COUNT(DISTINCT ph.donor_id)
        - SUM(CASE WHEN ph.suppress_flag = TRUE THEN 1 ELSE 0 END),
        0
      ) * 100, 2
  )                                     AS response_rate_pct,
  ROUND(AVG(CASE WHEN ph.response_flag = TRUE THEN ph.response_amount END), 2)
                                        AS avg_response_amount
FROM reporting.promotion_history ph
WHERE ph.campaign_id = :campaign_id    -- substitute target campaign ID
GROUP BY ph.segment_code
ORDER BY response_rate_pct DESC;
```

### Ask String Effectiveness

```sql
-- Did donors give above, at, or below the first ask amount?
SELECT
  ph.campaign_id,
  ph.ask_amount_1,
  COUNT(g.transaction_id)              AS responses,
  ROUND(AVG(g.gift_amount), 2)         AS avg_gift,
  SUM(CASE WHEN g.gift_amount > ph.ask_amount_1 THEN 1 ELSE 0 END)
                                        AS gave_above_ask,
  SUM(CASE WHEN g.gift_amount = ph.ask_amount_1 THEN 1 ELSE 0 END)
                                        AS gave_at_ask,
  SUM(CASE WHEN g.gift_amount < ph.ask_amount_1 THEN 1 ELSE 0 END)
                                        AS gave_below_ask
FROM reporting.promotion_history ph
JOIN reporting.gifts g
  ON ph.donor_id = g.donor_id
  AND ph.source_code = g.source_code
  AND g.gift_status = 'COMPLETED'
WHERE ph.response_flag = TRUE
  AND ph.campaign_id = :campaign_id
GROUP BY ph.campaign_id, ph.ask_amount_1
ORDER BY ph.ask_amount_1;
```

### Acquisition Channel Long-Term Value

```sql
-- Compare 3-year net revenue per donor by acquisition source
WITH acquired AS (
  SELECT
    d.donor_id,
    d.acquisition_date,
    c.channel AS acquisition_channel,
    c.program_type
  FROM reporting.donors d
  JOIN reporting.campaigns c ON d.acquisition_source_code = c.source_code
  WHERE d.acquisition_date BETWEEN CURRENT_DATE - INTERVAL '3 years'
                                AND CURRENT_DATE - INTERVAL '2 years'
    AND c.program_type = 'ACQUISITION'
),
lifetime_giving AS (
  SELECT
    g.donor_id,
    SUM(g.gift_amount) AS total_3yr_giving
  FROM reporting.gifts g
  WHERE g.gift_status = 'COMPLETED'
    AND g.gift_date >= CURRENT_DATE - INTERVAL '3 years'
  GROUP BY g.donor_id
)
SELECT
  a.acquisition_channel,
  COUNT(DISTINCT a.donor_id)                AS donors_acquired,
  ROUND(AVG(lg.total_3yr_giving), 2)        AS avg_3yr_giving,
  ROUND(SUM(lg.total_3yr_giving), 0)        AS total_3yr_revenue,
  SUM(CASE WHEN lg.total_3yr_giving > 0
           THEN 1 ELSE 0 END) * 100.0
  / NULLIF(COUNT(DISTINCT a.donor_id), 0)   AS pct_became_donors
FROM acquired a
LEFT JOIN lifetime_giving lg ON a.donor_id = lg.donor_id
GROUP BY a.acquisition_channel
ORDER BY avg_3yr_giving DESC;
```

---

## Glossary of Key Terms

| Term | Definition |
|---|---|
| **Ask String** | The set of suggested gift amounts in a fundraising appeal (e.g., $25 / $50 / $100 / Other). Typically personalized based on previous giving via `ask_amount_1/2/3` in the promotion history table. |
| **Batch ID** | Grouping identifier for gift transactions entered in a single data entry session; used for balancing and audit. |
| **Campaign Match-Back** | Matching incoming gifts to the campaign that prompted them via source code captured from the reply device. |
| **Churn / Attrition** | Rate at which donors stop giving year-to-year. The inverse of retention rate. |
| **Designation** | Fund or program a donor directs their gift to (e.g., General Fund, Capital Campaign). Stored in `designation_code`. |
| **House File** | The org's existing database of current and lapsed donors, as distinct from external prospecting lists. Corresponds to `list_type = 'HOUSE'` in campaigns. |
| **Lapsed Donor** | Donor who has not given within a defined period (commonly 13–24 months = Recently Lapsed; 25+ months = Long-Lapsed). |
| **Package Type** | Physical or digital format of an appeal: standard package, self-mailer, postcard, e-blast, landing page. |
| **RFM Segmentation** | Recency × Frequency × Monetary model for prioritizing outreach. See `references/rfm-segmentation.md`. |
| **Source Code** | Alphanumeric code assigned to each unique campaign variant (list × offer × package). The central attribution key of the CRM. |
| **Suppression List** | Records excluded from a campaign mailing (Do Not Mail, Deceased, Opt-Out). Suppressed records appear in promotion history with `suppress_flag = TRUE`. |
| **Swap** | List exchange between two nonprofits for prospecting; no cash transaction. Corresponds to `list_type = 'SWAP'`. |
