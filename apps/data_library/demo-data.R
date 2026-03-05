# Demo App - Mock Data
# All static data used by the demo app lives here.

# ── Reports ───────────────────────────────────────────────────────────────────

reports_data <- data.frame(
  name = c(
    "Quarterly Report",
    "Facility Level Dashboard",
    "Cases Dashboard",
    "Disease in Pregnancy Dashboard",
    "Treatment Dashboard"
  ),
  description = c(
    "Tracks confirmed cases, deaths, and reporting rates across a selection of countries on a quarterly basis.",
    "Monitors reporting rates and case data at the facility level for targeted follow-up.",
    "Summarizes case data across supported regions.",
    "Monitors disease in pregnancy indicators across supported regions.",
    "Tracks treatment indicators across supported regions."
  ),
  report_type      = c("Shiny", "Shiny", "Shiny", "Shiny", "Tableau"),
  development_status = c("Production", "Production", "In Development", "Production", "Production"),
  technical_area   = c("Reporting", "Reporting", "Measurement", "Measurement", "Treatment"),
  tags             = c(
    "quarterly;cases;reporting",
    "facility;reporting;cases",
    "cases;measurement",
    "disease;pregnancy;measurement",
    "treatment;cases"
  ),
  category         = c("General", "General", "Interventions", "Interventions", "Interventions"),
  featured         = c(1, 2, 3, 4, 5),
  location_link    = rep("#", 5),
  stringsAsFactors = FALSE
)
# ── Data Catalog ──────────────────────────────────────────────────────────────

data <- data.frame(
  name = c(
    "Reporting Table",
    "Facility Master List",
    "Stock Data",
    "Coverage Data",
    "Population Estimates"
  ),
  description = c(
    "Monthly reporting data aggregated from national systems across supported countries.",
    "Master list of all supported health facilities including location and administrative hierarchy.",
    "Logistics management data including commodity stockouts, consumption, and stock on hand.",
    "Seasonal campaign coverage data by cycle and administrative unit.",
    "Annual population estimates by administrative unit used for rate calculations."
  ),
  technical_area       = c("Case Management", "Health Systems", "Supply Chain", "Coverage", "Population"),
  tags                 = c(
    "monthly;reporting;cases",
    "facility;reporting;cases",
    "stock;logistics;commodities",
    "coverage;campaigns;SMC",
    "population;denominators"
  ),
  access_restrictions  = c(
    "Open use",
    "Open use",
    "Restricted",
    "Open use",
    "Publicly Available"
  ),
  clean_last_data_update = c(
    "January 2026", "December 2025", "November 2025", "October 2025", "January 2026"
  ),
  last_data_update     = as.Date(c(
    "2026-01-01", "2025-12-01", "2025-11-01", "2025-10-01", "2026-01-01"
  )),
  stringsAsFactors = FALSE
)