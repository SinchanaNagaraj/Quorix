"""Domain vocabulary and entity mapping for Query Analysis.

Decouples dataset-specific terms, aliases, and technical keywords from generic
query analysis and classification logic. Supports customizable domain configuration.
"""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class DomainVocabulary(BaseModel):
    """Configurable domain vocabulary for entity recognition and semantic expansion."""

    known_entities: list[str] = Field(
        default_factory=lambda: [
            "Redis",
            "PostgreSQL",
            "Postgres",
            "RabbitMQ",
            "Kafka",
            "FastAPI",
            "React",
            "Docker",
            "ElastiCache",
            "Amazon RDS",
            "Amazon MQ",
            "TTL",
            "p95",
            "JWT",
            "API",
            "caching",
            "authentication",
            "catalog",
            "tokens",
            "access token",
            "refresh token",
            "database",
            "worker",
            "runbook",
            "dead-letter queue",
            "DLQ",
            "idempotency",
            "audit event",
            "pull request",
            "PR",
        ]
    )

    entity_aliases: dict[str, str] = Field(
        default_factory=lambda: {
            "postgres": "PostgreSQL",
            "postgresql": "PostgreSQL",
            "rds": "Amazon RDS",
            "elasticache": "ElastiCache",
            "mq": "RabbitMQ",
            "amazon mq": "Amazon MQ",
            "jwt": "JWT",
            "auth": "authentication",
            "db": "database",
            "cache": "caching",
            "dlq": "dead-letter queue",
            "pr": "pull request",
            "token": "tokens",
            "login": "authentication",
        }
    )

    technical_synonyms: dict[str, list[str]] = Field(
        default_factory=lambda: {
            "authentication": ["auth", "login", "jwt", "token", "credentials", "session", "access token", "refresh token"],
            "database": ["db", "postgres", "postgresql", "sql", "rds", "schema", "tables"],
            "caching": ["cache", "redis", "ttl", "in-memory", "elasticache"],
            "messaging": ["queue", "rabbitmq", "kafka", "mq", "broker", "dlq", "dead-letter queue"],
            "troubleshooting": ["timeout", "error", "outage", "bug", "incident", "latency", "failure", "fix", "issue"],
            "configuration": ["config", "ttl", "setting", "parameter", "env", "port", "lifetime"],
            "architecture": ["design", "overview", "system", "components", "service"],
        }
    )

    intent_keywords: dict[str, list[str]] = Field(
        default_factory=lambda: {
            "config": ["ttl", "config", "configuration", "lifetime", "setting", "port", "env"],
            "troubleshoot": ["timeout", "fix", "issue", "bug", "outage", "error", "incident", "failure", "crash"],
            "architecture": ["architecture", "explain", "design", "how does", "overview", "system structure"],
            "historical": ["why was", "why did", "originally", "initial", "historical", "previously", "deprecated", "past", "earlier", "reason"],
            "comparative": ["compare", "difference", "change over time", "changed over time", "old and new", "vs", "versus", "how has"],
        }
    )

    stop_words: set[str] = Field(
        default_factory=lambda: {
            "a", "an", "the", "and", "or", "but", "if", "then", "else", "when",
            "at", "by", "for", "with", "about", "against", "between", "into",
            "through", "during", "before", "after", "above", "below", "to", "from",
            "up", "down", "in", "out", "on", "off", "over", "under", "again",
            "further", "then", "once", "here", "there", "all", "any", "both",
            "each", "few", "more", "most", "other", "some", "such", "no", "nor",
            "not", "only", "own", "same", "so", "than", "too", "very", "can",
            "will", "just", "don", "should", "now", "what", "which", "who", "whom",
            "this", "that", "these", "those", "am", "is", "are", "was", "were",
            "be", "been", "being", "have", "has", "had", "having", "do", "does",
            "did", "doing", "would", "could", "why", "how", "tell", "me", "something",
        }
    )


# Default singleton instance
DEFAULT_VOCABULARY = DomainVocabulary()


def get_default_vocabulary() -> DomainVocabulary:
    return DEFAULT_VOCABULARY
