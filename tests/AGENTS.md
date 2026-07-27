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

### API and Utility Test Files
- `tests/unit/api/test_health.py` — 146 lines: Health check endpoint tests
- `tests/unit/utils/test_state_size.py` — 102 lines: State size estimation/monitoring tests
- `tests/unit/utils/test_circuit_breaker.py` — Circuit breaker pattern tests
- `tests/unit/utils/test_error_classifier.py` — Error classification tests

### Agent Test Files
The following agent test suites cover the core LangGraph agents:

- `tests/unit/agents/test_orchestrator.py` — 51 tests covering phase routing, authentication, intake, document collection, processing, decision, and enablement flows
- `tests/unit/agents/test_extraction.py` — 26 tests covering tool invocation, gate integration, output parsing, and multi-document extraction
- `tests/unit/agents/test_validation.py` — 29 tests covering per-document validation, cross-document comparison, discrepancy classification, clarification generation, confidence scoring, reflexion loop, and gate 2 integration
- `tests/unit/agents/test_eligibility.py` — 27 tests covering feature engineering, ML prediction, factor adjustment, and gate 3 integration
- `tests/unit/agents/test_decision.py` — 39 tests covering decision logic, explanation generation, enablement packaging, formatting, routing, ReAct node behavior, and deterministic synthesis
- `tests/unit/agents/test_checkpointer.py` — 10 tests covering shared checkpointer factory, singleton pattern, and TTL cleanup task
- `tests/unit/agents/test_state.py` — 8 tests covering state reducers for list fields
- `tests/unit/agents/test_graph_caching.py` — 2 tests covering graph compilation caching for extraction and eligibility
- `tests/unit/agents/test_review_state_mutation.py` — State mutation review tests

### Domain Test Files
- `tests/unit/domain/test_emirates_id.py` — 9 tests covering Emirates ID generation and validation

### Gate Test Files
Deterministic validation gates are tested separately under `tests/unit/agents/gates/`:
- `test_completeness.py` — 9 tests covering document completeness validation
- `test_document_integrity.py` — 22 tests covering tamper/forgery detection gates
- `test_eligibility_rules.py` — 15 tests covering hard eligibility rule gates
- `test_retry_logic.py` — 12 tests covering retry and fallback behavior

### Integration and E2E Test Files
- `tests/integration/test_orchestrator_integration.py` — 4 integration tests covering full phase flow and resume-from-later-phase scenarios
- `tests/integration/test_agent_workflows.py` — Agent workflow integration tests (stub)
- `tests/integration/test_api.py` — API layer integration tests (stub)
- `tests/integration/test_repositories.py` — Repository integration tests (stub)
- `tests/integration/test_live_integration.py` — Live agent graph integration tests: structural buildability (15 non-live) + full graph execution with real LLM (6 live, marked `@pytest.mark.live`)
- `tests/e2e/test_full_application_flow.py` — End-to-end tests covering the complete applicant pipeline with synthetic data
- `tests/e2e/test_application_flow.py` — Application flow E2E tests
- `tests/e2e/test_full_pipeline_e2e.py` — Full pipeline E2E tests
- `tests/system/test_eligibility_e2e.py` — Eligibility-specific system-level E2E tests

### Ad-hoc Test Scripts
Root-level test scripts (not part of the formal test suite):
- `tests/live_test.py` — Live system testing
- `tests/db_layer_test.py` — Database layer testing
- `tests/live_api_test.py` — Live API testing

### Test Fixtures
Shared fixtures in `tests/conftest.py`:
- `synthetic_profiles` — Collection of synthetic applicant profiles for testing
- `approved_profile` — Profile expected to result in approval
- `manual_review_profile` — Profile expected to result in manual review
- `soft_decline_profile` — Profile expected to result in soft decline
- `sample_extracted_data` — Pre-built extracted document data for replay tests
- `sample_state` — Pre-populated LangGraph state for node-level tests
- `streamlake_settings` — LangChain settings configured for StreamLake LLM provider
- `mock_chat_openai` — Mocked ChatOpenAI instance for unit tests

### Test Types
- **Unit tests** (`tests/unit/`): Mock all external dependencies (DB, LLM, vector DB). Fast execution. Test business logic in isolation.
- **Integration tests** (`tests/integration/`): Use real PostgreSQL, Neo4j, Qdrant. Mock LLM calls. Test data access and agent workflows.
- **End-to-end tests** (`tests/e2e/`): Full stack with all services. Test complete application flow from authentication to decision.

### Testing Standards
Testing patterns (pytest, async testing, mocking strategies, evaluation tests) are defined in `.cursor/rules/testing.mdc`. Key conventions:
- Use `pytest` as test runner with `pytest-asyncio` for async tests
- Use `unittest.mock` or `pytest-mock` with `AsyncMock`
- Mock LLM layer; test everything around it
- Aim for >80% coverage on business logic

### Mocking Strategy
- Mock LLM calls (Ollama, StreamLake) in unit and integration tests
- Mock external APIs in unit tests
- Use real databases in integration tests (via Docker Compose)
- Use test fixtures for common data setups

**Extraction test patches**: Infrastructure tools (`PDFParser`, `OCREngine`, `TableExtractor`, `ResumeParser`) are patched at their import location in `src.infrastructure.document_processing.*`, not at `src.agents.extraction.tools.*` (since imports are local within the tool functions).

**Decision agent patches**: The decision agent is obtained via `get_decision_agent()` factory function. Tests patch `src.agents.decision.graph.get_decision_agent` with `return_value=mock_agent` rather than patching a module-level singleton.

**Service-layer patches**: `AuthService.login` and `ChatService.handle_chat` are the patch targets for API-level tests, replacing the previous pattern of patching repositories directly in route handlers.

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
- Current test coverage: ~241+ unit tests across agents, gates, and domain

## Child DOX Index
None - single-level structure.
