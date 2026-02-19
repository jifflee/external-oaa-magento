# Backlog

Connectors and components that are not yet ready for development or testing. These are parked here until prerequisites are met.

| Directory | Blocker | Prerequisite |
|-----------|---------|-------------|
| `cloud-graphql/` | No Commerce Cloud environment, no Adobe IMS credentials | Adobe Commerce Cloud instance + IMS OAuth client_id/secret |
| `cloud-rest/` | No Commerce Cloud environment, no Adobe IMS credentials | Adobe Commerce Cloud instance + IMS OAuth client_id/secret |

## When to Promote

Move a connector back to `connectors/` once its prerequisites are satisfied. The code is complete and tested — it just needs an environment to run against.
