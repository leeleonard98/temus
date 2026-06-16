---
name: tdd-workflow
description: Use this skill when writing new features, fixing bugs, or refactoring code. Enforces test-driven development with 80%+ coverage including unit and integration tests.
---

# Test-Driven Development Workflow

This skill ensures all code development follows TDD principles with comprehensive test coverage for the SCC Benchmarking Service (FastAPI + Clean Architecture).

## When to Activate

- Writing new features or functionality
- Fixing bugs or issues
- Refactoring existing code
- Adding API endpoints
- Creating new services or repositories
- Implementing external client integrations

## Core Principles

### 1. Tests BEFORE Code
ALWAYS write tests first, then implement code to make tests pass.

### 2. Coverage Requirements
- Minimum 80% coverage (unit + integration)
- All edge cases covered
- Error scenarios tested
- Boundary conditions verified
- Tenant isolation verified

### 3. Test Types

#### Unit Tests
- Individual functions and utilities
- Service business logic
- Repository methods
- Validators and normalizers
- Client interfaces (mocked)
- Pydantic schemas

#### Integration Tests
- FastAPI endpoints (full request/response)
- Database operations with testcontainers
- External service integrations
- Multi-tenant isolation

## TDD Workflow Steps

### Step 1: Write User Stories
```
As a [role], I want to [action], so that [benefit]

Example:
As a consultant, I want to upload a benchmark dataset,
so that I can evaluate AI performance against my custom documents.
```

### Step 2: Generate Test Cases
For each user story, create comprehensive test cases:

```python
import pytest
from httpx import ASGITransport, AsyncClient

class TestDatasetUpload:
    """Test dataset upload endpoint."""

    @pytest.mark.asyncio
    async def test_upload_valid_dataset_returns_201(self, client: AsyncClient):
        """Upload valid dataset returns 201 with dataset ID."""
        # Test implementation

    @pytest.mark.asyncio
    async def test_upload_duplicate_dataset_returns_400(self, client: AsyncClient):
        """Upload dataset with duplicate name returns 400."""
        # Test edge case

    @pytest.mark.asyncio
    async def test_upload_invalid_format_returns_422(self, client: AsyncClient):
        """Upload invalid file format returns 422."""
        # Test validation error

    @pytest.mark.asyncio
    async def test_upload_enforces_tenant_isolation(self, client: AsyncClient):
        """Dataset only visible to owning tenant."""
        # Test security constraint
```

### Step 3: Run Tests (They Should Fail)
```bash
pytest tests/integration/test_dataset_endpoints.py -v
# Tests should fail - we haven't implemented yet
```

### Step 4: Implement Code
Write minimal code to make tests pass following Clean Architecture:

```python
# app/api/v1/endpoints/datasets.py
from fastapi import APIRouter, Depends, UploadFile
from app.services.dataset_service import DatasetService

router = APIRouter()

@router.post("/datasets", status_code=201)
async def create_dataset(
    file: UploadFile,
    service: DatasetService = Depends(get_dataset_service)
):
    """Upload and validate dataset."""
    return await service.create_dataset(file)
```

### Step 5: Run Tests Again
```bash
pytest tests/integration/test_dataset_endpoints.py -v
# Tests should now pass
```

### Step 6: Refactor
Improve code quality while keeping tests green:
- Remove duplication
- Improve naming
- Optimize performance
- Enhance readability
- Extract reusable logic

### Step 7: Verify Coverage
```bash
pytest --cov=app --cov-report=term-missing
# Verify 80%+ coverage achieved
```

## Testing Patterns for FastAPI + Clean Architecture

### Unit Test Pattern (Pytest + AsyncIO)
```python
import pytest
from unittest.mock import AsyncMock, patch
from app.services.dataset_service import DatasetService
from app.core.enums import DatasetStatus

@pytest.mark.asyncio
class TestDatasetService:
    """Unit tests for DatasetService."""

    async def test_create_dataset_validates_and_stores(self):
        """Create dataset validates file and stores in S3."""
        # Arrange
        mock_repo = AsyncMock()
        mock_s3_client = AsyncMock()
        service = DatasetService(mock_repo, mock_s3_client)

        # Act
        result = await service.create_dataset(
            file_data=b"test,data",
            tenant_id="tenant-123",
            name="Test Dataset"
        )

        # Assert
        assert result.status == DatasetStatus.VALIDATED
        mock_repo.create.assert_called_once()
        mock_s3_client.upload.assert_called_once()

    async def test_create_dataset_rejects_invalid_format(self):
        """Create dataset rejects invalid file format."""
        service = DatasetService(AsyncMock(), AsyncMock())

        with pytest.raises(ValueError, match="Invalid file format"):
            await service.create_dataset(
                file_data=b"<html>not csv</html>",
                tenant_id="tenant-123",
                name="Invalid"
            )
```

### Integration Test Pattern (FastAPI TestClient)
```python
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app

@pytest.mark.asyncio
class TestDatasetEndpoints:
    """Integration tests for dataset API."""

    async def test_create_dataset_full_flow(self):
        """Test complete dataset creation flow."""
        # Arrange
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            files = {"file": ("test.csv", b"Query,Answer\nQ1,A1", "text/csv")}
            headers = {"X-Tenant-ID": "tenant-123"}

            # Act
            response = await client.post(
                "/api/v1/datasets",
                files=files,
                headers=headers
            )

            # Assert
            assert response.status_code == 201
            data = response.json()
            assert data["tenant_id"] == "tenant-123"
            assert data["status"] == "VALIDATED"

    async def test_get_dataset_enforces_tenant_isolation(self):
        """Datasets only accessible by owning tenant."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            # Create dataset for tenant A
            response = await client.post(
                "/api/v1/datasets",
                files={"file": ("test.csv", b"data", "text/csv")},
                headers={"X-Tenant-ID": "tenant-a"}
            )
            dataset_id = response.json()["id"]

            # Try to access from tenant B
            response = await client.get(
                f"/api/v1/datasets/{dataset_id}",
                headers={"X-Tenant-ID": "tenant-b"}
            )

            assert response.status_code == 404  # Not found (isolated)
```

### Repository Test Pattern (Testcontainers)
```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.dataset import DatasetRepository
from app.db.models.dataset import Dataset
from tests.factories import DatasetFactory

@pytest.mark.asyncio
class TestDatasetRepository:
    """Tests for DatasetRepository."""

    @pytest.fixture
    async def dataset_repo(self, async_session: AsyncSession):
        """Create repository instance."""
        return DatasetRepository(Dataset, async_session)

    async def test_create_dataset_persists_to_db(
        self,
        dataset_repo: DatasetRepository
    ):
        """Create dataset persists to database."""
        # Arrange
        dataset = DatasetFactory.build(tenant_id="tenant-123")

        # Act
        created = await dataset_repo.create(dataset)

        # Assert
        assert created.id is not None
        assert created.tenant_id == "tenant-123"

        # Verify persisted
        fetched = await dataset_repo.get_by_id(created.id, "tenant-123")
        assert fetched.id == created.id

    @pytest.mark.parametrize(
        "status,expected_count",
        [
            (DatasetStatus.UPLOADED, 2),
            (DatasetStatus.VALIDATED, 1),
            (DatasetStatus.FAILED, 0),
        ],
    )
    async def test_get_by_status_filters_correctly(
        self,
        dataset_repo: DatasetRepository,
        status: DatasetStatus,
        expected_count: int,
    ):
        """Get by status returns correct datasets."""
        # Arrange: Create test data
        await dataset_repo.create(
            DatasetFactory.build(status=DatasetStatus.UPLOADED)
        )
        await dataset_repo.create(
            DatasetFactory.build(status=DatasetStatus.UPLOADED)
        )
        await dataset_repo.create(
            DatasetFactory.build(status=DatasetStatus.VALIDATED)
        )

        # Act
        results = await dataset_repo.get_by_status("tenant-123", status)

        # Assert
        assert len(results) == expected_count
```

## Test File Organization

```
tests/
├── conftest.py                      # Shared fixtures (DB, client, factories)
├── factories.py                     # Factory Boy model factories
├── unit/                            # Unit tests (isolated, mocked)
│   ├── test_config.py
│   ├── test_logging.py
│   ├── clients/
│   │   ├── test_base_client.py
│   │   └── test_async_base_client.py
│   └── services/
│       └── test_dataset_service.py
├── repositories/                    # Repository tests (DB required)
│   ├── conftest.py                  # DB fixtures (testcontainers)
│   ├── test_base_repository.py
│   ├── test_dataset_repository.py
│   └── test_unit_of_work.py
└── integration/                     # Integration tests (full stack)
    ├── test_api.py                  # Health/root endpoints
    ├── test_database.py             # DB connectivity
    └── test_dataset_endpoints.py    # Dataset API flows
```

## Mocking External Services

### S3 Client Mock
```python
from unittest.mock import AsyncMock

@pytest.fixture
def mock_s3_client():
    """Mock S3 client for unit tests."""
    client = AsyncMock()
    client.upload_file.return_value = "s3://bucket/tenant/dataset.csv"
    client.generate_presigned_url.return_value = "https://s3.url/presigned"
    return client
```

### Database Mock (For Service Tests)
```python
@pytest.fixture
def mock_dataset_repo():
    """Mock DatasetRepository for service tests."""
    repo = AsyncMock()
    repo.create.return_value = DatasetFactory.build(id=1)
    repo.get_by_id.return_value = DatasetFactory.build(id=1)
    return repo
```

### Testcontainers (For Repository Tests)
```python
import pytest
from testcontainers.postgres import PostgresContainer
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

@pytest.fixture(scope="session")
async def postgres_container():
    """Start PostgreSQL container for tests."""
    with PostgresContainer("postgres:15") as postgres:
        yield postgres

@pytest.fixture
async def async_session(postgres_container):
    """Create async database session."""
    engine = create_async_engine(postgres_container.get_connection_url())
    async with AsyncSession(engine) as session:
        yield session
```

## Test Coverage Configuration

### pyproject.toml
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"

[tool.coverage.run]
source = ["app"]
omit = [
    "*/tests/*",
    "*/migrations/*",
    "*/__init__.py",
]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
]
```

## Common Testing Patterns

### Arrange-Act-Assert (AAA)
```python
async def test_create_dataset():
    # Arrange: Set up test data
    service = DatasetService(mock_repo, mock_s3)
    file_data = b"test,data"

    # Act: Execute function
    result = await service.create_dataset(file_data, "tenant-123")

    # Assert: Verify outcome
    assert result.status == DatasetStatus.VALIDATED
    mock_repo.create.assert_called_once()
```

### Parametrized Tests
```python
@pytest.mark.parametrize(
    "status,expected_count",
    [
        (DatasetStatus.UPLOADED, 2),
        (DatasetStatus.VALIDATED, 1),
    ],
)
async def test_get_by_status(status, expected_count):
    results = await repo.get_by_status("tenant-123", status)
    assert len(results) == expected_count
```

### Fixtures for Reusable Setup
```python
@pytest.fixture
async def dataset_repo(async_session):
    """Create repository instance."""
    return DatasetRepository(Dataset, async_session)

@pytest.fixture
def tenant_id():
    """Standard tenant ID for tests."""
    return "tenant-123"
```

## Common Testing Mistakes to Avoid

### ❌ WRONG: Testing Implementation Details
```python
# Don't test private methods
def test_private_method(service):
    assert service._internal_helper() == "value"
```

### ✅ CORRECT: Test Public Interface
```python
# Test public API behavior
async def test_create_dataset_validates_format(service):
    with pytest.raises(ValueError):
        await service.create_dataset(invalid_data, "tenant-123")
```

### ❌ WRONG: Hardcoded Test Data
```python
# Brittle and hard to maintain
dataset = Dataset(id=1, tenant_id="abc", name="Test")
```

### ✅ CORRECT: Use Factories
```python
# Flexible and maintainable
dataset = DatasetFactory.build(tenant_id="tenant-123")
```

### ❌ WRONG: Tests Depend on Each Other
```python
# Tests fail if run in different order
class TestDatasets:
    async def test_create(self):
        self.dataset_id = await create_dataset()

    async def test_get(self):
        await get_dataset(self.dataset_id)  # Depends on previous test
```

### ✅ CORRECT: Independent Tests
```python
# Each test is self-contained
class TestDatasets:
    async def test_create(self):
        dataset = await create_dataset()
        assert dataset.id is not None

    async def test_get(self):
        dataset = await create_dataset()  # Create own data
        fetched = await get_dataset(dataset.id)
        assert fetched.id == dataset.id
```

### ❌ WRONG: Vague Test Names
```python
async def test_dataset():
    # What does this test?
    pass
```

### ✅ CORRECT: Descriptive Test Names
```python
async def test_create_dataset_with_valid_csv_returns_201():
    # Clear what's being tested
    pass
```

## Continuous Testing

### Watch Mode During Development
```bash
pytest --watch
# Tests run automatically on file changes
```

### Run Specific Tests
```bash
# Run single file
pytest tests/unit/test_config.py -v

# Run single test
pytest tests/unit/test_config.py::test_config_defaults -v

# Run tests matching pattern
pytest -k "dataset" -v
```

### Coverage Report
```bash
# Terminal report
pytest --cov=app --cov-report=term-missing

# HTML report
pytest --cov=app --cov-report=html
open htmlcov/index.html
```

## Makefile Commands

```makefile
test:              # Run all tests with coverage
    pytest --cov=app --cov-report=term-missing

test-unit:         # Run unit tests only
    pytest tests/unit/ -v

test-integration:  # Run integration tests
    pytest tests/integration/ -v

test-repos:        # Run repository tests
    pytest tests/repositories/ -v

test-watch:        # Watch mode
    pytest --watch

test-verbose:      # Verbose output
    pytest -vv --tb=short
```

## Best Practices

1. **Write Tests First** - Always TDD, no exceptions
2. **One Assertion Per Test** - Focus on single behavior
3. **Descriptive Test Names** - `test_<action>_<scenario>_<expected_result>`
4. **Arrange-Act-Assert** - Clear test structure
5. **Mock External Dependencies** - Unit tests should be fast
6. **Test Edge Cases** - Null, empty, invalid, boundary values
7. **Test Error Paths** - Not just happy paths
8. **Keep Tests Fast** - Unit tests < 50ms, integration < 1s
9. **Use Fixtures** - DRY principle for test setup
10. **Test Tenant Isolation** - Critical for multi-tenant service
11. **Use Factories** - Generate test data consistently
12. **Async All The Way** - Use `pytest.mark.asyncio` for async code

## Clean Architecture Testing Strategy

### Layer 1: Repository Tests (Data Access)
- Test CRUD operations
- Test tenant isolation
- Test database constraints
- Use testcontainers for real DB
- No business logic

### Layer 2: Service Tests (Business Logic)
- Test business rules
- Test validation logic
- Mock repositories
- Mock external clients
- No database access

### Layer 3: Endpoint Tests (API)
- Test request/response formats
- Test HTTP status codes
- Test authentication/authorization
- Full integration (real DB)
- End-to-end workflows

## Success Metrics

- ✅ 80%+ code coverage achieved
- ✅ All tests passing (green)
- ✅ No skipped or disabled tests
- ✅ Fast test execution (< 30s for unit tests)
- ✅ Integration tests cover critical flows
- ✅ Tests catch bugs before production
- ✅ Tenant isolation verified in all layers

---

**Remember**: Tests are not optional. They are the safety net that enables confident refactoring, rapid development, and production reliability. In Clean Architecture, tests verify each layer independently and together as a system.
