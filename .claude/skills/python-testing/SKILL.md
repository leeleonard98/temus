---
name: python-testing
description: Python testing patterns with pytest, Factory Boy, async fixtures, and mocking strategies for FastAPI + SQLAlchemy applications.
---

# Python Testing Patterns

Comprehensive testing patterns for Python applications using pytest, Factory Boy, and async fixtures tailored for FastAPI + SQLAlchemy 2.0 async applications.

## When to Activate

- Writing test cases
- Setting up test fixtures
- Creating test factories
- Mocking external dependencies
- Testing async code
- Configuring pytest

## Core Testing Principles

### 1. Tests Should Be Fast and Isolated

Each test should run independently without side effects.

```python
# ✅ GOOD: Independent test with own data
@pytest.mark.asyncio
async def test_create_dataset():
    dataset = DatasetFactory.build()
    created = await repo.create(dataset)
    assert created.id is not None

# ❌ BAD: Tests depend on each other
class TestDatasets:
    async def test_create(self):
        self.dataset_id = await create_dataset()

    async def test_get(self):
        await get_dataset(self.dataset_id)  # Depends on previous test
```

### 2. Test Behavior, Not Implementation

Focus on what the code does, not how it does it.

```python
# ✅ GOOD: Test observable behavior
async def test_create_dataset_returns_entity():
    dataset = await service.create_dataset(file_data, tenant_id, "Test")
    assert dataset.status == DatasetStatus.VALIDATED
    assert dataset.tenant_id == tenant_id

# ❌ BAD: Test internal details
async def test_create_dataset_calls_private_method():
    service._validate_file = Mock()
    await service.create_dataset(file_data, tenant_id, "Test")
    assert service._validate_file.called
```

### 3. Descriptive Test Names

Test names should describe what is being tested and the expected outcome.

```python
# ✅ GOOD: Clear test names
async def test_create_dataset_with_valid_data_returns_201()
async def test_get_dataset_with_invalid_id_returns_404()
async def test_delete_dataset_enforces_tenant_isolation()

# ❌ BAD: Vague test names
async def test_dataset()
async def test_works()
async def test_1()
```

## Factory Boy for Test Data

### Basic Factory Usage

```python
import factory
import uuid
from datetime import datetime
from factory import Factory, LazyAttribute, Sequence

class DatasetFactory(Factory):
    """Factory for creating Dataset instances."""

    class Meta:
        model = Dataset

    id = LazyAttribute(lambda _: uuid.uuid4())
    tenant_id = LazyAttribute(lambda _: uuid.uuid4())
    name = Sequence(lambda n: f"dataset-{n}")
    description = factory.Faker("sentence")
    file_hash = LazyAttribute(lambda _: b"a" * 64)  # SHA-512 hash
    s3_key = Sequence(lambda n: f"tenant/datasets/dataset-{n}.xlsx")
    question_count = 75
    status = DatasetStatus.VALIDATED
    file_size_bytes = 1024000
    created_by = LazyAttribute(lambda _: uuid.uuid4())
    created_at = LazyAttribute(lambda _: datetime.now())
    updated_at = LazyAttribute(lambda _: datetime.now())
    version = 1

# Usage: Build instances without saving to database
def test_dataset_validation():
    dataset = DatasetFactory.build(name="Custom Name")
    assert dataset.name == "Custom Name"
    assert dataset.status == DatasetStatus.VALIDATED

# Override specific attributes
def test_failed_dataset():
    dataset = DatasetFactory.build(
        status=DatasetStatus.FAILED,
        question_count=0
    )
    assert dataset.status == DatasetStatus.FAILED
```

### Factory with SubFactories

```python
class BenchmarkFactory(Factory):
    """Factory for Benchmark with related Dataset."""

    class Meta:
        model = Benchmark

    id = LazyAttribute(lambda _: uuid.uuid4())
    tenant_id = LazyAttribute(lambda _: uuid.uuid4())
    dataset = SubFactory(DatasetFactory)  # Creates related dataset
    status = BenchmarkStatus.PENDING
    created_by = LazyAttribute(lambda _: uuid.uuid4())

# Usage: Creates both benchmark and dataset
def test_benchmark_with_dataset():
    benchmark = BenchmarkFactory.build()
    assert benchmark.dataset is not None
    assert benchmark.dataset.status == DatasetStatus.VALIDATED
```

### Factory Traits for Variants

```python
class DatasetFactory(Factory):
    """Factory with traits for different scenarios."""

    class Meta:
        model = Dataset

    # Base attributes...
    status = DatasetStatus.UPLOADED

    class Params:
        validated = factory.Trait(
            status=DatasetStatus.VALIDATED,
            question_count=75
        )
        failed = factory.Trait(
            status=DatasetStatus.FAILED,
            question_count=0
        )

# Usage
def test_validated_dataset():
    dataset = DatasetFactory.build(validated=True)
    assert dataset.status == DatasetStatus.VALIDATED

def test_failed_dataset():
    dataset = DatasetFactory.build(failed=True)
    assert dataset.status == DatasetStatus.FAILED
```

## Pytest Fixtures

### Async Database Session Fixture

```python
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from testcontainers.postgres import PostgresContainer

@pytest.fixture(scope="session")
def postgres_container():
    """Start PostgreSQL container for tests."""
    with PostgresContainer("postgres:15") as postgres:
        yield postgres

@pytest.fixture
async def async_session(postgres_container):
    """Provide async database session for tests."""
    engine = create_async_engine(
        postgres_container.get_connection_url().replace(
            "postgresql://",
            "postgresql+asyncpg://"
        )
    )

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Provide session
    async_session_maker = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session_maker() as session:
        yield session
        await session.rollback()  # Clean up after test

    await engine.dispose()
```

### Repository Fixture

```python
@pytest.fixture
async def dataset_repo(async_session: AsyncSession):
    """Provide DatasetRepository instance."""
    return DatasetRepository(Dataset, async_session)

# Usage in tests
@pytest.mark.asyncio
async def test_create_dataset(dataset_repo: DatasetRepository):
    dataset = DatasetFactory.build(tenant_id="tenant-123")
    created = await dataset_repo.create(dataset)
    assert created.id is not None
```

### Tenant ID Fixture

```python
@pytest.fixture
def tenant_id():
    """Standard tenant ID for tests."""
    return "tenant-123"

@pytest.fixture
def other_tenant_id():
    """Different tenant ID for isolation tests."""
    return "tenant-456"

# Usage
@pytest.mark.asyncio
async def test_tenant_isolation(
    dataset_repo: DatasetRepository,
    tenant_id: str,
    other_tenant_id: str
):
    # Create dataset for tenant A
    dataset = DatasetFactory.build(tenant_id=tenant_id)
    created = await dataset_repo.create(dataset)

    # Try to access from tenant B
    fetched = await dataset_repo.get_by_id(created.id, other_tenant_id)
    assert fetched is None  # Tenant isolation enforced
```

### FastAPI Test Client Fixture

```python
from httpx import ASGITransport, AsyncClient
from app.main import app

@pytest.fixture
async def client():
    """Provide async HTTP client for FastAPI tests."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        yield client

# Usage
@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
```

## Mocking Patterns

### Mocking External Services with AsyncMock

```python
from unittest.mock import AsyncMock, patch

@pytest.fixture
def mock_s3_client():
    """Mock S3 client for unit tests."""
    client = AsyncMock()
    client.upload_file.return_value = "s3://bucket/tenant/dataset.csv"
    client.generate_presigned_url.return_value = "https://s3.url/presigned"
    client.delete_file.return_value = True
    return client

# Usage in service tests
@pytest.mark.asyncio
async def test_create_dataset_uploads_to_s3(mock_s3_client):
    mock_repo = AsyncMock()
    service = DatasetService(mock_repo, mock_s3_client)

    await service.create_dataset(
        file_data=b"test data",
        tenant_id="tenant-123",
        name="Test Dataset"
    )

    # Verify S3 upload was called
    mock_s3_client.upload_file.assert_called_once()
```

### Mocking Repository Layer

```python
@pytest.fixture
def mock_dataset_repo():
    """Mock DatasetRepository for service tests."""
    repo = AsyncMock()
    repo.create.return_value = DatasetFactory.build(id=uuid.uuid4())
    repo.get_by_id.return_value = DatasetFactory.build(id=uuid.uuid4())
    repo.list.return_value = [DatasetFactory.build() for _ in range(3)]
    return repo

# Usage
@pytest.mark.asyncio
async def test_service_creates_dataset(mock_dataset_repo, mock_s3_client):
    service = DatasetService(mock_dataset_repo, mock_s3_client)

    result = await service.create_dataset(b"data", "tenant-123", "Test")

    mock_dataset_repo.create.assert_called_once()
    assert result.status == DatasetStatus.VALIDATED
```

### Patching Dependencies

```python
@pytest.mark.asyncio
@patch('app.clients.s3_client.S3Client')
async def test_service_with_patched_client(mock_s3_class):
    """Test service with patched S3 client class."""
    mock_instance = AsyncMock()
    mock_s3_class.return_value = mock_instance

    service = DatasetService(mock_repo, mock_instance)
    await service.create_dataset(b"data", "tenant-123", "Test")

    mock_instance.upload_file.assert_called_once()
```

## Parametrized Tests

### Basic Parametrization

```python
@pytest.mark.parametrize(
    "status,expected_count",
    [
        (DatasetStatus.UPLOADED, 2),
        (DatasetStatus.VALIDATED, 1),
        (DatasetStatus.FAILED, 0),
    ],
    ids=["uploaded", "validated", "failed"]
)
@pytest.mark.asyncio
async def test_get_by_status(
    dataset_repo: DatasetRepository,
    status: DatasetStatus,
    expected_count: int
):
    """Test retrieving datasets by different statuses."""
    # Arrange: Create test data
    await dataset_repo.create(DatasetFactory.build(status=DatasetStatus.UPLOADED))
    await dataset_repo.create(DatasetFactory.build(status=DatasetStatus.UPLOADED))
    await dataset_repo.create(DatasetFactory.build(status=DatasetStatus.VALIDATED))

    # Act
    results = await dataset_repo.get_by_status("tenant-123", status)

    # Assert
    assert len(results) == expected_count
```

### Complex Parametrization

```python
@pytest.mark.parametrize(
    "tenant_id,use_correct_tenant,expected_success",
    [
        ("tenant-123", True, True),   # Correct tenant
        ("tenant-123", False, False),  # Wrong tenant (isolation)
    ],
    ids=["correct_tenant", "tenant_isolation"]
)
@pytest.mark.asyncio
async def test_update_with_tenant_isolation(
    dataset_repo: DatasetRepository,
    tenant_id: str,
    use_correct_tenant: bool,
    expected_success: bool
):
    """Test update respects tenant isolation."""
    dataset = DatasetFactory.build(tenant_id=tenant_id)
    created = await dataset_repo.create(dataset)

    update_tenant = tenant_id if use_correct_tenant else "other-tenant"
    success = await dataset_repo.update(
        created.id,
        update_tenant,
        {"name": "Updated"}
    )

    assert success == expected_success
```

## Testing Async Code

### Basic Async Tests

```python
@pytest.mark.asyncio
async def test_async_repository_operation():
    """Test async repository method."""
    repo = DatasetRepository(Dataset, session)
    dataset = DatasetFactory.build()

    created = await repo.create(dataset)

    assert created.id is not None
    assert created.tenant_id == dataset.tenant_id
```

### Testing Concurrent Operations

```python
import asyncio

@pytest.mark.asyncio
async def test_concurrent_creates():
    """Test multiple concurrent creates."""
    repo = DatasetRepository(Dataset, session)
    datasets = [DatasetFactory.build() for _ in range(5)]

    # Create all concurrently
    results = await asyncio.gather(*[
        repo.create(ds) for ds in datasets
    ])

    assert len(results) == 5
    assert all(r.id is not None for r in results)
```

### Testing Timeout Scenarios

```python
import asyncio

@pytest.mark.asyncio
async def test_operation_timeout():
    """Test operation times out appropriately."""
    async def slow_operation():
        await asyncio.sleep(10)
        return "done"

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(slow_operation(), timeout=1.0)
```

## Integration Tests

### Full API Endpoint Test

```python
@pytest.mark.asyncio
async def test_create_dataset_endpoint(client: AsyncClient):
    """Test complete dataset creation flow."""
    # Arrange
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
```

### Testing Error Responses

```python
@pytest.mark.asyncio
async def test_create_dataset_with_invalid_data_returns_400(client: AsyncClient):
    """Test validation error returns 400."""
    files = {"file": ("test.txt", b"invalid data", "text/plain")}
    headers = {"X-Tenant-ID": "tenant-123"}

    response = await client.post(
        "/api/v1/datasets",
        files=files,
        headers=headers
    )

    assert response.status_code == 400
    assert "detail" in response.json()
```

### Testing Tenant Isolation at API Level

```python
@pytest.mark.asyncio
async def test_api_enforces_tenant_isolation(client: AsyncClient):
    """Test datasets are isolated by tenant at API level."""
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

    assert response.status_code == 404  # Not found due to isolation
```

## Best Practices

### Test Organization

```
tests/
├── conftest.py                 # Global fixtures
├── factories.py                # Factory Boy factories
├── unit/                       # Unit tests (isolated, mocked)
│   ├── conftest.py             # Unit test fixtures
│   ├── test_config.py
│   └── services/
│       └── test_dataset_service.py
├── repositories/               # Repository tests (DB required)
│   ├── conftest.py             # DB fixtures
│   ├── test_base_repository.py
│   └── test_dataset_repository.py
└── integration/                # Integration tests (full stack)
    ├── conftest.py             # Client fixtures
    ├── test_api.py
    └── test_dataset_endpoints.py
```

### Arrange-Act-Assert Pattern

```python
@pytest.mark.asyncio
async def test_create_dataset():
    # Arrange: Set up test data and dependencies
    repo = DatasetRepository(Dataset, session)
    dataset = DatasetFactory.build(tenant_id="tenant-123")

    # Act: Execute the operation
    created = await repo.create(dataset)

    # Assert: Verify the outcome
    assert created.id is not None
    assert created.tenant_id == "tenant-123"
    assert created.status == DatasetStatus.VALIDATED
```

### DRY with Fixtures

```python
# Reusable fixture for common setup
@pytest.fixture
async def created_dataset(dataset_repo, tenant_id):
    """Create and return a dataset for tests."""
    dataset = DatasetFactory.build(tenant_id=tenant_id)
    return await dataset_repo.create(dataset)

# Use fixture in multiple tests
@pytest.mark.asyncio
async def test_get_dataset(dataset_repo, created_dataset, tenant_id):
    fetched = await dataset_repo.get_by_id(created_dataset.id, tenant_id)
    assert fetched.id == created_dataset.id

@pytest.mark.asyncio
async def test_update_dataset(dataset_repo, created_dataset, tenant_id):
    success = await dataset_repo.update(
        created_dataset.id,
        tenant_id,
        {"name": "Updated"}
    )
    assert success is True
```

## Quick Reference

| Pattern | Use Case | Example |
|---------|----------|---------|
| Factory Boy | Test data generation | `DatasetFactory.build()` |
| Async Fixtures | Database sessions | `@pytest.fixture async def session()` |
| AsyncMock | Mock async methods | `mock_client = AsyncMock()` |
| Parametrize | Test multiple scenarios | `@pytest.mark.parametrize(...)` |
| Testcontainers | Real database for tests | `PostgresContainer("postgres:15")` |
| Arrange-Act-Assert | Test structure | Standard pattern for clarity |
| Fixtures | Reusable setup | `@pytest.fixture def tenant_id()` |

---

**Remember**: Good tests are fast, isolated, repeatable, and focused on behavior. Use factories for data, fixtures for setup, and mocks for external dependencies. Test what matters to users, not internal implementation details.
