# ai-city

Order automation for dropshipping stores. The project accepts Shopify order webhooks, sources supplier offers, routes purchase orders, tracks fulfillment, and records order and audit data in SQLite.

## Run Locally

Requires Python 3.12 or newer.

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
mkdir -p data
set -a
. ./.env
set +a
```

Set `SHOPIFY_WEBHOOK_SECRET` before receiving real webhooks. Configure `SHOPIFY_STORE_ID`, `TENANT_ID`, `DATABASE_PATH`, and `MOCK_SUPPLIER_CATALOG` as needed. `ANTHROPIC_API_KEY` and `ANTHROPIC_MODEL` are only used when drafting support replies. The default app uses a development webhook secret and an in-memory database; do not use those defaults in production.

Start the API:

```sh
python -m uvicorn api.main:app --reload
```

The API provides `GET /health`, `POST /webhooks/shopify`, `GET /orders`, and `GET /audit`. Run the end-to-end mock supplier demo with:

```sh
python scripts/demo_loop.py
```

Run tests and byte-compile the project with:

```sh
python -m compileall -q .
python -m unittest discover -s tests -v
```

## Docker

After setting the desired environment variables (or using the development defaults), start the API with:

```sh
docker compose up --build
```

The service listens on port `8000` and stores its SQLite database under the mounted `data/` directory.

## Layout

```text
adapters/       Shopify, mock store, and mock supplier integrations
agents/         Guarded agent tools and Anthropic reply drafting
api/            FastAPI application and webhook endpoints
core/           Order models, state machine, pricing, events, SQLite repository
scripts/        Runnable demos
services/       Sourcing, order workflow, inventory synchronization
tests/          Standard-library unittest suites
```

## Real vs TODO

| Capability | Current state |
| --- | --- |
| Shopify webhook HMAC verification and order parsing | Implemented |
| Order validation, sourcing, rerouting, idempotency, and status audit | Implemented |
| Mock supplier ordering, stock decrement, tracking, and mock store updates | Implemented |
| SQLite order and audit persistence | Implemented |
| Price guardrails and refund approval classification | Implemented; refunds do not call a payment provider |
| Support reply drafting | Implemented through Anthropic when configured; drafts only, never sent automatically |
| Shopify inventory, price, and fulfillment API calls | TODO in the Shopify adapter |
| Production supplier integrations and payment/refund execution | TODO |
| Staging and production deployment commands | TODO in the deployment workflow |
