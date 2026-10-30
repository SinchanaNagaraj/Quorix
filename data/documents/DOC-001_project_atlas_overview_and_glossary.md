---
doc_id: DOC-001
title: Project Atlas Overview and Glossary
version: "1.2"
status: approved
owner: Vikram Shah
created_at: 2024-01-15T09:00:00Z
last_updated: 2025-01-10T11:30:00Z
authority_score: 0.9
tags: [overview, glossary, team]
---

# Project Atlas Overview and Glossary

## Purpose
Atlas is an order and catalog management platform for mid-size retailers. It exposes a REST API that lets retailers publish product catalogs, accept orders, and search products. The pilot launched in April 2024 and general availability followed in September 2024.

## Services
- **api-gateway**: authentication check, rate limiting, request routing.
- **catalog-service**: product catalog reads and writes.
- **order-service**: order creation and order status.
- **auth-service**: issues and refreshes tokens.
- **search-service**: product search backed by OpenSearch.
- **notification-worker**: consumes order events and sends emails/webhooks.

## Technology Summary
Python 3.11 with FastAPI, PostgreSQL, Redis, RabbitMQ, OpenSearch, running on Kubernetes (AWS EKS). The engineering team has six engineers and one engineering manager.

## Glossary
- **TTL**: time to live, the number of seconds a cached value is kept before it expires.
- **p95 latency**: the response time under which 95 percent of requests complete.
- **ADR**: architecture decision record, a short document capturing a design decision and its rationale.
- **Blue-green deployment**: running two production environments and switching traffic between them.
- **Expand/contract migration**: a database change pattern that keeps old and new application versions compatible.
