"""
GraphQL query definitions for Magento B2B extraction.

Based on official Adobe Commerce B2B GraphQL API documentation.
The VezaExtraction query retrieves all identity and authorization
data in a single API call.
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

# Query to get role permissions tree (optional, used for GraphQL-only permission extraction)
ROLE_PERMISSIONS_QUERY = """
query RolePermissions {
  company {
    structure {
      items {
        entity {
          ... on Customer {
            email
            role {
              id
              name
              permissions {
                id
                text
                sort_order
                children {
                  id
                  text
                  sort_order
                  children {
                    id
                    text
                    sort_order
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
"""
