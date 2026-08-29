import civis
from pathlib import Path
from datetime import datetime

# This example demonstrates how to programatically generate a new Civis API key 
# and update a local configuration file with the new key. This script will need 
# to be automated locally, such as with cron, or run manually periodically.
# 
# This example expects a .civis file in the user's home directory
# A single line is written to this file setting the API key. This file is then
# imported to the shell configuration script on the system
# such as with .source ~/.civis in your .bashrc or .zshrc file on Posix systems.
#
# For Windows based systems, replace the path below with an absolute path to a .env 
# file in your project folder. Then load that value at the top of your scripts such 
# as with dotenv: https://pypi.org/project/python-dotenv/#getting-started


_KEY_FILE = Path("~/.civis").expanduser()
# _KEY_FILE = Path.WindowsPath("c:/absolute/path/to/.env")

current_time = datetime.now().isoformat()

# This assumes that there is already a valid API key configured on the system. If no
# key is present or the key is expired, this block will fail.
client = civis.APIClient()
user = client.users.list_me()

# the new key is generated
# in this example, the key expires after 1 day or 86400 seconds
# maximum API key expiration is 30 days.
new_key_rep = client.users.post_api_keys(
    "me", expires_in=86400, name=f"{user.username}_local_key_regerated_{current_time}"
)

key_string = f"CIVIS_API_KEY={new_key_rep.token}"


# finally now that a new key has been generated, 
with open(_KEY_FILE, "w") as key_file:
    key_file.seek(0)
    key_file.write(key_string)
    key_file.truncate()
