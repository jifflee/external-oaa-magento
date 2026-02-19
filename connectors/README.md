# Connectors

Active connectors for extracting B2B authorization data from self-hosted Adobe Commerce / Magento and pushing to Veza.

Commerce Cloud connectors are in `backlog/` pending environment setup.

## Choose Your Connector

| Your Setup | GraphQL Available? | Use This |
|------------|--------------------|----------|
| Self-hosted / On-Prem | Yes | `on-prem-graphql/` (recommended) |
| Self-hosted / On-Prem | No | `on-prem-rest/` |
| Commerce Cloud | -- | See `backlog/cloud-graphql/` and `backlog/cloud-rest/` |

### GraphQL vs REST

- **GraphQL** (recommended) — 1-2 API calls, complete user-role resolution, full user profiles.
- **REST** (fallback) — 5-7+ API calls, no user-role resolution without a gap strategy, only authenticated user has a full profile.

## Shared Library

All connectors depend on `shared/magento_oaa_shared`. Install it first:

```bash
cd ../shared && pip install -e .
```

This is also handled automatically by each connector's `requirements.txt`.

## Running

```bash
cd <connector-directory>
pip install -r requirements.txt
cp .env.template .env
# Edit .env

python run.py --dry-run    # Test extraction
python run.py --push       # Push to Veza
```
