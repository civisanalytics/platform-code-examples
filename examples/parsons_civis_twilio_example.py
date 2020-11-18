# This script is an example of using the Parsons library to import data from
# Twilio using the Parsons Twilio connector, and then upload the resulting
# table to Platform using the Parsons Civis connector.
# Below are instructions to be able to customize and run this file in Platform.

# Step 1: Copy this file to a Github repository that is connected to Platform.
#         For docs on how to connect Platform to Github, follow the steps in
#         the first two paragraphs under "Connecting Platform to Github/Bitbucket":
#         https://civis.zendesk.com/hc/en-us/articles/115003734992-Version-Control

# Step 2: Set CIVIS_DATABASE and CIVIS_TABLE global variables below
#         List of databases: platform.civisanalytics.com/spa/remote_hosts
#         CIVIS_TABLE should be in "schema.table" form

CIVIS_DATABASE = 99
CIVIS_TABLE = "twilio_test.account_usage"

# Step 3: Create a platform custom credential with the following fields:
#         Name: Twilio Account
#         Credential Type: Custom
#         Username: <Twilio Account SID>
#         Password: <Twilio Auth Token>
#
#         Docs on creating platform credentials: platform.civisanalytics.com/spa/credentials/new
#         Twilio Account SID & Auth Token can be found at www.twilio.com/console

# Step 4: Create a Platform container script (Code -> Container) with the following fields:
#         GITHUB REPOSITORY URL: <Github repository from Step 1>
#         GITHUB REPOSITORY REFERENCE: <Github Branch that contains the copy of this file>
#         COMMAND: pip install pandas
#                  python /app/examples/parsons_civis_twilio_example.py
#         DOCKER IMAGE NAME: movementcooperative/parsons
#         DOCKER IMAGE TAG: v0.16.0
#
#         Container Scripts docs:
#         https://civis.zendesk.com/hc/en-us/articles/218200643-Container-Scripts

# Step 5: Add a parameter to the container (Set Parameters) with the following fields:
#         TYPE: Custom Credential
#         REQUIRED: Yes
#         PARAMETER NAME: TWILIO_ACCOUNT
#         INPUT DISPLAY NAME (OPTIONAL): TWILIO ACCOUNT CREDENTIAL

# Step 6: Set the TWILIO ACCOUNT CREDENTIAL parameter from Step 5 to be the
#         credential created in Step 3

# Step 7: Run the container script!

# For complete documentation on Parsons Twilio & Civis connectors, see:
# Civis: github.com/move-coop/parsons/blob/master/parsons/civis/civisclient.py
# Twilio: github.com/move-coop/parsons/blob/master/parsons/twilio/twilio.py

from parsons.civis.civisclient import CivisClient
from parsons.twilio.twilio import Twilio
import os


class CivisTwilioConnector:

    def __init__(self):
        self.validate_environment()
        self.civis_client = CivisClient(db=CIVIS_DATABASE)
        self.twilio_client = Twilio(
            account_sid=os.environ.get('TWILIO_ACCOUNT_USERNAME'),
            auth_token=os.environ.get('TWILIO_ACCOUNT_PASSWORD'))

    def twilio_to_civis(self):
        table = self.twilio_client.get_account_usage()
        self.civis_client.table_import(table, CIVIS_TABLE, existing_table_rows='drop')

    def read_from_civis(self):
        query = f"SELECT * from {CIVIS_TABLE}"
        table = self.civis_client.query(query)
        print(table)

    def validate_environment(self):
        if not os.environ.get('TWILIO_ACCOUNT_USERNAME'):
            raise ValueError(
                "No credential named 'Twilio Account' found, see Step 4")
        if not os.environ.get('TWILIO_ACCOUNT_PASSWORD'):
            raise ValueError(
                "'Twilio Account' credential must be a custom credential, see Step 4")


if __name__ == "__main__":
    connector = CivisTwilioConnector()
    connector.twilio_to_civis()
    connector.read_from_civis()
