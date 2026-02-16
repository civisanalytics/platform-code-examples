#!/bin/bash

# ===================================================================
# Example: Rendering an HTML Report from R Markdown in GitHub
# ===================================================================
#
# This script demonstrates how to render an R Markdown file from a
# GitHub repository using a Civis Container Script.
#
# Prerequisites:
# - Use a Container Script with the civisanalytics/datascience-r image
# - Configure the git repository settings in the Container Script
# - The git repository will be cloned into the /app directory
#
# Usage:
# - Update the path to your R Markdown file in the repository
# - Use this command in your Container Script's command field

# The R Markdown file path should be updated to match your repo structure
# Replace "/app/path/to/example.Rmd" with the actual path in your repository

Rscript -e '
reportId <- civis::publish_rmd("/app/R/rmarkdown/example_report.Rmd");
jobId <- as.numeric(Sys.getenv("CIVIS_JOB_ID"));
runId <- as.numeric(Sys.getenv("CIVIS_RUN_ID"));
civis::scripts_post_containers_runs_outputs(jobId, runId, "Report", reportId)
'

echo "HTML report successfully generated from GitHub repository and attached to run output."
