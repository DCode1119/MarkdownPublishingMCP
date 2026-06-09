# 요구사항 정의서

- **Revision**: 0.5
- **Last Updated**: 2026-06-09
- **Status**: Draft → Refined (Round 4)

## 1. 프로젝트 개요

**프로젝트명**: md-publishing-mcp (MarkdownPublishingMCP)

Markdown을 입력으로 받아 출판/보고서 수준의 A4 PDF 문서를 조판하는 MCP(Model Context Protocol) 서버.

단순한 Markdown→PDF 변환기가 아닌, 중간 표현(IR)을 거쳐 조판 규칙을 적용하는 **문서 조판 시스템**을 목표로 한다.

### 1.1 지원 범위 (v1.0 목표)

| 항목 | 기준 |
|---|---|
| 최대 페이지 | 200p (권장), 500p (허용, 성능 저하 가능) |
| 렌더링 시간 | A4 10p < 5초 / 100p < 30초 / 200p < 60초 |
| 이미지 포함 | 50개 이하 권장, 100개까지 허용 |
| 메모리 사용 | 200p 기준 < 512MB |
| 동시 요청 | 3개 (기본), 설정 가능 |
| 지원 문서 유형 | ADR, 설계서, 보고서, 제안서, 기술문서 (5종) |
| 지원 기능 | 표, 코드블록(구문 강조), 이미지(내장/참조/외부URL), 각주, 목차, 머리글/바닥글 |

## 2. 배경 및 동기

MD → PDF 생성에서 A4 레이아웃, 문단 제어, 페이지 나눔, 머리글/바닥글, 목차, 각주, 표, 코드블록까지 제대로 관리하려면 단순 변환기로는 한계가 있다.

### 비교: 변환기 vs 조판 시스템

| 구분 | 단순 변환 | 문서 조판 MCP |
|---|---|---|
| 기본 스타일 | 적용 | 적용 |
| 페이지 여백 | 설정 가능 | 설정 가능 |
| 긴 표/코드블록/이미지 배치 | 불안정 | 정규화/자동 배치 |
| 문단/장/페이지 제어 | 약함 | 엄격한 규칙 적용 |
| 구조 처리 | Markdown → PDF 직접 | MD → AST → IR → Typst AST → PDF |

## 3. 기술 스택 검토

백엔드 엔진 후보 세 가지를 검토함:

| 방식 | 품질 | 문서 레이아웃 제어 | 난이도 | 추천도 |
|---|---|---|---|---|
| Pandoc + Typst | 매우 높음 | 매우 강력 | 중간 | ★★★★★ |
| Pandoc + LaTeX | 최고 | 최고 | 높음 | ★★★★ |
| Markdown + HTML + Paged.js/WeasyPrint | 높음 | CSS 기반 | 중간 | ★★★ |

**결정: Pandoc + Typst**

Typst는 원래 PDF 조판 엔진으로 설계되어 A4 문서 품질이 매우 뛰어나고, LaTeX보다 유지보수가 쉬우며 PDF 생성 속도가 빠르다.

### 3.1 선정 근거 및 알려진 한계

#### Typst 장점
- Python 바인딩(`typst` 패키지)을 통한 네이티브 호출 가능 (CLI 우회)
- LaTeX 대비 간결한 문법, 빠른 컴파일 속도
- 적극적인 개발 진행 중

#### 알려진 한계 (v0.11 기준)
- **Pandoc Typst writer**: 표 셀 병합, 일부 특수 문자에서 알려진 이슈 존재. GitHub `jgm/pandoc` Typst writer 이슈 트래킹 필수
- **Breaking changes**: Typst v0.11에서 다수 호환성 변경 있음. v0.12 대비 고정 버전 정책 필요
- **패키지 생태계**: LaTeX 대비 매우 작음. Typst Universe 패키지 의존 시 버전 고정 필요
- **한국어 조판**: Noto Sans KR 등 한글 폰트는 정상 동작 확인됨. 한글/한자 혼합 문서는 사전 검증 필요
- **긴 문서 안정성**: 500p 이상에서 메모리 사용량 선형 증가 확인. 스트리밍 렌더링 불가

#### 대응 전략
- Typst 버전 고정: `typst-compile` 실행 시 `--font-path`로 폰트 명시 지정
- CI에서 Typst 버전별 호환성 테스트 매트릭스 운영
- Pandoc Typst writer 버그 발생 시 --to typst 대신 IR→Typst 직접 생성 코드로 우회 가능 (Layer 3)

## 4. 대상 문서 유형

**v1.0 단일 포맷 전략**: 하나의 "A4 리포트 포맷"을 기본으로 하고, 문서 유형별 차이는 Typst show rules 변수 세트로만 처리한다.

| 유형 | 기본 템플릿 | 차별점 |
|---|---|---|
| ADR | `default` | 제목+날짜+상태 헤더, 경량 |
| 설계서 | `default` | 목차 자동 포함 |
| 보고서 | `default` | 표지 페이지+요약문 |
| 제안서 | `default` | 표지+목차+부록 |
| 기술문서 | `default` | 코드블록 강조, 목차 |

v1.0에서 지원하는 유형은 ADR·설계서·보고서·제안서·기술문서 5종이며, API 문서·게임 기획서·계약서는 향후 고려한다.

각 유형은 `template_vars.document_type` 값만 다르며, Typst 템플릿 내에서 `if document_type == "report"` 방식으로 분기 처리한다. 유형별 전용 템플릿 파일이 필요한 경우 v2.0에서 고려.

## 5. 핵심 요구사항

### 5.1 페이지 레이아웃
- A4 기본 지원
- 여백 설정 (상/하/좌/우 각각 설정 가능)
- 가로(Landscape) 모드 지원 (표/코드블록 자동 전환)
- 페이지 크기 커스터마이징

### 5.2 문단/단락 제어
- 문단 간격 정밀 제어 (strict mode)
- Widow/Orphan(외톨이 줄) 방지
- 제목과 본문 연결 유지 (keep-with-next)
- 단락 구분 스타일 지정

### 5.3 페이지 나눔
- 챕터 시작 시 새 페이지
- 표 페이지 넘김 자동 분할
- 코드블록 페이지 분할 방지 (avoid-page-break)
- 큰 표 Landscape 전환 (fit-or-landscape)
- 이미지 자동 리사이즈

### 5.4 머리글/바닥글
- 페이지 번호
- 문서 제목
- 섹션명 표시
- 커스텀 헤더/푸터

### 5.5 목차 (Table of Contents)
- 자동 생성
- 페이지 번호 매핑
- 섹션 깊이 제어 (section_depth)

### 5.6 각주 (Footnotes)
- Markdown 각주 → Typst footnote 변환
- 페이지 하단 배치

### 5.7 표 (Tables)
- 페이지 넘김 자동 분할
- 큰 표 Landscape 전환 정책
- 표 스타일링 (테두리, 배경, 정렬)

### 5.8 코드블록
- 페이지 분할 방지
- 구문 강조 (Syntax Highlighting)
- 언어별 스타일 지정

### 5.9 템플릿 시스템
- 단일 기본 템플릿 (v1.0)
- 템플릿 변수 시스템 (아래 10장 참조)
- 확장 가능한 템플릿 구조 (v2.0)

## 6. 제안 아키텍처

```
User (MCP Client)
  │
  │  "이 Markdown을 A4 보고서로 변환해줘"
  ▼
MCP Server (Python)
  │
  ├─ Layer 1: Markdown Parser
  │   mdast → AST 노드 추출
  │   (markdown-it-py 또는 mistune)
  │
  ├─ Layer 2: Document IR
  │   AST → 정규화된 중간 표현
  │   → 조판 규칙 적용
  │   → 페이지/문단 정규화
  │
  ├─ Layer 3: Typst Generator
  │   IR → Typst AST → .typ 파일
  │   + 템플릿 오버레이
  │
  └─ Layer 4: PDF Renderer
      typst compile → PDF 반환
      (Python typst 패키지 또는 CLI)
```

### 데이터 흐름

```
Input Markdown
  │
  ▼
[Layer 1] Markdown Parser
  │  mdast (JSON AST)
  ▼
[Layer 2] Document IR Builder
  │
  ├─ Step 2a: IR 정규화 — mdast → DocumentIR 구조 변환
  │
  └─ Step 2b: Composition Engine — 조판 규칙 적용 → 페이지/문단 배치 정규화
  │  (Layer 2 내부 하위 단계, 출력은 동일 DocumentIR 구조)
  ▼
[Layer 3] Typst Generator
  │  .typ source
  ▼
[Layer 4] PDF Renderer
  │  PDF bytes
  ▼
Output PDF
```

## 7. Layer 간 인터페이스 규약

### 7.1 Layer 0→1: 입력 검증

MCP 요청이 들어오면 **가장 먼저** 다음 검증을 수행한다:

```python
MAX_INPUT_SIZE = 10 * 1024 * 1024  # 10MB

async def validate_input(markdown: str, params: dict) -> InputValidationResult:
    # 1. 크기 검증 (스트리밍 카운트)
    if len(markdown.encode("utf-8")) > MAX_INPUT_SIZE:
        return InputValidationResult(
            valid=False,
            error=McpError(code="TOO_LARGE", message=f"Input exceeds {MAX_INPUT_SIZE//1024//1024}MB")
        )

    # 2. 필수 파라미터 검증
    if not markdown or not markdown.strip():
        return InputValidationResult(
            valid=False,
            error=McpError(code="VALIDATION_ERROR", message="Markdown content is required")
        )

    # 3. 이미지 경로 보안 검증 (Path Traversal 방지)
    image_refs = re.findall(r'!\[.*?\]\((.+?)\)', markdown)
    for ref in image_refs:
        if ".." in ref or ref.startswith("/") or ref.startswith("~"):
            return InputValidationResult(
                valid=False,
                error=McpError(
                    code="VALIDATION_ERROR",
                    message=f"Path traversal detected in image reference: {ref}",
                    details={"violation": "path_traversal", "ref": ref}
                )
            )

    # 4. 허용된 URL 체계만 통과 (이미지)
    for ref in image_refs:
        if ref.startswith(("http://", "https://", "data:")):
            continue
        # 상대 경로는 허용하되, 프로젝트 디렉토리 내부로 제한
        normalized = os.path.normpath(ref)
        if normalized.startswith("..") or os.path.isabs(normalized):
            return InputValidationResult(
                valid=False,
                error=McpError(code="VALIDATION_ERROR", message=f"Invalid image path: {ref}")
            )

    # 5. 링크 URL 보안 검증 (javascript:, file: 프로토콜 차단)
    link_refs = re.findall(r'\[.*?\]\((.+?)\)', markdown)
    for ref in link_refs:
        if ref.startswith(("javascript:", "file:", "data:")):
            return InputValidationResult(
                valid=False,
                error=McpError(
                    code="VALIDATION_ERROR",
                    message=f"Disallowed URL protocol in link: {ref.split(':')[0]}://",
                    details={"violation": "disallowed_protocol", "ref": ref[:100]}
                )
            )
        # Path Traversal 검증 (이미지와 동일 기준)
        if ".." in ref or ref.startswith("/") or ref.startswith("~"):
            return InputValidationResult(
                valid=False,
                error=McpError(
                    code="VALIDATION_ERROR",
                    message=f"Path traversal detected in link reference: {ref}",
                    details={"violation": "path_traversal", "ref": ref}
                )
            )

    return InputValidationResult(valid=True)
```

**Path Traversal 방지 정책:**
- `../` 포함된 이미지 경로 → 거절됨
- 절대 경로(`/etc/passwd`, `C:\Windows\...`) → 거절됨
- 외부 URL(`https://`) → 허용 (v1.0에서는 다운로드 후 캐시)
- data:URI → 이미지에서만 허용, 링크에서는 거절
- 상대 경로(`images/diagram.png`) → 허용, 작업 디렉토리 기준으로 해석
- 링크 URL(`[text](url)`)에서 `javascript:`, `file:`, `data:` 프로토콜 → 거절됨

### 7.2 Layer 1→2: IR 검증 (Validation Layer)

Layer 1이 생성한 IR이 스키마를 완전히 만족하는지 **Layer 2 진입 전에 검증**한다. 이는 버그가 있는 Markdown 파서가 잘못된 IR을 생성했을 때 Layer 3까지 전파되어 진단 불가능한 Typst 에러가 발생하는 것을 방지한다.

```python
from pydantic import BaseModel, Field, ValidationError
from typing import Literal

class SectionModel(BaseModel):
    heading: str = Field(min_length=0)
    level: int = Field(ge=1, le=6)
    blocks: list["BlockModel"]
    children: list["SectionModel"]

class ImageModel(BaseModel):
    src: str = Field(min_length=1)
    alt: str = ""
    width: float | None = Field(default=None, ge=1.0)  # 1mm 미만 불가
    caption: str | None = None
    placement: Literal["inline", "block", "float"] = "block"

class TableModel(BaseModel):
    headers: list[list["InlineModel"]] = Field(min_length=1)
    rows: list[list[list["InlineModel"]]]
    caption: str | None = None
    alignment: list[Literal["left", "center", "right"]] = Field(default_factory=list, min_length=1)

class CodeBlockModel(BaseModel):
    code: str = Field(min_length=0)
    language: str | None = None
    show_line_numbers: bool = Field(default=False)  # 기본값: 줄번호 미표시

class ListBlockModel(BaseModel):
    items: list[list["BlockModel"]] = Field(min_length=1)
    ordered: bool = False
    start: int | None = Field(default=None)  # ordered=False 시 무시됨

class InlineModel(BaseModel):
    type: Literal["text", "bold", "italic", "code", "link", "image"]
    text: str = Field(default="", min_length=0)
    url: str | None = None  # link/image 타입에서 사용
    alt: str | None = None  # image 타입에서 사용

def validate_ir(ir: DocumentIR) -> ValidationReport:
    """IR 스키마 적합성 검증 + 안전성 검사"""
    try:
        # 구조 검증
        model = DocumentIRModel.from_orm(ir)

        # 추가 안전성 검사
        warnings = []
        for section in ir.sections:
            _check_section_depth(section, warnings, max_depth=10)

        return ValidationReport(valid=True, warnings=warnings)
    except ValidationError as e:
        return ValidationReport(valid=False, errors=e.errors())
```

**검증 항목:**
- Section.level: 1-6 범위 (0이나 7+ → `VALIDATION_ERROR`)
- Image.width: 1mm 이상 또는 None (0이나 음수 → `VALIDATION_ERROR`)
- Table.headers: 최소 1개 열 필요 (빈 리스트 → `VALIDATION_ERROR`)
- Table.alignment: 열 개수와 일치해야 함
- 중첩 Section 깊이: 최대 10레벨 제한 (무한 재귀 방지)
- 각 Block/Inline 타입의 필수 필드 존재 여부

## 8. 중간 표현 (IR) 스키마

Layer 2→3 간의 인터페이스를 정의하는 **프로젝트 핵심 데이터 모델**. Python 코드로 먼저 정의되며, 7.2의 Pydantic 모델과 함께 Layer 2와 3의 인터페이스를 고정시킨다.

### 8.1 IR 설계 원칙

1. **정규화**: 모든 Markdown 입력이 동일한 IR 구조로 정규화된다. 입력 형식의 차이가 Layer 2 이후에 영향을 주지 않음.
2. **불변성**: IR은 일단 생성되면 변경되지 않는다. 조판 규칙은 IR을 읽어서 새로운 IR을 생성한다 (transform pipeline).
3. **Inline vs Block 분리**: Inline 요소(굵게, 기울임, 코드, 링크)와 Block 요소(문단, 코드블록, 표)는 명확히 분리된다.
4. **확장성**: 새 Block/Inline 타입 추가 시 다른 타입에 영향을 주지 않음.

## 9. MCP 도구 인터페이스 및 에러 명세

### 9.1 도구 목록

| 도구 | 설명 | 주요 파라미터 |
|---|---|---|
| `render` | MD → PDF 즉시 변환 (기본 템플릿) | `markdown`, `paper`, `margin` |
| `render_with_template` | 템플릿 지정 변환 | `markdown`, `template`, `variables` |
| `preview` | 특정 페이지 미리보기 (render_id 기반 캐시 사용) | `render_id`, `page` |

### 9.2 공통 응답 스키마

모든 도구는 다음 통합 응답 포맷을 사용한다:

```python
@dataclass
class McpSuccessResponse:
    success: Literal[True]
    data: RenderResult | PreviewResult

@dataclass
class McpErrorResponse:
    success: Literal[False]
    error: McpError

@dataclass
class McpError:
    code: str           # 표준화된 에러 코드
    message: str        # 사람이 읽을 수 있는 메시지
    details: dict | None  # 추가 컨텍스트 (선택)

@dataclass
class RenderResult:
    pdf: bytes
    pages: int
    render_id: str   # preview 등 후속 작업에 사용
    warnings: list[str]

@dataclass
class PreviewResult:
    page: int
    total_pages: int
    pdf: bytes  # 해당 페이지 1장만 포함
    warnings: list[str]
```

### 9.3 표준 에러 코드

| 코드 | HTTP 유사 | 발생 조건 |
|---|---|---|
| `DEPENDENCY_ERROR` | 503 | Typst/Pandoc 미설치 또는 버전 불일치 |
| `PARSE_ERROR` | 400 | Markdown 파싱 실패 (구문 오류) |
| `VALIDATION_ERROR` | 422 | 요청 파라미터 검증 실패 (필수값 누락, 범위 초과) |
| `RENDER_ERROR` | 500 | Typst 조판/컴파일 실패 |
| `TIMEOUT` | 504 | 렌더링 시간 초과 (기본 120초) |
| `TOO_LARGE` | 413 | 입력 크기 제한 초과 (기본 10MB) |
| `TEMPLATE_ERROR` | 422 | 템플릿 변수 불일치 또는 템플릿 파일 누락 |
| `CACHE_MISS` | 404 | 요청한 render_id의 캐시를 찾을 수 없음 (만료 또는 유효하지 않은 ID) |
| `INTERNAL_ERROR` | 500 | 예상치 못한 내부 오류 (버그) |

### 9.4 요청 예시

```json
// render 도구 호출
{
  "markdown": "# Hello\n\nThis is a test document.",
  "paper": "a4",
  "margin": { "top": 20, "bottom": 20, "left": 25, "right": 25 }
}

// 성공 응답
{
  "success": true,
  "data": {
    "pdf": "<base64 encoded bytes>",
    "pages": 3,
    "warnings": ["Image 'chart.png' not found — skipped"]
  }
}

// 실패 응답
{
  "success": false,
  "error": {
    "code": "DEPENDENCY_ERROR",
    "message": "Typst CLI not found. Install with: https://github.com/typst/typst/releases",
    "details": { "missing": ["typst"], "version_required": ">=0.11" }
  }
}
```

### 9.5 렌더링 시간 제한

| 파라미터 | 기본값 | 최대값 |
|---|---|---|
| `timeout` | 120초 | 600초 |
| `max_pages` | 200 | 500 |
| `max_input_size` | 10MB | 50MB |

### 9.6 Timeout 및 부분 실패 처리

| 조건 | 동작 |
|---|---|
| timeout 초과 | `TIMEOUT` 에러 반환. 부분 PDF는 반환하지 않음 (완전 실패) |
| 렌더링 중 Typst 크래시 | `RENDER_ERROR` 반환. 재시도 정책 없음 (입력 문제일 가능성) |
| 1페이지 렌더링 성공 후 10페이지에서 실패 | 전체 실패로 처리. 부분 결과 반환하지 않음 |
| 연속 3회 동일 입력 실패 | `DEPENDENCY_ERROR` 반환 (Typst 프로세스 자체 문제로 간주) |

**원칙:** PDF는 항상 완전한 문서여야 한다. 부분 PDF를 반환하지 않는다.

### 9.7 Preview 시스템 (캐시 기반)

preview는 **이전 render 결과의 캐시**에서 특정 페이지 PDF를 추출한다.
render와 달리 Typst 재컴파일이 발생하지 않는다.

**워크플로:**
1. `render(markdown)` → 전체 문서 렌더링 + 캐시 저장 → `render_id` 반환
2. `preview(render_id, page)` → 캐시에서 PDF 로드 → 지정 페이지 추출 → 1페이지 PDF 반환

**캐시 정책:**
- TTL: 10분 (마지막 접근 기준)
- 최대 캐시 개수: 20개 (LRU eviction)
- 서버 재시작 시 캐시 초기화
- preview 호출은 캐시 TTL을 갱신함 (keep-alive)

```python
RENDER_CACHE: dict[str, CacheEntry] = {}
CACHE_TTL = 600  # 10분
MAX_CACHED = 20

@dataclass
class CacheEntry:
    render_id: str
    pdf: bytes
    pages: int
    created_at: float
    last_access: float

def cache_render_result(render_id: str, pdf: bytes, pages: int) -> None:
    """render 결과를 캐시에 저장 (LRU eviction)"""
    if len(RENDER_CACHE) >= MAX_CACHED:
        oldest = min(RENDER_CACHE.items(), key=lambda x: x[1].last_access)
        del RENDER_CACHE[oldest[0]]
    
    now = time.time()
    RENDER_CACHE[render_id] = CacheEntry(
        render_id=render_id, pdf=pdf, pages=pages,
        created_at=now, last_access=now
    )

def get_preview(render_id: str, page: int) -> PreviewResult:
    """캐시에서 특정 페이지 추출"""
    entry = RENDER_CACHE.get(render_id)
    if entry is None:
        raise McpError(
            code="CACHE_MISS",
            message=f"Render ID '{render_id}' not found in cache (expired or invalid)"
        )
    
    if page < 1 or page > entry.pages:
        raise McpError(
            code="VALIDATION_ERROR",
            message=f"Page {page} out of range. Document has {entry.pages} pages."
        )
    
    # TTL 갱신
    entry.last_access = time.time()
    
    # 특정 페이지 추출 (PyMuPDF 등으로 구현)
    page_pdf = extract_page(entry.pdf, page)
    
    return PreviewResult(
        page=page, total_pages=entry.pages,
        pdf=page_pdf, warnings=[]
    )
```

> **참고:** `extract_page()`의 구체적 구현은 PDF 조작 라이브러리(PyMuPDF/pypdf)에 의존한다. v1.0에서는 `render` 사용 권장, preview 성능 최적화는 v1.1 목표.

### 9.8 동시 요청 관리

MCP 서버는 Typst 렌더링에 **세마포어 기반 동시성 제어**를 적용한다:

```python
import asyncio
import tempfile
from pathlib import Path

class RenderPool:
    def __init__(self, max_concurrent: int = 3):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.active_tasks: dict[str, asyncio.Task] = {}
        self.temp_dir = Path(tempfile.mkdtemp(prefix="mdpub_"))
        self._counter = 0

    async def render(self, request_id: str, typst_source: str) -> RenderResult:
        """Typst 소스(.typ)를 컴파일하여 PDF 반환"""
        async with self.semaphore:
            task = asyncio.create_task(
                self._compile_typst(typst_source, request_id)
            )
            self.active_tasks[request_id] = task
            try:
                return await asyncio.wait_for(task, timeout=120.0)
            except asyncio.TimeoutError:
                raise McpError(code="TIMEOUT")
            except Exception:
                raise McpError(code="RENDER_ERROR")
            finally:
                self.active_tasks.pop(request_id, None)

    async def _compile_typst(self, source: str, request_id: str) -> RenderResult:
        """임시 .typ 파일 생성 → Typst compile → 정리"""
        typst_path = self.temp_dir / f"{request_id}.typ"
        output_path = typst_path.with_suffix(".pdf")
        
        try:
            typst_path.write_text(source, encoding="utf-8")
            renderer = TypstRenderer()
            pdf_bytes = await renderer.compile(str(typst_path), output_path)
            pages = _count_pdf_pages(pdf_bytes)
            self._counter += 1
            render_id = f"r{int(time.time())}_{self._counter}"
            
            # 캐시 등록
            cache_render_result(render_id, pdf_bytes, pages)
            
            return RenderResult(pdf=pdf_bytes, pages=pages, render_id=render_id, warnings=[])
        finally:
            import os as _os
            if not _os.environ.get("MDPUB_DEBUG"):
                typst_path.unlink(missing_ok=True)
                output_path.unlink(missing_ok=True)
```

**리소스 제한 정책:**
- 동시 Typst compile: 최대 3개 (기본)
- 추가 요청은 큐에서 대기 (Semaphore 대기)
- 각 Typst compile은 별도 서브프로세스로 실행됨
- 메모리: 각 compile에 256MB limit (서브프로세스 수준)
- 3개 동시 실행 시 총 ~1.5GB 메모리 사용 예상 (Typst 자체 메모리 포함)

**임시 파일 관리:**
- RenderPool 생성 시 전용 temp 디렉토리 생성 (`mkdtemp`)
- 각 요청: `{temp_dir}/{request_id}.typ` + `.pdf` 파일 생성 후 compile
- `finally` 블록에서 즉시 정리 (`MDPUB_DEBUG` 환경변수 설정 시 유지)
- RenderPool 소멸 시 temp 디렉토리 전체 정리

## 10. 템플릿 변수 시스템

Typst 템플릿이 수신하는 컨텍스트는 단일 JSON 객체로 고정된다:

```json
{
  "document_type": "report",
  "title": "문서 제목",
  "subtitle": "부제 (선택)",
  "author": "작성자",
  "date": "2026-06-09",
  "language": "ko",
  "toc": [
    { "title": "서론", "level": 1 },
    { "title": "배경", "level": 1 },
    { "title": "구현", "level": 2 }
  ],
  "custom": {}
}
```

### 10.1 변수 정의

| 변수 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `document_type` | string | yes | `adr` / `design` / `report` / `proposal` / `tech` |
| `title` | string | yes | 문서 제목 |
| `subtitle` | string | no | 부제 |
| `author` | string | yes | 작성자명 |
| `date` | string | yes | 작성일 (ISO 8601) |
| `language` | string | yes | `ko` 또는 `en` |
| `toc` | array | no | 목차 항목 배열 |
| `custom` | object | no | 사용자 정의 변수 (템플릿에서 자유롭게 사용) |

### 10.2 Typst 템플릿 구조

```typst
// template.typ
#let context = json.decode(sys.inputs.text)

// --- Null-safe 기본값 처리 ---
#let doc_type = context.at("document_type", default: "report")
#let title = context.at("title", default: "Untitled")
#let subtitle = context.at("subtitle", default: none)
#let author = context.at("author", default: "Unknown")
#let date = context.at("date", default: datetime.today())
#let language = context.at("language", default: "ko")
#let toc = context.at("toc", default: ())

// --- 문서 유형별 분기 ---
#if doc_type == "report" {
  // 보고서 레이아웃
} else if doc_type == "adr" {
  // ADR 레이아웃
} else {
  // 기본 레이아웃
}

// --- Subtitle 조건부 렌더링 ---
#if subtitle != none {
  v(0.5em)
  text(subtitle, size: 14pt, weight: "light")
}

// --- 목차 조건부 렌더링 ---
#if toc.len() > 0 {
  pagebreak()
  heading("Table of Contents", level: 1)
  list(toc.map(entry => entry.title))
}
```

**None 처리 규칙:**
- optional 변수(`subtitle`, `toc`, `custom`): Typst 템플릿에서 `at(..., default: none)`으로 수신
- `none`인 경우 조건부 렌더링 생략 (Typst의 `#if`로 분기)
- Generator(Layer 3)는 JSON 직렬화 시 None을 JSON null로 변환
- Generator는 절대 template context에서 필수 키를 생략하지 않음

### 10.3 충돌 정책

- 내장 변수(`title`, `author`, `date`, `document_type` 등)는 `custom` 객체로 오버라이드할 수 없음
- 사용자 정의 변수는 `custom` 아래에만 추가 가능
- 충돌 발생 시 명시적 오류 반환 (`TEMPLATE_ERROR`)

### 10.4 템플릿 합성 방식 (Layer 3 → .typ 생성)

Layer 3는 DocumentIR을 Typst 코드로 변환하고, 템플릿과 합성하여 완전한 `.typ` 파일을 생성한다.

**v1.0 단일 파일 방식:**
Layer 3가 생성하는 `.typ` 파일은 템플릿 프리앰블과 IR 변환 본문이 **하나의 파일**에 순차적으로 포함된다:

```typst
// === 템플릿 프리앰블 (show rules, 레이아웃 설정) ===
#let context = json.decode(sys.inputs.text)
#set page(paper: "a4", margin: (top: 20mm, bottom: 20mm, left: 25mm, right: 25mm))
#show heading.where(level: 1): it => [ #block(spacing: 0.5em, it) ]

// === 문서 본문 (IR → Typst 변환 결과) ===
= 제목
본문 내용...
#figure(
  caption: [...],
  image("diagram.png", width: 80%),
)
```

**합성 규칙:**
1. Layer 3는 먼저 템플릿 프리앰블을 생성한다 (show rules, page 설정, 변수 바인딩)
2. 그 다음 IR의 각 Block/Inline 요소를 Typst 코드로 변환하여 본문을 생성한다
3. 변환 순서: Section heading → Block(문단/표/코드블록/이미지) → Inline(굵게/기울임/링크/코드)

**render_with_template 동작:**
- 사용자가 제공한 템플릿 파일이 Layer 3의 기본 프리앰블을 대체한다
- 사용자 템플릿이 `#include "body.typ"` 방식으로 IR 변환 결과를 참조한다고 가정한다
- 템플릿 변수 검증은 Layer 2 입력 검증 단계에서 수행됨 (7.1 참조)

**v2.0 분리 방식 (예정):**
- 템플릿 프리앰블을 별도 `.typ` 파일로 분리
- `#include "body.typ"`로 본문 참조
- 사용자 정의 템플릿 파일을 MCP 요청 파라미터로 전달 가능

## 11. 의존성 및 설치

### 11.1 요구사항

- Python 3.11+
- Pandoc CLI (`pandoc --version >= 3.0`)
- Typst: Python 패키지 `typst` 또는 CLI `typst` (택 1)

### 11.2 Typst 우선순위 및 버전 정책

Typst에는 **Python 바인딩 패키지(`pip install typst`)** 와 **네이티브 CLI(`typst compile`)** 두 가지 실행 방식이 존재한다. 이 둘은 별도 프로젝트이며 버전이 다를 수 있다.

| 방식 | 설치 | 버전 | 사용 |
|---|---|---|---|
| Python 패키지 | `pip install typst` | PyPI 버전 | Layer 4 기본 사용 (우선순위 1순위) |
| 네이티브 CLI | GitHub Releases | typst 자체 버전 | Python 패키지 없을 때 fallback (2순위) |

**버전 정책:**
- 두 방식 중 하나만 있으면 그것을 사용
- 둘 다 있으면 **Python 패키지 우선** (프로세스 관리가 더 안정적)
- Layer 4는 내부에서 추상화하여 호출 방식을 감춤:
  ```python
  class TypstRenderer:
      async def compile(self, source: str, output: Path) -> bytes:
          if self._use_python_binding:
              import typst
              result = typst.compile(source, output_path=output)
              return output.read_bytes()
          else:
              proc = await asyncio.create_subprocess_exec(
                  "typst", "compile", source, str(output),
                  stdout=asyncio.subprocess.PIPE,
                  stderr=asyncio.subprocess.PIPE
              )
              stdout, stderr = await proc.communicate()
              if proc.returncode != 0:
                  raise TypstError(stderr.decode())
              return output.read_bytes()
  ```
- CI 테스트 매트릭스: Python typst 패키지 버전 × CLI typst 버전 (2×2)
- 입력 Typst 소스는 두 방식에 호환되어야 함 (표준 Typst 문법만 사용)

### 11.3 설치 검증 (MCP 서버 초기화 시)

MCP 서버는 `initialize` 핸들러에서 다음 검증을 수행한다:

```python
async def check_dependencies() -> list[DependencyStatus]:
    checks = []
    # 1. Pandoc
    try:
        result = subprocess.run(["pandoc", "--version"], capture_output=True, text=True, timeout=5)
        checks.append(Dependency("pandoc", installed=True, version=parse_version(result.stdout)))
    except (FileNotFoundError, subprocess.TimeoutExpired):
        checks.append(Dependency("pandoc", installed=False))

    # 2. Typst (Python 바인딩 우선)
    try:
        import typst
        version = getattr(typst, "__version__", "unknown")
        checks.append(Dependency("typst", installed=True, source="python", version=version))
    except ImportError:
        try:
            result = subprocess.run(["typst", "--version"], capture_output=True, text=True, timeout=5)
            checks.append(Dependency("typst", installed=True, source="cli", version=parse_version(result.stdout)))
        except (FileNotFoundError, subprocess.TimeoutExpired):
            checks.append(Dependency("typst", installed=False))

    return checks
```

미설치 시 `initialize` 응답에 `DependencyError`로 보고하며, MCP 클라이언트는 설치 안내 메시지를 표시한다.

### 11.4 Setup 스크립트

```
install_deps.ps1 (Windows)
install_deps.sh (macOS/Linux)

기능:
- Python venv 생성
- pip install -r requirements.txt  (Python typst 패키지 포함)
- Pandoc (없으면 winget/brew/apt로 설치 안내)
- Typst (Python 패키지 `pip install typst` 우선, CLI는 선택)
```

**일관성 주의:** 11.2에 따라 Python 패키지를 1순위로 사용한다. CLI 설치는 권장되지만 필수는 아니다.

## 12. 테스트 전략

### 12.1 테스트 레벨

| 레벨 | 대상 | 도구 | 빈도 |
|---|---|---|---|
| **단위 테스트** | 각 Layer 개별 함수, IR 검증, 에러 처리 | `pytest` | 모든 PR |
| **스냅샷 테스트** | Typst Generator 출력 (.typ 파일) | `pytest --snapshot-update` | 모든 PR |
| **통합 테스트** | MCP 도구 호출 → PDF 출력 (전체 파이프라인) | `pytest` + MCP 클라이언트 | 모든 PR |
| **회귀 테스트** | 기존 문서 재렌더링 동일성 | `pytest` + 이전 PDF 해시 비교 | 주간 |
| **시각적 회귀** | PDF 페이지 이미지 비교 (레이아웃 변경 감지) | `pytest` + `pillow` 이미지 비교 | 릴리스 전 |

### 12.2 스냅샷 테스트 상세

Generator(Layer 3)의 출력인 `.typ` 파일은 **스냅샷 테스트**로 관리한다:

```
tests/
  snapshots/
    test_adr.typ              # ADR 템플릿 출력 스냅샷
    test_report.typ           # Report 템플릿 출력 스냅샷
    test_code_block.typ       # 코드블록 포함 문서
    test_table.typ            # 표 포함 문서
    test_footnotes.typ        # 각주 포함 문서
    test_long_document.typ    # 50p 이상 문서
    test_edge_cases.typ       # 빈 문서, 특수문자, unicode
```

- 스냅샷 변경 시 PR에 diff를 포함
- `--snapshot-update` 플래그로 스냅샷 갱신
- CI에서 스냅샷 불일치 감지 시 실패 처리

### 12.3 통합 테스트

실제 MCP 클라이언트를 통해 `render`, `render_with_template`, `preview`를 호출하고:
- PDF 출력이 valid한가 (PDF magic bytes 체크)
- 페이지 수가 예상과 일치하는가
- 에러 조건에서 올바른 error code를 반환하는가
- timeout 시 TIMEOUT을 반환하는가

### 12.4 시각적 회귀 테스트 (선택, v1.1 목표)

PDF를 PNG로 변환하여 페이지별로 이전 버전과 픽셀 단위 비교:
- `pytest` + `pdf2image` + `pillow`
- 임계값(threshold) 이상 차이 발생 시 실패
- 차이 이미지를 artifact로 저장

## 13. 차별성

기존 MCP들은 대부분 단순 변환기(wrapper) 수준:

```
Markdown → Pandoc → PDF
또는
Markdown → HTML → PDF
```

본 프로젝트의 차별점:

1. **중간 표현(IR) 레이어** — 단순 변환이 아닌 조판 규칙 적용
2. **조판 정책 시스템** — 문서 유형별 레이아웃/스타일 규칙
3. **템플릿 시스템** — 재사용 가능한 문서 템플릿
4. **Typst 기반** — LaTeX 수준의 품질을 더 쉬운 문법으로

## 14. 기술 스택

- **Language**: Python 3.11+ (MCP SDK 생태계 성숙도)
- **MCP SDK**: 공식 Python MCP SDK (`pypi mcp`)
- **Markdown Parser**: `markdown-it-py` (추천) 또는 `mistune`
- **Pandoc Binding**: Layer 1 fallback 또는 참조 구현용
- **Typst**: Python `typst` 패키지 (우선), CLI fallback (`typst compile`)
- **Validation**: `pydantic` (IR 스키마 검증)

## 15. 향후 고려사항

- 추가 문서 유형: API 문서, 게임 기획서, 계약서
- 병렬 렌더링 (여러 문서 동시 변환)
- 페이지별 증분 렌더링 (preview 최적화)
- 이미지 자동 최적화 (리사이즈, WebP 변환)
- 캐싱 전략 (동일 입력 재렌더링 방지)
- CI/CD 파이프라인 연동 (GitHub Actions, 문서 자동 생성)
- 템플릿 마켓플레이스 (커뮤니티 템플릿 공유)

## 16. 용어 정리

| 용어 | 의미 |
|---|---|
| **조판 (Typesetting)** | 텍스트와 이미지를 페이지에 배치하여 인쇄/출판 가능한 형태로 만드는 과정 |
| **중간 표현 (IR)** | 파싱된 문서 구조를 정규화한 데이터 모델. Layer 2의 출력이자 Layer 3의 입력 |
| **MCP** | Model Context Protocol. AI 에이전트가 도구를 사용할 수 있게 하는 프로토콜 |
| **Typst** | Rust 기반 현대적인 조판 언어 및 엔진 |
