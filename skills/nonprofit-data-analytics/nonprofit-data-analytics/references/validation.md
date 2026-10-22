# Report Validation — Reference Guide

Use this guide when the user wants to check a dashboard or report against the source data, for example "run your validation questions", "validate the report", or "compare against the live report". Answer a fixed set of questions directly from the reporting schema, then compare those answers to the report. Agreement shows the report is built on the right definitions. Disagreement points to a definition, filter, or date-window difference.

## The Questions

Unless the user says otherwise, ask all questions about the house file (the org's own donors, excluding acquisition-list prospects), as of today.

1. How many active donors are on the file (donors who gave at least once in the last 12 months)?
2. What is the overall donor retention rate right now?
3. Which channel drove the most revenue in the last 12 months, and how much?
4. How many donors are in the recently lapsed segment?
5. Among recently lapsed donors, what is the breakdown by a donor attribute the report also shows (for example `donor_type`, last-gift channel, or a wealth/capacity rating if the org has one)? Show NULL values as their own group.

Adapt the questions to the report being checked. If the report doesn't show one of these metrics, swap in an equivalent (for example sustainer count or MRR) and use the matching definition from `references/sustainer-analytics.md`.

## Protocol

1. **Derive the SQL fresh.** Build each query from the schema and metric definitions in this skill (`SKILL.md`, `references/donor-lifecycle.md`, `references/channel-fundraising.md`). Don't reuse numbers or queries from earlier sessions, and don't treat any previous answer as a target.
2. **Run the queries.** Independent queries can run in parallel. Request enough result rows that grouped results aren't truncated.
3. **Present the answers** in one table with the run date and the interpretation used for each. Every window is rolling from `CURRENT_DATE`, so the run date is part of the answer.
4. **Run internal consistency checks** before trusting the results, and report any that fail:
   - Q2 and Q4 must reconcile: donors who gave 13–24 months ago, minus those who gave again in the last 12 months, equals the recently lapsed count.
   - Q1 must match the lifecycle definition: active donors are the four active lifecycle segments combined.
   - Q3 channel revenues must sum to total house-file revenue for the same window.
   - Q5 counts must sum to the Q4 count.
5. **Compare to the report.** Ask the user for the report's numbers, URL, or SQL. Build a comparison table with columns: metric, validation value, report value, difference, status (match or mismatch).
6. **Diagnose every mismatch** before saying either side is wrong. Re-run the validation query using the report's apparent definition and see whether it reproduces the report's number. Common drivers to test:
   - House-file filter missing or applied differently
   - Rolling window versus fixed or calendar window, and months versus days
   - Gift types included or excluded (sustainer installments, DAF, pledge fulfillments)
   - `gift_status = 'COMPLETED'` filter missing, so reversals or declines are counted
   - Different run date or data refresh time
   - Channel versus attributed channel, and channel codes dropped or unmapped in the report
   - Retention denominator (prior-year donors versus all donors) and which period is treated as "prior"
   - "Lapsed" scope: recently lapsed only versus all lapsed including long-lapsed
   - Breakdown attribute ranked by donor count versus revenue or another measure, or read from a different column
7. **Conclude clearly.** For each question, say one of: match, explained mismatch (name the definition difference), or unexplained mismatch (needs investigation). If the user wants a shareable artifact, show each question, its answer, the SQL used, and the comparison status.
