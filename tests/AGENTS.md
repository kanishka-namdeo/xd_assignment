# Test Suite

## Purpose
Comprehensive test coverage for the Social Support Application system. Three-tier testing strategy: unit tests (mocked dependencies), integration tests (real databases, mocked LLMs), and end-to-end tests (full stack).

## Ownership
- Primary: Development Team
- Review Required: Test changes require review

## Local Contracts

### Test Structure
Mirror `src/` structure in `tests/unit/`:
- `tests/unit/agents/` - Agent logic tests
- `tests/unit/services/` - Service layer tests
- `tests/unit/domain/` - Domain logic tests
- `tests/unit/infrastructure/` - Infrastructure tests

### Test Types
- **Unit tests** (`tests/unit/`): Mock all external dependencies (DB, LLM, vector DB). Fast execution. Test business logic in isolation.
- **Integration tests** (`tests/integration/`): Use real PostgreSQL, Neo4j, Qdrant. Mock LLM calls. Test data access and agent workflows.
- **End-to-end tests** (`tests/e2e/`): Full stack with all services. Test complete application flow from authentication to decision.

### Testing Standards
- Use `pytest` as test runner
- Use `pytest-asyncio` for async tests
- Use `unittest.mock` or `pytest-mock` for mocking
- Use `AsyncMock` for async functions
- Test both success and failure paths
- Aim for >80% coverage on business logic

### Mocking Strategy
- Mock LLM calls (Ollama, StreamLake) in unit and integration tests
- Mock external APIs in unit tests
- Use real databases in integration tests (via Docker Compose)
- Use test fixtures for common data setups

## Work Guidance

### Writing a Unit Test
1. Create test file mirroring source structure (e.g., `tests/unit/services/test_application_service.py`)
2. Mock all dependencies using `pytest-mock` or `unittest.mock`
3. Test business logic in isolation
4. Cover success, failure, and edge cases

### Writing an Integration Test
1. Create test file in `tests/integration/`
2. Use real database connections (ensure Docker services running)
3. Mock LLM calls
4. Test data access patterns and agent workflows
5. Clean up test data after each test

### Writing an E2E Test
1. Create test file in `tests/e2e/`
2. Start all Docker services
3. Test complete flow: authentication → intake → document upload → processing → decision
4. Verify end-to-end data consistency

### Running Tests
```bash
# Unit tests only
.\.venv\Scripts\pytest.exe tests/unit/

# Integration tests (requires Docker)
.\.venv\Scripts\pytest.exe tests/integration/

# All tests
.\.venv\Scripts\pytest.exe tests/

# With coverage
.\.venv\Scripts\pytest.exe tests/ --cov=src --cov-report=html
```

## Verification
- All tests must pass before merge
- Coverage report generated on CI
- No test should depend on external services (except integration tests with Docker)

## Child DOX Index
None - single-level structure.
