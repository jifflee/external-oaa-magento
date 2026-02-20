"""
GraphQL Query Definitions — The single query used for B2B data extraction.

This module defines the FULL_EXTRACTION_QUERY, a single GraphQL query named
"VezaExtraction" that retrieves all B2B authorization data in one API call.

The query extracts:
  - customer: The authenticated user's email and name (used as admin reference)
  - company: The B2B company entity with admin info
  - company.structure.items: A flat list of all entities in the company tree,
    each tagged with __typename (Customer or CompanyTeam) and linked by
    parent_id for hierarchy reconstruction

Customer fields extracted:
  - email, firstname, lastname, job_title, telephone, status
  - role: {id, name} — the B2B role assigned to this user
  - team: {id, name, structure_id} — the team this user belongs to

CompanyTeam fields extracted:
  - id, name, description

Note on permissions:
  GraphQL returns role id and name per user, but NOT the per-role ACL
  permission tree (allow/deny for each of the 34 resources). To get explicit
  permissions, the REST role supplement (Step 3 in the pipeline) is needed.

Based on the official Adobe Commerce B2B GraphQL API documentation.

Pipeline context:
  This query is used in Step 2 of the orchestrator pipeline. The response
  is passed to EntityExtractor (Step 4) for parsing.
"""

FULL_EXTRACTION_QUERY = """
query VezaExtraction {
  customer {
    email
    firstname
    lastname
  }
  company {
    id
    name
    legal_name
    email
    company_admin {
      email
      firstname
      lastname
    }
    structure {
      items {
        id
        parent_id
        entity {
          __typename
          ... on Customer {
            email
            firstname
            lastname
            job_title
            telephone
            status
            role {
              id
              name
            }
            team {
              id
              name
              structure_id
            }
          }
          ... on CompanyTeam {
            id
            name
            description
          }
        }
      }
    }
  }
}
"""
