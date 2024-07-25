# Platform Code Examples - Python


This directory contains Python scripts and configurations used for various purposes, including email reporting, integration with Civis and Twilio, and turning off notifications.

## Getting Started

### Initial Setup

1. Set up a virtual environment:
    ```sh
    python3 -m venv venv
    source venv/bin/activate
    python3 -m pip install --upgrade pip
    ```

2. Install dependencies:
    ```sh
    pip install -r requirements.txt
    ```

## Scripts

### Email Reporting

The scripts in the `email_reporting_python/` directory are used for generating and sending email reports.

### Civis and Twilio Integration

The `parsons_civis_twiliio_example/` directory contains scripts that demonstrate how to integrate Civis and Twilio using the Parsons library. For example, the [`parsons_civis_twilio_example.py`](python/parsons_civis_twiliio_example/parsons_civis_twilio_example.py) script shows how to import data from Twilio to Civis and query data from Civis.

### Turn Off Notifications

The `turn_off_notifications/` directory contains a script to turn off notifications for all jobs, imports, and workflows owned by the running user. For example, the [`turn_off_notifications.py`](python/turn_off_notifications/turn_off_notifications.py) script handles this functionality.
