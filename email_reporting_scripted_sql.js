
// This script is an example of how to transform the results of SQL queries in Markdown for email reporting.
// Both values and tables can both be transformed to Markdown for email reporting.


// Step 1: Update the query you wish to deliver in an email report (value, table, or both)

//// Value example (swap out query for your own):
var number = queryToVariable("SELECT max(amount) FROM reporting.donations");

//// Table example (swap out query for your own):
var table = query("SELECT * FROM reporting.donations;")
var mdTable = toMarkdownTable(table)


// Step 2: Add the markdown to the body of your email notifications.

//// If you wish to add a value in-line, simply add it in-line in the email body:
//// Our largest donation this week was {{number}}.

//// If you wish to add a table, you'll need to add a line break before and after the table:
//// Here is a summary of all donations:
////
//// {{mdTable}}
////


// Step 3: Run the job/schedule the job/receive your email reports.



//// ****



// Functions below will not require editing, but need to be included in the script
function queryToVariable(qtext){
  var result = query(qtext);
  
// checks length of query result, returns query or error message
  if(result.length == 1) {
    var propname = Object.getOwnPropertyNames(result[0]);
    var output = result[0][propname];
  } else if (result.length == 0) {
    var output = "Error! query returned nothing.";
  } else if (result.length > 1) {
    var output = "Error! query returned more than 1 value.";
  } else {
    var output = "Error!";
  }
  return output;
}

function queryToMarkdownTable(qtext){
  var result = query(qtext);
  if(result.length == 0){
    return("Error! query returned nothing.");
  } else {
    return toMarkdownTable(query(qtext));
  }
}

// adapted from https://source.opennews.org/en-US/articles/introducing-sheetdown/
// converts a SQL query to markdown
function toMarkdownTable(data) {
    var table = '|'
    var headers = Object.keys(data[0])
    var underHeaders = ''
    headers.map(function(key) {
        table += key + '|'
        underHeaders += ' ------ |'
    })
 
    table += '\n|' + underHeaders + '\n'
    data.map(function(row) {
      var values = headers.map(function(h) { return row[h] })
      table += '|' + values.join('|') + '|\n'
    })
    return table
}