---
doc_id: DOC-004
title: Security and Authentication Guidelines
version: "2.1"
status: approved
owner: Meera Krishnan
created_at: 2024-03-20T09:00:00Z
last_updated: 2025-01-20T16:00:00Z
authority_score: 0.9
tags: [security, jwt, authentication]
---

# Security and Authentication Guidelines (v2.1)

## Token Standard
Atlas uses JSON Web Tokens signed with **RS256**. The auth-service holds the private key. The gateway and all other services verify tokens with the public key only.

## Token Lifetimes
- **Access token: 15 minutes.**
- **Refresh token: 7 days**, with rotation on every use and reuse detection. If a rotated refresh token is presented again, the whole token family is revoked.

## Key Management
Signing keys are stored in AWS Secrets Manager and **rotated every 90 days**. Services must never log token contents.

## Passwords and Secrets
Passwords are hashed with bcrypt (cost factor 12). Secrets must not be committed to source control.

## Transport and Data Protection
All inter-service traffic uses TLS. Personally identifiable information columns are encrypted at rest.
