---
doc_id: DOC-007
title: Atlas Configuration Reference
version: "4.2"
status: approved
owner: Rohan Iyer
created_at: 2024-03-15T09:00:00Z
last_updated: 2025-02-18T09:45:00Z
authority_score: 0.9
tags: [configuration, settings, ttl, rate-limit, pool]
---

# Atlas Configuration Reference (v4.2)

Values below describe the production defaults.

## Caching
| Setting | Value |
| --- | --- |
| CATALOG_CACHE_TTL_SECONDS | 600 |
| SESSION_TTL_SECONDS | 1800 |
| REDIS_MAX_MEMORY | 2gb |
| REDIS_EVICTION_POLICY | allkeys-lru |

## Database
| Setting | Value |
| --- | --- |
| DB_POOL_MAX | 40 (per service instance) |
| DB_POOL_TIMEOUT_SECONDS | 30 |

## Gateway
| Setting | Value |
| --- | --- |
| RATE_LIMIT_PER_MIN | 120 |
| RATE_LIMIT_BURST | 20 |
| REQUEST_TIMEOUT_SECONDS | 10 |

## Authentication
| Setting | Value |
| --- | --- |
| JWT_ACCESS_TTL_MIN | 15 |
| JWT_REFRESH_TTL_DAYS | 7 |

## Messaging and Search
| Setting | Value |
| --- | --- |
| RABBITMQ_PREFETCH | 20 |
| SEARCH_BULK_BATCH | 200 |
