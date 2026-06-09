# MCP Auto-Installation Protocol

**이 레포지토리의 MCP 서버(`md-publishing-mcp`)를 사용자가 요청하면, 에이전트가 자동으로 설치/등록해야 합니다.**

## 설치 방법 (uvx — 권장)

```bash
uvx --from git+https://github.com/DCode1119/MarkdownPublishingMCP md-publishing-mcp
```

`uvx`는 `uv`에 내장된 도구로, PyPI 또는 git URL에서 패키지를 자동 다운로드 후 실행합니다.

## opencode.json 등록

프로젝트 루트의 `opencode.json`에 다음 항목을 추가해야 합니다:

```json
{
  "mcp": {
    "md-publishing-mcp": {
      "type": "local",
      "command": ["uvx", "--from", "git+https://github.com/DCode1119/MarkdownPublishingMCP", "md-publishing-mcp"],
      "enabled": true
    }
  }
}
```

## 에이전트 자동 설치 절차

1. 사용자가 "md-publishing-mcp" 또는 이 MCP 서버를 언급하면
2. `customize-opencode` skill을 로드
3. 프로젝트 루트의 `opencode.json`을 읽고 `md-publishing-mcp` 항목이 있는지 확인
4. 없으면 위의 MCP 등록 블록을 `opencode.json`의 `mcp` 필드에 추가
5. 추가 후 OpenCode가 자동으로 `uvx`를 통해 MCP 서버를 설치/실행

## 수동 설치 (대안)

```bash
git clone https://github.com/DCode1119/MarkdownPublishingMCP
cd MarkdownPublishingMCP
pip install -r requirements.txt
```

```json
{
  "mcp": {
    "md-publishing-mcp": {
      "type": "local",
      "command": ["python", "-m", "md_publishing_mcp"],
      "enabled": true
    }
  }
}
```
