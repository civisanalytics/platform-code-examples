# R Markdown Examples for Civis Platform

This directory contains example code for creating reports with R Markdown on Civis Platform, based on the [Creating Reports with R Markdown](https://support.civisanalytics.com/hc/en-us/articles/360036425472-Creating-Reports-with-R-Markdown) article.

## Overview

R Markdown is an authoring framework for creating documents with analyses and visualizations in R. While Civis Platform does not have a built-in user interface specifically for R Markdown, you can render R Markdown files in Scripts and save them as outputs.

## Files in this Directory

### R Markdown Template

- **[example_report.Rmd](rmarkdown/example_report.Rmd)** - A sample R Markdown document that demonstrates:
  - Data analysis with the mtcars dataset
  - Creating visualizations with ggplot2
  - Running statistical models
  - Generating HTML or PDF output

### Rendering Scripts

1. **[render_html_from_file.R](rmarkdown/render_html_from_file.R)** - Renders an HTML report from an R Markdown file stored in Civis Files
   - Downloads .Rmd file from Civis Files
   - Uses `civis::publish_rmd()` to render HTML
   - Attaches report as run output

2. **[render_pdf_from_file.R](rmarkdown/render_pdf_from_file.R)** - Renders a PDF from an R Markdown file stored in Civis Files
   - Downloads .Rmd file from Civis Files
   - Uses `rmarkdown::render()` to create PDF
   - Uploads PDF to Civis Files
   - Attaches as run output

3. **[render_from_github.sh](rmarkdown/render_from_github.sh)** - Renders an HTML report from R Markdown in a GitHub repository
   - For use in Container Scripts
   - Uses the civisanalytics/datascience-r Docker image
   - Renders files directly from cloned repository

## Usage

### Option 1: Using R Scripts with Civis Files

1. Upload your .Rmd file to Civis Files and note the File ID
2. Create a new R Script in Civis Platform
3. Copy the code from either `render_html_from_file.R` or `render_pdf_from_file.R`
4. Update the `fileId` variable with your Civis File ID
5. Run the script

### Option 2: Using Container Scripts with GitHub

1. Store your .Rmd file in a GitHub repository
2. Create a new Container Script in Civis Platform
3. Configure the script to use the `civisanalytics/datascience-r` Docker image
4. Set up the git repository settings to clone your repo
5. Use the command from `render_from_github.sh`, updating the file path
6. Run the script

## Prerequisites

### For R Scripts:
- `civis` R package installed
- `rmarkdown` R package (for PDF output)
- LaTeX distribution (for PDF rendering)
- CIVIS_API_KEY environment variable set

### For Container Scripts:
- Access to Civis Container Scripts
- GitHub repository with your R Markdown files
- civisanalytics/datascience-r Docker image

## Customizing the Example Report

The [`example_report.Rmd`](rmarkdown/example_report.Rmd) file can be customized to:
- Connect to Civis Platform databases using the `civis` package
- Query data using `civis::read_civis()`
- Create custom visualizations
- Add your own analysis code
- Modify the output format (HTML, PDF, Word, etc.)

## Output Formats

R Markdown supports multiple output formats. In the YAML header of your .Rmd file, you can specify:

```yaml
---
output:
  html_document:
    toc: true
    theme: cosmo
  pdf_document:
    toc: true
  word_document: default
---
```

## Additional Resources

- [R Markdown Documentation](https://rmarkdown.rstudio.com/)
- [Civis R Client Documentation](https://civisanalytics.github.io/civis-r/index.html)
- [R Notebooks in Platform](https://support.civisanalytics.com/hc/en-us/articles/115003386866-R-Notebooks) (alternative to R Markdown)
- [Civis Platform Docker Images](https://support.civisanalytics.com/hc/en-us/articles/217294746-Public-Civis-Docker-Images)

## Notes

- R Notebooks in Civis Platform offer an interactive alternative to R Markdown
- The `publish_rmd()` function is specifically designed for Civis Platform
- For PDF output, ensure a LaTeX distribution is available in your environment
- Reports can be scheduled to run automatically using Civis Platform's scheduling features
