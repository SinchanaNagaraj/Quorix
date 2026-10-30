---
doc_id: DOC-010
title: Database Schema and Migration Guide
version: "2.0"
status: approved
owner: Priya Nair
created_at: 2024-03-01T09:00:00Z
last_updated: 2024-10-28T10:00:00Z
authority_score: 0.9
tags: [database, postgresql, migrations, backup]
---

# Database Schema and Migration Guide (v2.0)

## Engine
Atlas runs **PostgreSQL 16** on Amazon RDS. The database was upgraded from PostgreSQL 14 in October 2024.

## Core Tables
`products`, `orders`, `order_items`, `customers`, `api_keys`.

## Migrations
Schema changes are managed with Alembic and follow the expand/contract pattern: add new structures first, migrate data, and remove old structures in a later release.

## Connection Pooling
Each service instance maintains an application-level pool of up to **40** connections.

## Read Replica
One read replica serves reporting queries. Transactional reads and writes use the primary.

## Backups
Automated daily snapshots are retained for 30 days. Point-in-time recovery is available for the last 7 days.
