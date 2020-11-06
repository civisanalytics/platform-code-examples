# This script is an example of using the parsons library to import data from
# Twilio using the parsons Twilio connector, and then upload the resulting
# table to Platform using the parsons Civis connector.
from parsons.civis.civisclient import CivisClient
from parsons.twilio.twilio import Twilio

# Step 1: Open a new Python script in Platform, and paste this entire file
#         into the script body.
#         TODO: this would require adding parsons to datascience-python

# Step 2: Set CIVIS_DATABASE and CIVIS_TABLE variables.
#         CIVIS_TABLE should be in "schema.table" form
#         See list of databases: platform.civisanalytics.com/spa/remote_hosts

# Step 3: Set environment variables necessary for the clients:
#         CIVIS_API_KEY: Civis API key
#         TWILIO_ACCOUNT_SID: Twilio Account SID
#         TWILIO_AUTH_TOKEN: Twilio Auth Token
#         Note: both twilio variables can be found at www.twilio.com/console

# For complete documentation on parsons twilio & civis connectors, see:
# Civis: github.com/move-coop/parsons/blob/master/parsons/civis/civisclient.py
# Twilio: github.com/move-coop/parsons/blob/master/parsons/twilio/twilio.py

CIVIS_DATABASE = 99
CIVIS_TABLE = "twilio_test.account_usage"

civis_client = CivisClient(db=CIVIS_DATABASE)
twilio_client = Twilio()


def twilio_to_civis():
    table = twilio_client.get_account_usage()
    civis_client.table_import(table, CIVIS_TABLE, existing_table_rows='drop')


def read_from_civis():
    query = f"SELECT * from {CIVIS_TABLE}"
    table = civis_client.query(query)
    print(table)


twilio_to_civis()
read_from_civis()
