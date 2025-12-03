// test comment #1 from local dev
// test comment #2 from studio
# Platform Code Examples Repository

This repository contains various code examples and scripts used across different platforms and technologies. It is organized into several directories based on the language and purpose of the scripts.

## Kinds of Examples

- dbt
- javascript
- python
- workflows

### dbt

Contains dbt models, seeds, and configuration files.

- `dbt_project.yml`: Main configuration file for the dbt project.
- `profiles.yml`: Profiles configuration for dbt.
- `models/`: SQL models for dbt.
- `seeds/`: Seed files for dbt.

For more details see the [README.md](./dbt/README.md) in the dbt directory.

### javascript

Contains JavaScript scripts and configurations.

- `email_reporting_scripted_sql/`: Scripts for email reporting using SQL.

### python

Contains Python scripts and configurations.

- `email_reporting_python/`: Scripts for email reporting using Python.
- `parsons_civis_twiliio_example/`: Example scripts using Parsons, Civis, and Twilio.
- `turn_off_notifications/`: Scripts to turn off notifications.

### workflows

Contains various workflow scripts.

- `facebook_ad_insights_workflow/`: Workflow for Facebook Ad Insights.
- `fail_if_prev_execution_is_running`: Enforce only one workflow execution at a time
- `van_multistate_workflow`: Van workflow for multiple states
- `van_turf_import`: Van workflow to import van turfs


## Getting Started

### Initial Setup

1. Clone the repository:
  ```sh
  git clone https://github.com/civisanalytics/platform-code-examples.git
  cd platform-code-examples
  ```

### Installing Dependencies

1. Set up a virtual environment:
  ```sh
  python3 -m venv venv
  source venv/bin/activate
  python3 -m pip install --upgrade pip
  ```

2. Install `pip-tools`:
  ```sh
  pip install pip-tools
  ```

3. Update dependencies:
  ```sh
  pip-compile -o dbt/<version>/requirements.txt dbt/<version>/requirements.txt.in
  ```
