---
doc_id: DOC-003
title: Atlas Caching Architecture
version: "1.0"
status: approved
owner: Priya Nair
created_at: 2024-04-10T09:30:00Z
last_updated: 2024-04-10T09:30:00Z
authority_score: 0.9
tags: [caching, redis, ttl]
---

# Atlas Caching Architecture (v1.0)

## Pattern
The catalog read path uses a **cache-aside** pattern with Redis. catalog-service reads from Redis first and falls back to PostgreSQL on a miss.

## Key Format
Product entries use the key `catalog:product:{id}`.

## TTL Policy
- Catalog product entries: **300 seconds**.
- Session entries: **1800 seconds**.

## Invalidation
Entries are invalidated by **TTL expiry only**. There is no explicit invalidation when a product is updated.

## Capacity and Eviction
The Redis node is configured with **1 GB** of max memory and the `allkeys-lru` eviction policy.

## Targets
Target cache hit ratio for catalog reads is 80 percent. Target p95 latency for `GET /v2/products` is below 250 ms.
