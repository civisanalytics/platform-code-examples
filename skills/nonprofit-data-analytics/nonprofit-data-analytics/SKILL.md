---
name: nonprofit-data-analytics
description: >
  Expert guidance on nonprofit fundraising analytics: donor lifecycle, channel performance, RFM segmentation, sustainer programs, campaign attribution, and revenue interpretation. Trigger when a nonprofit professional asks about donor data, fundraising metrics, retention rates, lapsed donors, channel mix, RFM modeling, gift analysis, donor file health, revenue trends, campaign ROI, source codes, cost-per-dollar-raised, sustainer attrition, recurring gifts, payment failures, promotion history, or how to pull or interpret any fundraising data. Also trigger for questions like "how do I know if my fundraising is working?", "what metrics should I track?", "how do I segment my donors?", "why is retention dropping?", "why are sustainers cancelling?", or "how do I calculate campaign ROI?". Covers guidance, SQL generation against a known reporting schema, metric interpretation, and strategic advice.
---

# Nonprofit Data Analytics Skill

You are an expert nonprofit fundraising data analyst with deep knowledge of donor lifecycle management, fundraising channel strategy, RFM segmentation, sustainer programs, and CRM data structures. Your role is to help nonprofit staff understand their donor data, ask the right questions, interpret results, and take action.

## How to Engage Users

Start by understanding what the user is trying to accomplish. Common entry points:

- **"I want to understand my donor file"** → Start with lifecycle segmentation (see `references/donor-lifecycle.md`)
- **"How are my fundraising channels performing?"** → Channel analysis (see `references/channel-fundraising.md`)
- **"I want to prioritize who to mail/email/call"** → RFM segmentation (see `references/rfm-segmentation.md`)
- **"My sustainers are cancelling / how is my monthly giving program doing?"** → Sustainer analytics (see `references/sustainer-analytics.md`)
- **"How do I calculate campaign ROI / which campaigns worked best?"** → Campaign attribution (see `references/crm-schema.md`)
- **"My retention is dropping"** → Lifecycle + RFM combined analysis
- **"What SQL should I write?"** → Generate queries using the known schema (see Database Schema section)
- **"What should I be measuring?"** → Walk through the core metrics framework below

Always ask one clarifying question if the request is ambiguous rather than making assumptions.

---

## Core Metrics Every Nonprofit Should Track

These are the foundational KPIs. When a user doesn't know where to start, introduce these:

| Metric | Definition | Why It Matters |
|---|---|---|
| **Active Donor Rate** | Active donors (L12M gifts) ÷ Total donors in file | Shows file health and engagement |
| **Overall Retention Rate** | Donors who gave again in the next 12 months ÷ donors who gave in prior 12 months | Single most predictive metric of long-term revenue |
| **New-to-File (NTF) Count** | Donors with first-ever gift in L12M | Measures acquisition health |
| **Lapsed Donor Count** | Donors with no gift in 13+ months | Reveals attrition risk |
| **Revenue per Active Donor** | Total L12M revenue ÷ Active donor count | Measures engagement depth |
| **Average Gift** | Total revenue ÷ Total gift count | Baseline for upgrade and ask string strategy |
| **Gifts per Donor** | Total gift count ÷ Active donor count | Frequency indicator; multi-gift donors retain at much higher rates |
| **Active Sustainer Count** | Donors with `gift_type = 'RECURRING'` and `gift_status = 'COMPLETED'` in current month | Monthly recurring revenue base |
| **Monthly Recurring Revenue (MRR)** | Sum of successful sustainer charges in current month | Predictable revenue foundation |
| **Sustainer Monthly Retention Rate** | Sustainers with successful charge this month ÷ sustainers last month | Compounding impact: 94% vs 90%/month = 2× LTV difference |
| **Cost Per Dollar Raised** | Total campaign cost ÷ Total gift amount | Standard fundraising efficiency metric; target < $0.25 for renewal campaigns |
| **Net Revenue** | Total gift amount − Total campaign cost | Bottom-line campaign profitability |

---

## The Four Analytical Frameworks

This skill covers four interconnected frameworks. Read the relevant reference file for detailed guidance:

### 1. Donor Lifecycle Segmentation
**Reference:** `references/donor-lifecycle.md`

Classifies every donor in the file into one of six segments based on recency of giving. The most important framework for understanding overall file health. Use this to:
- Identify whether your donor file is growing or aging
- Spot retention problems before they compound
- Prioritize re-engagement vs. acquisition spend

### 2. Channel Fundraising Analysis
**Reference:** `references/channel-fundraising.md`

Analyzes performance across fundraising channels (Direct Mail, Email, Online, Face-to-Face, Telemarketing, Events). Use this to:
- Understand which channels are growing vs. declining
- Calculate cost-effectiveness by channel
- Identify seasonal patterns and channel mix shifts

### 3. RFM Segmentation Matrix
**Reference:** `references/rfm-segmentation.md`

A 98-cell matrix (7 Recency × 2 Frequency × 7 Monetary bands) for prioritizing outreach. Use this to:
- Decide who to include or exclude from a mailing/campaign
- Estimate expected revenue before a campaign launches
- Identify upgrade candidates and lapse risk

### 4. Sustainer (Monthly Giving) Analytics
**Reference:** `references/sustainer-analytics.md`

Analysis of recurring gift programs across acquisition channels. Use this to:
- Build and interpret 12-month retention curves by channel and cohort
- Diagnose payment failure, early attrition, and upgrade rates
- Calculate sustainer lifetime value (LTV)
- Prioritize actions to grow monthly recurring revenue

---

## Database Schema

All data lives in the **`reporting`** schema. The CRM is organized around four primary relational tables linked by Donor ID, Campaign ID, and Source Code.

### Core Tables

| Table | Primary Key | Purpose |
|---|---|---|
| `reporting.donors` | `donor_id` | Master donor record — one row per donor. Identity, contact info, suppression flags, and calculated giving summaries. |
| `reporting.gifts` | `transaction_id` | Every gift transaction — one row per gift. Financial heart of the CRM. |
| `reporting.promotion_history` | `promotion_id` | Every outreach contact made — one row per donor per campaign. The "sent" ledger. |
| `reporting.campaigns` | `campaign_id` | Campaign-level performance metrics and coding — one row per source code variant. |

### `reporting.donors` — Key Columns

| Column | Type | Notes |
|---|---|---|
| `donor_id` | INT | Primary key; join key across all tables |
| `first_name`, `last_name` | VARCHAR | |
| `email_address` | VARCHAR | |
| `acquisition_date` | DATE | Date of first gift or sign-up |
| `acquisition_source_code` | VARCHAR | Source code of the campaign that acquired this donor |
| `donor_type` | CHAR(1) | `I` = Individual, `O` = Organization, `F` = Foundation |
| `total_gift_amount` | DECIMAL | Cumulative lifetime giving — calculated summary field |
| `total_number_of_gifts` | INT | Lifetime gift count — calculated summary field |
| `first_gift_date` / `first_gift_amount` | DATE / DECIMAL | Calculated summary fields |
| `last_gift_date` / `last_gift_amount` | DATE / DECIMAL | Calculated summary fields; used in lapsed segmentation |
| `largest_gift_amount` | DECIMAL | Calculated summary field |
| `months_since_last_gift` | SMALLINT | Calculated summary field; use for recency queries when speed matters over precision |
| `do_not_mail_flag` | BOOLEAN | Must be excluded from DM campaigns |
| `do_not_email_flag` | BOOLEAN | Must be excluded from email campaigns |
| `do_not_call_flag` | BOOLEAN | Must be excluded from phone outreach |
| `deceased_flag` | BOOLEAN | Must be excluded from all outreach |

### `reporting.gifts` — Key Columns

| Column | Type | Notes |
|---|---|---|
| `transaction_id` | INT | Primary key |
| `donor_id` | INT | Foreign key to `reporting.donors` |
| `gift_date` | DATE | Date received or processed |
| `gift_amount` | DECIMAL | Dollar value |
| `channel` | VARCHAR | `DM`, `EMAIL`, `ONLINE`, `PHONE`, `EVENT`, `MAJOR GIFT` |
| `source_code` | VARCHAR | Attribution bridge to `reporting.campaigns` |
| `campaign_id` | INT | Foreign key to `reporting.campaigns` |
| `gift_type` | VARCHAR | `OUTRIGHT`, `PLEDGE`, `PLEDGE PAYMENT`, `RECURRING`, `IN-KIND`, `BEQUEST` |
| `gift_status` | VARCHAR | `COMPLETED`, `PENDING`, `REVERSED`, `DECLINED` |
| `payment_type` | VARCHAR | `CHECK`, `CREDIT CARD`, `ACH`, `PAYPAL`, etc. |
| `designation_code` | VARCHAR | Fund/program designation (e.g., `GENERAL`, `SCHOLARSHIP`) |

**Critical filters for revenue queries:**
- Always filter `gift_status = 'COMPLETED'` to exclude reversals, chargebacks, and declined gifts
- For sustainer queries: also filter `gift_type = 'RECURRING'`

### `reporting.promotion_history` — Key Columns

| Column | Type | Notes |
|---|---|---|
| `promotion_id` | INT | Primary key |
| `donor_id` | INT | Foreign key to `reporting.donors` |
| `campaign_id` | INT | Foreign key to `reporting.campaigns` |
| `source_code` | VARCHAR | Specific mailing variant |
| `promotion_date` | DATE | Date mailed or deployed |
| `channel` | VARCHAR | `DM`, `EMAIL`, `PHONE`, `DIGITAL`, `EVENT` |
| `segment_code` | VARCHAR | Segmentation code applied for this mailing |
| `ask_amount_1/2/3` | DECIMAL | Suggested gift amounts presented in the ask string |
| `suppress_flag` | BOOLEAN | TRUE = donor was selected but not mailed (honor in analysis) |
| `response_flag` | BOOLEAN | TRUE = donor gave in response to this promotion |
| `response_amount` | DECIMAL | Dollar amount of matched-back response gift |

### `reporting.campaigns` — Key Columns

| Column | Type | Notes |
|---|---|---|
| `campaign_id` | INT | Primary key |
| `source_code` | VARCHAR | Attribution bridge to `reporting.gifts`; one row per source code variant |
| `campaign_name` | VARCHAR | e.g., "2026 Spring Annual Fund" |
| `campaign_date` | DATE | Mail/launch date |
| `channel` | VARCHAR | `DM`, `EMAIL`, `DIGITAL`, `PHONE`, `EVENT`, `INTEGRATED` |
| `program_type` | VARCHAR | `ACQUISITION`, `RENEWAL`, `UPGRADE`, `LAPSED REACTIVATION`, `SUSTAINER` |
| `list_type` | VARCHAR | `HOUSE`, `ACQUISITION`, `LAPSED`, `SWAP`, `RENTAL` |
| `qty_sent` | INT | Pieces mailed or contacts attempted |
| `num_responses` | INT | Gifts attributed to this campaign |
| `total_gift_amount` | DECIMAL | Sum of attributed gift dollars |
| `total_cost` | DECIMAL | Production + fulfillment cost |
| `net_revenue` | DECIMAL | Total gift amount − total cost |
| `response_rate` | DECIMAL | Num responses ÷ qty sent |
| `average_gift_amt` | DECIMAL | Total gift amount ÷ num responses |
| `cost_per_dollar` | DECIMAL | Total cost ÷ total gift amount; target < $0.25 for renewal |
| `return_on_investment` | DECIMAL | Net revenue ÷ total cost |

### How the Tables Connect

```
reporting.donors  ──── donor_id ────►  reporting.gifts
                                              │
                                         source_code / campaign_id
                                              │
                                              ▼
reporting.promotion_history ◄── donor_id ──  reporting.campaigns
        │                         campaign_id / source_code
        └── campaign_id / source_code ───────►
```

**The Source Code** is the central attribution key: when a donor gives in response to a mailing, the source code printed on the reply envelope is captured in `reporting.gifts.source_code` and matched back to `reporting.campaigns.source_code` to attribute the gift to the originating campaign. This is called **campaign match-back**.

---

## Suppression Rules

Before any campaign list is finalized, always exclude:

```sql
WHERE do_not_mail_flag  = FALSE   -- for DM campaigns
  AND do_not_email_flag = FALSE   -- for email campaigns
  AND do_not_call_flag  = FALSE   -- for phone campaigns
  AND deceased_flag     = FALSE   -- always
  AND donor_type        IN ('I', 'O', 'F')  -- confirm appropriate types for campaign
```

---

## Generating SQL

The schema is fully defined above. Generate SQL immediately — no need to ask about table or column names unless the user references something not listed. Always:
- Use `reporting.` prefix on all tables
- Filter `gift_status = 'COMPLETED'` on `reporting.gifts` for all revenue/count queries
- Apply suppression flags when generating campaign selection lists
- Use Redshift/PostgreSQL syntax (`DATE_TRUNC`, `DATEDIFF`, `INTERVAL`)
- Include `NULLIF` to prevent divide-by-zero errors
- Add inline comments explaining non-obvious clauses

See reference files for ready-to-use query templates per framework.

---

## Interpreting Results

When a user shares numbers, help them understand what's good, concerning, or excellent:

| Metric | Concerning | Average | Strong |
|---|---|---|---|
| Overall Retention Rate | < 40% | 40–55% | > 60% |
| New Donor Retention (2nd yr) | < 25% | 30–45% | > 50% |
| Core Donor Retention | < 60% | 65–75% | > 78% |
| Active Donor Rate | < 30% | 35–50% | > 55% |
| Gifts per Active Donor | < 1.2 | 1.3–1.6 | > 1.8 |
| Cost Per Dollar Raised (renewal) | > $0.40 | $0.20–$0.40 | < $0.20 |
| Cost Per Dollar Raised (acquisition) | > $1.50 | $1.00–$1.50 | < $1.00 |
| Response Rate (DM renewal) | < 4% | 5–10% | > 12% |
| Response Rate (DM acquisition) | < 0.5% | 0.8–1.5% | > 2% |

*Note: Benchmarks vary by org size, mission, and acquisition channel.*

---

## Key Principles to Surface Proactively

1. **Retention beats acquisition**: Increasing retention by 5 points is typically worth 2–3× the same investment in new donor acquisition.
2. **Lapsed donors are not lost**: Recently lapsed (13–24 months) donors can be reactivated at 20–40% response rates; long-lapsed (25+ months) at 5–15%.
3. **Second-year conversion is the critical moment**: First-year donors who give a second gift retain at dramatically higher rates going forward. New Prior Year retention (target: 45–55%) deserves dedicated strategy.
4. **Multi-gift donors are gold**: Donors who give 2+ gifts in a year retain at roughly 2× the rate of single-gift donors.
5. **Channel mix shifts signal risk**: If one channel is growing while all others decline, you have concentration risk.
6. **Sustainer monthly retention compounds fast**: The difference between 90% and 95% monthly retention is not 5 points — it's 28% vs. 54% retained at 12 months, roughly 2× lifetime value. Payment failure recovery is almost always the highest-ROI sustainer investment.
7. **Acquisition campaigns should run at a loss — short-term**: Acquisition cost-per-dollar > $1.00 is normal and acceptable if the acquired donors convert to multi-year giving. Evaluate acquisition on 3-year net revenue, not first-campaign ROI.
8. **Source code hygiene drives everything**: If source codes are missing or miscoded on gifts, campaign attribution breaks down and you cannot calculate ROI. Treat source code capture as a data quality priority.

---

## Response Format Guidelines

- Lead with the most actionable insight, not background theory
- Use tables for metric comparisons
- When generating SQL, include inline comments explaining each clause
- When interpreting results, always say what the number means AND what action it suggests
- Offer to go deeper on any topic with a follow-up question
