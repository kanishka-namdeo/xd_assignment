# ADR 0002: Polyglot Persistence (PostgreSQL + Neo4j + Qdrant)

## Status

Accepted

## Context

The UAE Social Support Application handles multiple data shapes:
- Relational data: applicants, applications, documents, extraction results (ACID compliance required for financial/identity data)
- Graph data: document lineage (which extraction came from which document version), family relationships across applications
- Vector data: document embeddings for similarity search, duplicate detection, semantic search

A single database would force one data model to fit all shapes, resulting in complex queries and poor performance.

## Decision

Use three databases, each optimized for its data shape:

1. **PostgreSQL** — Primary data store for applicants, applications, documents, extraction results. 16-table schema with strict referential integrity, JSONB for state snapshots, Alembic migrations.

2. **Neo4j** — Graph database for document lineage and family relationships. Cypher queries for transitive relationships are orders of magnitude simpler than recursive SQL. Used sparingly — only for lineage and family graphs, not primary data.

3. **Qdrant** — Vector database for document embeddings. HNSW indexing for similarity search. Local embeddings via Ollama, stored in Qdrant for self-hosted deployment parity.

## Alternatives Considered

### PostgreSQL Only (pgvector, recursive CTEs)

pgvector provides vector search but with inferior HNSW performance compared to Qdrant. Recursive CTEs for graph queries are verbose and slow compared to Cypher. Would couple all data access to a single database, creating a bottleneck.

### MongoDB (Document Store)

Schemaless design conflicts with the strict validation requirements for financial/identity data. No native graph or vector capabilities.

### Single Cloud Provider (AWS RDS + Neptune + OpenSearch)

Violates the local-first deployment requirement. Government PII cannot egress to third-party cloud by default.

## Consequences

### Positive
- Each database is optimized for its data shape
- Independent scaling per database
- Clear separation of concerns

### Negative
- Three databases to manage, monitor, and back up
- Cross-database transactions not possible (eventual consistency for graph/vector updates)
- Higher infrastructure complexity

### Risks
- Data consistency between PostgreSQL and Neo4j/Qdrant (mitigated by updating graph/vector stores as post-commit hooks, not in the same transaction)
