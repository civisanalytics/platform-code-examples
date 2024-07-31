# dbt Examples

This directory contains the configuration files, models, and seeds for the dbt (Data Build Tool) project. The dbt project is used to transform raw data into a more usable format for analysis.

## Structure

- [`dbt_project.yml`]( dbt_project.yml ): Main configuration file for the dbt project.
- [`profiles.yml`]( profiles.yml  ): Profiles configuration for dbt, specifying different environments and their settings.
- `models/`: Directory containing SQL models for dbt.
  - `docs.md`: Documentation for the models.
  - [`overview.md`](  ./models/overview.md )): Overview of the dbt project.
  - `schema.yml`: Schema configuration for the models.
  - `staging/`: Directory containing staging models.
    - `stg_customers.sql`: SQL model for staging customers.
    - `stg_orders.sql`: SQL model for staging orders.
    - `stg_payments.sql`: SQL model for staging payments.
- `seeds/`: Directory containing seed files for dbt.

## Configuration

### dbt_project.yml

The [`dbt_project.yml`]( dbt_project.yml )file contains the main configuration for the dbt project, including the project name, version, paths to models, seeds, and other configurations.

### profiles.yml

The [`profiles.yml`]( profiles.yml ) file contains the profiles configuration for dbt, specifying different environments (e.g., development, production) and their settings, such as database credentials and connection details.


## Platform Configuration

When using this example in Civis Platform, you will need to include `dbt` for both `dbt Project Directory` and `dbt Profiles Directory` as highlighted in the screenshot below.

![Civis DBT Screenshot](./civis_dbt_screenshot.png)

When creating a dbt job with your own git repository, if `profiles.yml` and/or `dbt_project.yml` are located at the root of the repository, you can leave these blank.

## Environment Variables

Below is a quick reference of the fundamental environment variables used in the dbt example code, which are provided by Platform when run in that context. For in depth documentation on the topic, please see [our documentation](https://support.civisanalytics.com/hc/en-us/articles/27926077597581-dbt-Scripts).

 For more information on environment variables automatically used by dbt (which can also be specified from Platform), see [dbt's environment variables documentation.](https://docs.getdbt.com/docs/build/environment-variables)


### Shared Environment Variables

The environment variables listed below can be used universally across all database types.

- `DBT_TARGET`: The profiles.yml dbt target
- `DATABASE_TYPE`: The database type.
- `DATABASE_NAME`: The name of the database, e.g. "dev"
- `DBT_SCHEMA`: The schema where dbt will create the output tables. Must be a schema you have ‘create’ permission on.

### PostgreSQL & Redshift

For PostgreSQL and Redshift connections, the following environment variables are required:

- `DATABASE_HOST`: The hostname of the database server.
- `DATABASE_PORT`: The port number on which the database server is listening.
- `DATABASE_USER`: The username to connect to the database.
- `DATABASE_PASSWORD`: The password to connect to the database.

### BigQuery

For BigQuery connections, the following environment variables are required depending on whether you are connecting via a service account json keyfile credential or via an oauth credential

### Shared Environment Variables

- `GCP_AUTH_METHOD`: The BigQuery authentication method. The following examples expect `oauth-secrets` or  `service-account`.
- `GCP_PROJECT_ID`: The Project ID of the Google Cloud Platform BigQuery Project.

#### Service Accounts JSON Keyfile

- `GCP_SERVICE_ACCOUNT_KEYFILE_JSON`: The GCP Service Account JSON Credential Key File.

#### OAuth Credentials

- `GCP_CLIENT_ID`: The GCP OAuth Client ID.
- `GCP_CLIENT_SECRET`: The GCP OAuth Client Secret.
- `GCP_TOKEN_CREDENTIAL_URI`: The GCP token credential uri.
- `DATABASE_PASSWORD`: The GCP OAuth refresh token.
- `GCP_SCOPE`: The GCP scopes required to authenticate.



