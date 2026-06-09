# Python 실전 가이드: 견고한 코드를 위한 Best Practices

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-stable-brightgreen)

> 이 문서는 프로덕션 환경에서 Python 코드를 작성할 때 고려해야 할 핵심 원칙들을 정리한 실전 가이드입니다. 이론보다 실무에서 바로 적용할 수 있는 패턴과 예시를 중심으로 구성했습니다.

---

## 1. 프로젝트 구조

### 1.1 표준 레이아웃

잘 설계된 Python 프로젝트는 일관된 디렉토리 구조를 가집니다. `src` 레이아웃은 패키지를 의도치 않게 임포트하는 실수를 방지하고, 설치된 패키지와 개발 중인 패키지를 명확히 구분합니다.

```
my_project/
├── src/
│   └── my_package/
│       ├── __init__.py
│       ├── core.py
│       └── utils.py
├── tests/
│   ├── __init__.py
│   ├── test_core.py
│   └── conftest.py
├── docs/
├── pyproject.toml
├── README.md
└── .gitignore
```

### 1.2 pyproject.toml 설정

`setup.py`는 더 이상 권장되지 않습니다. 모든 프로젝트 메타데이터는 `pyproject.toml`에 선언합니다.

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "my-package"
version = "0.1.0"
description = "A well-structured Python package"
requires-python = ">=3.11"
dependencies = [
    "pydantic>=2.0",
    "httpx>=0.25",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "ruff>=0.1",
    "mypy>=1.0",
]

[tool.ruff]
line-length = 88
target-version = "py311"

[tool.mypy]
python_version = "3.11"
strict = true
```

---

## 2. 타입 힌트와 Pydantic

### 2.1 모든 공개 API에 타입 힌트 사용

타입 힌트는 문서이자 버그 방지망입니다. 특히 함수 시그니처에는 반드시 적용합니다.

```python
from __future__ import annotations

from typing import Sequence


def process_items(
    items: Sequence[str],
    max_count: int = 100,
    *,
    strict: bool = False,
) -> list[str]:
    """Process and filter items.

    Args:
        items: Input sequence to process.
        max_count: Maximum items to return.
        strict: Raise on invalid items when True.

    Returns:
        Filtered list of processed items.
    """
    result: list[str] = []
    for item in items:
        if not item.strip():
            if strict:
                raise ValueError(f"Empty item: {item!r}")
            continue
        result.append(item.strip().lower())
        if len(result) >= max_count:
            break
    return result
```

### 2.2 Pydantic v2 데이터 모델

Pydantic v2는 런타임 유효성 검사와 직렬화를 동시에 처리합니다. `dataclass` 대신 복잡한 도메인 객체에 사용하세요.

```python
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class Priority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Task(BaseModel):
    id: int
    title: str = Field(min_length=1, max_length=200)
    priority: Priority = Priority.MEDIUM
    due_date: datetime | None = None
    tags: list[str] = Field(default_factory=list)

    @field_validator("title")
    @classmethod
    def normalise_title(cls, v: str) -> str:
        return v.strip()

    @field_validator("tags")
    @classmethod
    def lowercase_tags(cls, v: list[str]) -> list[str]:
        return [tag.lower().strip() for tag in v if tag.strip()]
```

---

## 3. 에러 처리

### 3.1 커스텀 예외 계층

예외 계층을 설계할 때는 도메인별로 묶고, 최상위 베이스 예외를 두어 라이브러리 사용자가 한 번에 잡을 수 있게 합니다.

```python
class AppError(Exception):
    """Base exception for all application errors."""

    def __init__(self, message: str, *, code: str = "UNKNOWN") -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def __repr__(self) -> str:
        return f"{type(self).__name__}(code={self.code!r}, message={self.message!r})"


class ValidationError(AppError):
    """Raised when input validation fails."""

    def __init__(self, message: str, field: str | None = None) -> None:
        super().__init__(message, code="VALIDATION_ERROR")
        self.field = field


class NotFoundError(AppError):
    """Raised when a requested resource does not exist."""

    def __init__(self, resource: str, identifier: str | int) -> None:
        super().__init__(
            f"{resource} not found: {identifier!r}",
            code="NOT_FOUND",
        )
        self.resource = resource
        self.identifier = identifier
```

### 3.2 컨텍스트 매니저로 리소스 보호

파일, DB 연결, 네트워크 소켓 등 모든 리소스는 `with` 블록으로 감쌉니다.

```python
from contextlib import contextmanager
from pathlib import Path
from typing import Generator
import tempfile


@contextmanager
def atomic_write(path: Path) -> Generator[Path, None, None]:
    """Write to a temp file and rename atomically on success."""
    tmp = Path(tempfile.mktemp(dir=path.parent, suffix=".tmp"))
    try:
        yield tmp
        tmp.replace(path)   # atomic on POSIX; near-atomic on Windows
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


# Usage
with atomic_write(Path("output.json")) as tmp:
    tmp.write_text('{"status": "ok"}')
```

---

## 4. 비동기 프로그래밍

### 4.1 asyncio 기초 패턴

비동기 I/O는 CPU-bound 작업이 아닌 네트워크/디스크 I/O에 적합합니다. `asyncio.gather`로 독립적인 I/O 작업을 병렬 실행합니다.

```python
import asyncio
import httpx
from typing import Any


async def fetch_all(urls: list[str], timeout: float = 10.0) -> list[dict[str, Any]]:
    """Fetch multiple URLs concurrently."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        tasks = [client.get(url) for url in urls]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

    results: list[dict[str, Any]] = []
    for url, resp in zip(urls, responses):
        if isinstance(resp, Exception):
            results.append({"url": url, "error": str(resp), "data": None})
        else:
            results.append({"url": url, "error": None, "data": resp.json()})
    return results
```

### 4.2 백그라운드 태스크와 취소

```python
import asyncio
import signal


async def worker(name: str, queue: asyncio.Queue[str]) -> None:
    while True:
        item = await queue.get()
        try:
            await asyncio.sleep(0.1)  # simulate work
            print(f"[{name}] processed: {item}")
        finally:
            queue.task_done()


async def main() -> None:
    queue: asyncio.Queue[str] = asyncio.Queue()

    workers = [
        asyncio.create_task(worker(f"w{i}", queue))
        for i in range(4)
    ]

    for i in range(20):
        await queue.put(f"item-{i}")

    await queue.join()

    for w in workers:
        w.cancel()
    await asyncio.gather(*workers, return_exceptions=True)
```

---

## 5. 테스트 전략

### 5.1 pytest 구성

| 항목 | 권장 설정 | 이유 |
|---|---|---|
| `testpaths` | `["tests"]` | 명시적 범위 지정 |
| `addopts` | `-ra -q --tb=short` | 간결한 출력 |
| `asyncio_mode` | `"auto"` | async 테스트 자동 처리 |
| `filterwarnings` | `"error"` | 경고를 에러로 처리 |

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra -q --tb=short"
asyncio_mode = "auto"
filterwarnings = ["error"]
```

### 5.2 Fixture 설계

```python
import pytest
from pathlib import Path


@pytest.fixture(scope="session")
def tmp_workspace(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Session-scoped workspace directory."""
    return tmp_path_factory.mktemp("workspace")


@pytest.fixture
def sample_task() -> dict:
    return {
        "id": 1,
        "title": "  Write tests  ",
        "priority": "high",
        "tags": ["Python", "TDD", ""],
    }


class TestTask:
    def test_title_is_stripped(self, sample_task: dict) -> None:
        task = Task(**sample_task)
        assert task.title == "Write tests"

    def test_tags_are_lowercased(self, sample_task: dict) -> None:
        task = Task(**sample_task)
        assert task.tags == ["python", "tdd"]

    def test_empty_tags_are_removed(self, sample_task: dict) -> None:
        task = Task(**sample_task)
        assert "" not in task.tags
```

### 5.3 커버리지 목표

프로젝트 성숙도에 따른 현실적 커버리지 목표:

| 단계 | 커버리지 | 설명 |
|---|---|---|
| 초기 개발 | 60–70% | 핵심 로직 위주 |
| 베타 | 75–85% | 주요 경로 전체 |
| 프로덕션 | 85–95% | 에러 경로 포함 |
| 라이브러리 | 95%+ | 공개 API 전체 |

```bash
pytest --cov=src --cov-report=html --cov-fail-under=80
```

---

## 6. 로깅과 관찰 가능성

### 6.1 structlog 활용

표준 `logging` 대신 구조화 로그를 사용하면 검색과 집계가 훨씬 쉬워집니다.

```python
import structlog

logger = structlog.get_logger()


def process_order(order_id: str, user_id: int) -> None:
    log = logger.bind(order_id=order_id, user_id=user_id)
    log.info("order.processing_started")

    try:
        # ... business logic ...
        log.info("order.processing_completed", duration_ms=42)
    except Exception as exc:
        log.error("order.processing_failed", error=str(exc), exc_info=True)
        raise
```

### 6.2 OpenTelemetry 트레이싱

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

provider = TracerProvider()
provider.add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint="http://localhost:4317"))
)
trace.set_tracer_provider(provider)

tracer = trace.get_tracer(__name__)


def handle_request(request_id: str) -> str:
    with tracer.start_as_current_span("handle_request") as span:
        span.set_attribute("request.id", request_id)
        result = do_work(request_id)
        span.set_attribute("result.size", len(result))
        return result
```

---

## 7. 의존성 관리

### 7.1 uv 사용

`uv`는 Rust 기반의 초고속 패키지 매니저입니다. `pip`보다 10–100배 빠릅니다.

```bash
# 가상환경 생성
uv venv .venv

# 의존성 설치
uv pip install -e ".[dev]"

# lockfile 생성
uv pip compile pyproject.toml -o requirements.lock

# 도구 실행 (설치 없이)
uvx ruff check src/
uvx mypy src/
```

### 7.2 의존성 그룹

| 그룹 | 패키지 예시 | 용도 |
|---|---|---|
| 기본 | `pydantic`, `httpx`, `structlog` | 프로덕션 런타임 |
| dev | `pytest`, `ruff`, `mypy` | 로컬 개발 |
| docs | `mkdocs`, `mkdocstrings` | 문서 생성 |
| ci | `coverage`, `pytest-cov` | CI 파이프라인 |

---

## 8. CI/CD 파이프라인

### 8.1 GitHub Actions 예시

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]

    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v1
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: uv pip install -e ".[dev]"

      - name: Lint
        run: |
          uvx ruff check src/ tests/
          uvx ruff format --check src/ tests/

      - name: Type check
        run: uvx mypy src/

      - name: Test
        run: pytest --cov=src --cov-fail-under=80
```

### 8.2 릴리스 자동화

| 단계 | 도구 | 작업 |
|---|---|---|
| 버전 범프 | `bump2version` | 태그 생성 |
| 빌드 | `hatchling` | wheel/sdist |
| 퍼블리시 | `twine` / GitHub Actions | PyPI 업로드 |
| 변경 이력 | `git-cliff` | CHANGELOG 자동 생성 |

---

## 9. 보안 고려사항

### 9.1 환경 변수와 시크릿

```python
import os
from functools import lru_cache
from pydantic import SecretStr
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    secret_key: SecretStr
    debug: bool = False
    allowed_hosts: list[str] = ["localhost"]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

### 9.2 SQL Injection 방지

절대로 f-string이나 `.format()`으로 SQL을 만들지 않습니다.

```python
# ❌ 위험
query = f"SELECT * FROM users WHERE name = '{user_input}'"

# ✅ 안전 — parameterised query
query = "SELECT * FROM users WHERE name = ?"
cursor.execute(query, (user_input,))
```

---

## 10. 요약

Python 실전 개발에서 가장 중요한 원칙들을 다시 한 번 정리합니다.

| 원칙 | 핵심 메시지 |
|---|---|
| 구조 | `src` 레이아웃, `pyproject.toml` 단일 진실 |
| 타입 | 모든 공개 API에 타입 힌트, Pydantic으로 유효성 검사 |
| 에러 | 도메인별 커스텀 예외 계층, 리소스는 항상 컨텍스트 매니저 |
| 비동기 | I/O 병렬화에 `asyncio.gather`, 취소 처리 명시 |
| 테스트 | fixture 재사용, 커버리지 85%+ 목표 |
| 로깅 | 구조화 로그, 트레이싱 연동 |
| 의존성 | `uv`로 빠른 관리, 그룹별 분리 |
| 보안 | 시크릿은 환경변수, SQL은 파라미터화 |

> **한 줄 요약**: 명시적이고, 테스트 가능하며, 읽기 쉬운 코드가 빠른 코드보다 낫다.
