---
doc_id: DOC-005
title: Atlas Public API Specification
version: "2.3"
status: approved
owner: Aarav Mehta
created_at: 2024-04-02T10:00:00Z
last_updated: 2025-02-14T12:00:00Z
authority_score: 0.9
tags: [api, rest, rate-limit, bulk-import]
---

# Atlas Public API Specification (v2.3)

## Style
The Atlas API is **REST over JSON**. Base path: `/v2`. There is no GraphQL interface.

## Endpoints
- `GET /v2/products` and `GET /v2/products/{id}`
- `POST /v2/orders` and `GET /v2/orders/{id}`
- `POST /v2/products/bulk`: bulk product import, **maximum 500 items per request**.

## Authentication
Send either `Authorization: Bearer <JWT>` or the `X-Atlas-Key` header.

## Rate Limiting
Each API key is limited to **100 requests per minute**, with a burst allowance of 20 additional requests. Exceeding the limit returns HTTP 429 with a `Retry-After` header.

## Pagination
Cursor-based. Default page size 50, maximum 200.

## Data Freshness
Catalog responses may be up to 10 minutes behind the system of record because of caching.

## Errors
Errors use a JSON body with `code`, `message`, and `request_id`.
