# Reference Material

Non-deployable reference documentation and archived code. None of these directories are used in production.

## Contents

| Directory | Purpose |
|-----------|---------|
| `odie-oaa/` | Generic CSV-to-Veza OAA connector. Reference implementation for building custom OAA integrations. Not Magento-specific. |
| `commerce-webapi/` | Adobe Commerce REST and GraphQL API documentation (Gatsby site). B2B endpoint reference, schema types, authentication docs. |
| `legacy/graphql-connector/` | Original standalone GraphQL connector. Superseded by `connectors/on-prem-graphql/` and `connectors/cloud-graphql/`. |
| `legacy/rest-connector/` | Original standalone REST connector. Superseded by `connectors/on-prem-rest/` and `connectors/cloud-rest/`. |

## Legacy Connectors

The `legacy/` subdirectory contains the original standalone connectors that were superseded by the refactored versions in `connectors/`. The new connectors use a shared library (`shared/magento_oaa_shared`) to eliminate code duplication for Veza client operations, output management, permissions, and preflight checks.

Do not use these for new deployments. They are kept for reference and migration context.
