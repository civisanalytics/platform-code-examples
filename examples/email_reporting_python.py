# This script is an example of how to transform the results of SQL queries in
# Markdown for email reporting. Both values and tables can both be transformed
# to Markdown for email reporting.
import civis
import json
import os

# Step 1: Open a new Python script in Platform, and paste this entire file
#         into the script body.
#
# Step 2: Update the query you wish to deliver in an email report
#         (value, table, or both)

# Swap out name of database for your own
DATABASE = 'database_name'


def main():
    # Value example (swap query for your own):
    number = query_to_variable('SELECT max(genre_id) FROM movielens.genres')

    # Table example (swap query for your own; result is limited to 100 rows):
    md_table = query_to_markdown_table('SELECT * FROM movielens.genres')

    # Upload the value and table as a run output JSONValue
    # named "email_outputs":
    json_value_dict = {
        'number': number,
        'md_table': md_table
    }
    post_json_run_output(json_value_dict)

# Step 3: Add the markdown to the body of your email notifications.
#
# If you wish to add a value in-line, add it in-line in the email body:
# Our largest donation this week was {{number}}.
#
# If you wish to add a table, you'll need to add a line break
# before and after the table:
# Here is a summary of all donations:
#
# {{md_table}}
#
#
# Step 4: Run the job/schedule the job/receive your email reports.
#
# ****


# Functions below will not require editing, but
# need to be included in the script
def query_to_variable(qtext):
    result = query(qtext)['result_rows']

    # checks length of query result, returns query or error message
    if len(result) == 1:
        output = result[0][0]
    elif len(result) > 1:
        output = "Error! query returned more than 1 row."
    else:
        output = "Error!"

    return output


def query(qtext):
    return civis.io.query_civis(qtext, DATABASE).result()


def query_to_markdown_table(qtext):
    return to_markdown_table(query(qtext))


# adapted from https://source.opennews.org/en-US/articles/introducing-sheetdown
# converts a SQL query to markdown
def to_markdown_table(data):
    table = '|'
    under_headers = ''
    for header in data['result_columns']:
        table += header + '|'
        under_headers += ' ------ |'
    table += '\n|' + under_headers + '\n'
    for row in data['result_rows']:
        table += '|' + '|'.join(row) + '|\n'
    return table


def post_json_run_output(json_value_dict):
    client = civis.APIClient()
    json_value_object = client.json_values.post(
            json.dumps(json_value_dict),
            name='email_outputs'
            )
    client.scripts.post_python3_runs_outputs(
            os.environ['CIVIS_JOB_ID'],
            os.environ['CIVIS_RUN_ID'],
            'JSONValue',
            json_value_object.id
            )


if __name__ == '__main__':
    main()
