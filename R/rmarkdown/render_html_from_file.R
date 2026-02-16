#!/usr/bin/env Rscript

# ===================================================================
# Example: Rendering an HTML Report from R Markdown in a Civis File
# ===================================================================
#
# This script demonstrates how to:
# 1. Download an R Markdown file from Civis Files
# 2. Render it to HTML using publish_rmd()
# 3. Attach the resulting HTML report as a run output
#
# Prerequisites:
# - The civis R package must be installed
# - An R Markdown file must be uploaded to Civis Files
#
# Usage:
# - Update the fileId variable with your Civis File ID
# - Run this script in a Civis R Script

library(civis)

# Configuration
fileId <- 12345  # CHANGE THIS: Enter your File ID here

# Download the R Markdown file from Civis Files
civis::download_civis(fileId, file = "example.Rmd")

# Render the R Markdown file and publish as an HTML report
reportId <- civis::publish_rmd("example.Rmd")

# Get the current job and run IDs from environment variables
jobId <- as.numeric(Sys.getenv("CIVIS_JOB_ID"))
runId <- as.numeric(Sys.getenv("CIVIS_RUN_ID"))

# Attach the HTML report as a run output
civis::scripts_post_r_runs_outputs(jobId, runId, "Report", reportId)

cat("HTML report successfully generated and attached to run output.\n")
cat("Report ID:", reportId, "\n")
