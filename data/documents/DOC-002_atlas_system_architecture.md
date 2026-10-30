---
doc_id: DOC-002
title: Atlas System Architecture
version: "3.0"
status: approved
owner: Aarav Mehta
created_at: 2024-02-01T10:00:00Z
last_updated: 2024-12-05T14:20:00Z
authority_score: 0.9
tags: [architecture, components, data-flow]
---

# Atlas System Architecture (v3.0)

## Overview
Client requests enter through the **api-gateway**, which verifies JWT signatures using the auth-service public key (RS256) and applies per-key rate limiting. Requests are then routed to catalog-service, order-service, or search-service.

## Data Stores
- **PostgreSQL 16** on Amazon RDS: one primary and one read replica. It is the source of truth for products, orders, and customers.
- **Redis 7** on Amazon ElastiCache: a cache-aside layer for catalog reads and the session store. Caching details are described in the Caching Architecture document.
- **OpenSearch 2.11**: product search index, updated incrementally from catalog events.

## Messaging
Order and catalog events are published to RabbitMQ 3.12 (Amazon MQ). Events include `order.created` and `catalog.updated`. The messaging technology choice is recorded in ADR-003.

## Deployment
Services run as containers on AWS EKS and are released using blue-green deployments (see the Deployment and Rollback Runbook).

## Data Flow: Catalog Read
1. Gateway authenticates the request and checks the rate limit.
2. catalog-service checks Redis for `catalog:product:{id}`.
3. On a miss, it reads from PostgreSQL and writes the result back to Redis.
