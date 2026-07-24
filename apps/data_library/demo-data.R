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
    "Tracks confirmed cases and reporting rates across a selection of countries on a quarterly basis.",
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
    "QR Reporting Table",
    "Facility Master List",
    "Inventory Stock Data",
    "Program Coverage Data",
    "Population Estimates"
  ),
  description = c(
    "Monthly case and reporting data aggregated from national health information systems across supported countries.",
    "Master list of all supported health facilities including location and administrative hierarchy.",
    "Logistics data including commodity stockouts, consumption, and stock on hand.",
    "Campaign coverage data by cycle and administrative unit.",
    "Annual population estimates by administrative unit used for rate calculations."
  ),
  full_description = c(
    "The QR Reporting Table contains monthly surveillance data compiled from national health information systems
     across all supported countries. It includes confirmed cases, suspected cases, and testing data broken down
     by administrative unit (admin 1 and admin 2), facility, and month. Reporting rates and completeness
     indicators are also included to help users assess data quality. This table is the primary data source
     for the Quarterly Report dashboard.",
    "The Facility Master List is the authoritative reference for all supported health facilities.
     It includes facility names, unique identifiers, administrative hierarchy (country, admin 1, admin 2),
     GPS coordinates where available, facility type, and ownership category.
     It is used as a lookup table across multiple dashboards to ensure consistent facility naming
     and geographic attribution.",
    "The Inventory Stock Data table contains commodity tracking information from national logistics
     information systems. It covers stock on hand, quantities received, quantities consumed, and stockout
     days for key commodities. Data is reported at the facility level on a monthly basis.
     Access is restricted due to the sensitivity of supply chain information.",
    "The Program Coverage Data table contains campaign-level coverage data for seasonal intervention
     programs. Each row represents one administrative unit in one campaign cycle, with fields for
     target population, individuals reached, and coverage percentage.
     Data is available for all supported countries with active programs.",
    "The Population Estimates table provides annual population denominators by administrative unit
     used across the platform for calculating rate-based indicators (e.g. cases per 1,000 population).
     Estimates are derived from national census projections and are updated annually."
  ),
  technical_area       = c("Case Management", "Health Systems", "Supply Chain", "Campaigns", "Cross-cutting"),
  tags                 = c(
    "surveillance;cases;reporting",
    "facilities;geo;admin",
    "stockouts;commodities;logistics",
    "coverage;campaigns",
    "population;denominators"
  ),
  access_restrictions  = c(
    "Open use within platform",
    "Open use within platform",
    "Restricted",
    "Open use within platform",
    "Publicly Available"
  ),
  clean_last_data_update = c(
    "January 2026", "December 2025", "November 2025", "October 2025", "January 2026"
  ),
  last_data_update     = as.Date(c(
    "2026-01-01", "2025-12-01", "2025-11-01", "2025-10-01", "2026-01-01"
  )),
  source               = c(
    "National Health Information System",
    "Country Program Teams",
    "National Logistics System",
    "National Program Office",
    "National Census Projections"
  ),
  unit_of_analysis     = c(
    "Country / Admin 1 / Admin 2 / Month",
    "Facility",
    "Facility / Month",
    "Admin unit / Campaign cycle",
    "Admin unit / Year"
  ),
  associated_reports   = c(
    "Quarterly Report; Facility Level Dashboard",
    "Facility Level Dashboard",
    "",
    "Cases Dashboard",
    "Quarterly Report; Disease in Pregnancy Dashboard"
  ),
  stringsAsFactors = FALSE
)
