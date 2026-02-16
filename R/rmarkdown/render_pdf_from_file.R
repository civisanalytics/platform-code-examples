#!/usr/bin/env Rscript

# ===================================================================
# Example: Rendering a PDF from R Markdown in a Civis File
# ===================================================================
#
# This script demonstrates how to:
# 1. Download an R Markdown file from Civis Files
# 2. Render it to PDF using rmarkdown::render()
# 3. Upload the PDF to Civis Files
# 4. Attach the PDF as a run output
#
# Prerequisites:
# - The civis and rmarkdown R packages must be installed
# - A LaTeX distribution must be available (for PDF rendering)
# - An R Markdown file must be uploaded to Civis Files
# - CIVIS_API_KEY environment variable must be set
#
# Usage:
# - Update the fileId variable with your Civis File ID
# - Run this script in a Civis R Script

library(civis)
library(rmarkdown)

# Configuration
fileId <- 12345  # CHANGE THIS: Enter your File ID here

# Download the R Markdown file from Civis Files
civis::download_civis(fileId, file = "example.Rmd")

# Render the R Markdown file to PDF
rmarkdown::render("example.Rmd", output_format = "pdf_document")

# Upload the PDF to Civis Files (set expires_at to NULL for permanent storage)
pdfFileId <- civis::write_civis_file("example.pdf", expires_at = NULL)

# Get the current job and run IDs from environment variables
jobId <- as.numeric(Sys.getenv("CIVIS_JOB_ID"))
runId <- as.numeric(Sys.getenv("CIVIS_RUN_ID"))

# Attach the PDF as a run output
civis::scripts_post_r_runs_outputs(jobId, runId, "File", pdfFileId)

cat("PDF report successfully generated and attached to run output.\n")
cat("PDF File ID:", pdfFileId, "\n")
