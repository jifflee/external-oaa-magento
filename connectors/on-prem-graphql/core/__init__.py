"""
Core package — The extraction pipeline modules.

This package contains all the modules that implement the 7-step extraction
pipeline. Each module handles one concern:

  orchestrator.py        Pipeline coordination (Steps 1-7)
  magento_client.py      HTTP communication with Magento (Steps 1-3)
  graphql_queries.py     GraphQL query definition (Step 2)
  entity_extractor.py    Parse GraphQL response into entities (Step 4)
  application_builder.py Build OAA CustomApplication structure (Step 5)
  relationship_builder.py Wire entity relationships (Step 6)
"""

from .orchestrator import GraphQLOrchestrator
from .magento_client import MagentoGraphQLClient
from .graphql_queries import FULL_EXTRACTION_QUERY
from .entity_extractor import EntityExtractor, decode_graphql_id
from .application_builder import ApplicationBuilder
from .relationship_builder import RelationshipBuilder
