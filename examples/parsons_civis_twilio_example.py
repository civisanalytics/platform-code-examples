# This script is an example of using the parsons library to import data from
# Twilio using the parsons Twilio connector, and then upload the resulting
# table to Platform using the parsons Civis connector.
# Below are instructions to be able to customize and run this file in Platform.

# Step 1: Copy this file to a github repository that is connected to Platform.
#         For docs on how to connect Platform to Github, follow the steps in
#         the first two paragraphs under "Connecting Platform to Github/Bitbucket":
#         https://civis.zendesk.com/hc/en-us/articles/115003734992-Version-Control


# Step 2: Create a new container script in Platform with the following fields:
#         GITHUB REPOSITORY URL: The github repository from Step 1
#         GITHUB REPOSITORY REFERENCE: The branch name that contains the copy of this file.
#         COMMAND: python /app/<path to the copy of this file>
#         DOCKER IMAGE NAME: movementcooperative/parsons
#         DOCKER IMAGE TAG: v0.16.0
#         Docs: https://civis.zendesk.com/hc/en-us/articles/218200643-Container-Scripts


# Step 3: Set CIVIS_DATABASE and CIVIS_TABLE global variables below
#         CIVIS_TABLE should be in "schema.table" form
#         See list of databases: platform.civisanalytics.com/spa/remote_hosts

CIVIS_DATABASE = 32
CIVIS_TABLE = "twilio_test.account_usage"

# Step 4: Create a platform custom credential with the following fields:
#         Name: Twilio Account
#         Credential Type: Custom
#         Username: Twilio Account SID
#         Password: Twilio Auth Token
#
#         To create platform credentials: platform.civisanalytics.com/spa/credentials/new
#         Note: both twilio variables can be found at www.twilio.com/console

# Step 5: Run the container script!

# For complete documentation on parsons twilio & civis connectors, see:
# Civis: github.com/move-coop/parsons/blob/master/parsons/civis/civisclient.py
# Twilio: github.com/move-coop/parsons/blob/master/parsons/twilio/twilio.py

from parsons.civis.civisclient import CivisClient
from parsons.twilio.twilio import Twilio
import os

class CivisTwilioConnector:

    def __init__(self):
        self.validate_params()
        self.civis_client = CivisClient(db=CIVIS_DATABASE)
        self.twilio_client = Twilio(
            account_sid=os.environ.get('TWILIO_ACCOUNT_USERNAME'),
            auth_token=os.environ.get('TWILIO_ACCOUNT_PASSWORD')
            )


    def twilio_to_civis(self):
        table = self.twilio_client.get_account_usage()
        self.civis_client.table_import(table, CIVIS_TABLE, existing_table_rows='drop')


    def read_from_civis(self):
        query = f"SELECT * from {CIVIS_TABLE}"
        table = self.civis_client.query(query)
        print(table)

    def validate_params(self):
        pass
        # TODO: validate params

if __name__ == "__main__":
    connector = CivisTwilioConnector()
    connector.twilio_to_civis()
    connector.read_from_civis()
