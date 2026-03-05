# Demo App - Mock Data
# All static data used by the demo app lives here.

# ── Reports ───────────────────────────────────────────────────────────────────

reports_data <- data.frame(
  name = c(
    "Malaria Quarterly Report",
    "Facility Level Dashboard",
    "SMC Dashboard",
    "Malaria in Pregnancy Dashboard",
    "Vector Control Dashboard"
  ),
  description = c(
    "Tracks confirmed malaria cases, deaths, and reporting rates across PMI-supported countries on a quarterly basis.",
    "Monitors HMIS reporting rates and case data at the facility level for targeted follow-up.",
    "Summarizes seasonal malaria chemoprevention coverage and distribution across supported regions.",
    "Monitors malaria prevention and treatment indicators for pregnant women across PMI countries.",
    "Tracks indoor residual spraying coverage and insecticide-treated net distribution and usage."
  ),
  report_type        = c("Shiny", "Shiny", "Shiny", "Shiny", "Tableau"),
  development_status = c("Production", "Production", "In Development", "Production", "Production"),
  technical_area     = c("Case Management", "Health Systems", "SMC", "Malaria in Pregnancy", "Vector Control"),
  tags               = c(
    "malaria;quarterly;HMIS;cases",
    "facility;reporting;HMIS",
    "SMC;prevention;chemoprevention",
    "MIP;pregnancy;prevention",
    "IRS;ITN;vector control"
  ),
  category           = c("HMIS", "HMIS", "Interventions", "Interventions", "Interventions"),
  featured           = c(1, 2, 3, 4, 5),
  location_link      = rep("#", 5),
  stringsAsFactors   = FALSE
)

# ── Data Catalog ──────────────────────────────────────────────────────────────

data <- data.frame(
  name = c(
    "QR Reporting Table",
    "Facility Master List",
    "LMIS Stock Data",
    "SMC Coverage Data",
    "Population Estimates"
  ),
  description = c(
    "Monthly malaria case and reporting data aggregated from national HMIS systems across PMI-supported countries.",
    "Master list of all PMI-supported health facilities including location and administrative hierarchy.",
    "Logistics management data including commodity stockouts, consumption, and stock on hand.",
    "Seasonal malaria chemoprevention campaign coverage data by cycle and administrative unit.",
    "Annual population estimates by administrative unit used for rate calculations."
  ),
  full_description = c(
    "The QR Reporting Table contains monthly malaria surveillance data compiled from national HMIS systems
     across all PMI-supported countries. It includes confirmed cases, suspected cases, malaria deaths,
     and testing data broken down by administrative unit (admin 1 and admin 2), facility, and month.
     Reporting rates and completeness indicators are also included to help users assess data quality.
     This table is the primary data source for the Malaria Quarterly Report dashboard.",
    "The Facility Master List is the authoritative reference for all PMI-supported health facilities.
     It includes facility names, unique identifiers, administrative hierarchy (country, admin 1, admin 2),
     GPS coordinates where available, facility type, and ownership category.
     It is used as a lookup table across multiple M-DIVE dashboards to ensure consistent facility naming
     and geographic attribution.",
    "The LMIS Stock Data table contains commodity tracking information from national logistics management
     information systems. It covers stock on hand, quantities received, quantities consumed, and stockout
     days for key malaria commodities including ACTs, RDTs, and ITNs. Data is reported at the facility
     level on a monthly basis. Access is restricted due to the sensitivity of supply chain information.",
    "The SMC Coverage Data table contains campaign-level coverage data for seasonal malaria
     chemoprevention programs. Each row represents one administrative unit in one campaign cycle,
     with fields for target population, children reached, and coverage percentage.
     Data is available for all PMI-supported countries with active SMC programs.",
    "The Population Estimates table provides annual population denominators by administrative unit
     used across M-DIVE for calculating rate-based indicators (e.g. cases per 1,000 population).
     Estimates are derived from national census projections and are updated annually."
  ),
  technical_area       = c("Case Management", "Health Systems", "Supply Chain", "SMC", "Cross-cutting"),
  tags                 = c(
    "malaria;HMIS;cases;reporting",
    "facilities;geo;admin",
    "LMIS;stockouts;commodities",
    "SMC;coverage;campaigns",
    "population;denominators"
  ),
  access_restrictions  = c(
    "Open use within M-DIVE",
    "Open use within M-DIVE",
    "Restricted",
    "Open use within M-DIVE",
    "Publicly Available"
  ),
  clean_last_data_update = c(
    "January 2026", "December 2025", "November 2025", "October 2025", "January 2026"
  ),
  last_data_update     = as.Date(c(
    "2026-01-01", "2025-12-01", "2025-11-01", "2025-10-01", "2026-01-01"
  )),
  source               = c(
    "National HMIS (DHIS2)",
    "PMI Country Teams",
    "National LMIS",
    "PMI SMC Program",
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
    "Malaria Quarterly Report; Facility Level Dashboard",
    "Facility Level Dashboard",
    "",
    "SMC Dashboard",
    "Malaria Quarterly Report; Malaria in Pregnancy Dashboard"
  ),
  stringsAsFactors = FALSE
)
