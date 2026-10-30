---
doc_id: DOC-008
title: Deployment and Rollback Runbook
version: "2.0"
status: approved
owner: Rohan Iyer
created_at: 2024-09-10T09:00:00Z
last_updated: 2024-11-12T13:00:00Z
authority_score: 0.9
tags: [deployment, rollback, blue-green, runbook]
---

# Deployment and Rollback Runbook (v2.0)

## Strategy
Atlas uses **blue-green deployments** on EKS. The new version is deployed to the idle environment, verified, and then traffic is switched at the load balancer. Rolling updates are no longer used for production.

## Release Steps
1. Deploy the new version to the idle (green) environment.
2. Run the automated smoke test suite.
3. Switch 100 percent of traffic to green.
4. Monitor error rate and p95 latency for 15 minutes.

## Rollback
To roll back, switch traffic back to the previous (blue) environment. The target time to complete a rollback is **under 5 minutes**. The previous environment is kept running for **60 minutes** after cutover so that it is available for rollback.

## Database Changes
Migrations must be backward compatible (expand/contract) because the old and new versions share one database.

## Windows and Approvals
Deployments are allowed Monday to Thursday. Friday deployments are only for approved hotfixes. A release manager must approve each production cutover.
