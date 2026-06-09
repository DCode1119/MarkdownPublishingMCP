# 문서 맵 (Document Map)

**Revision**: 0.3
**Last Updated**: 2026-06-09

## 문서 목록

| 문서 | 설명 | 상태 |
|---|---|---|
| `REQUIREMENTS.md` | 요구사항 정의서 (v0.5, Round 4 정제 완료) | Draft → Refined |

## 문서 구조 규칙

- 모든 문서는 `Revision`과 `Last Updated`를 포함합니다.
- 문서 추가/변경/삭제 시 이 파일의 문서 맵을 함께 갱신합니다.
- 가장 구체적인 문서부터 업데이트한 후 상위 요약 문서를 갱신합니다.
- Round 2 이상 정제 시 RECURSIVE_REVIEW_LOG를 REQUIREMENTS.md 하단에 추가합니다.

## 정제 이력

| Round | 일자 | 적용된 grill-me 이슈 |
|---|---|---|
| R1 | 2026-06-09 | CRITICAL 2건 + MAJOR 3건 + MINOR 2건 처리. IR 스키마, 에러 명세, 템플릿 변수, 의존성 검증, 문서유형 정리 완료 |
| R2 | 2026-06-09 | CRITICAL 3건 + MAJOR 5건 처리. 입력 검증(Path Traversal 방지), IR Pydantic 검증 레이어, 동시성 제어(RenderPool), timeout/크래시 정책, preview 검증, 템플릿 None 처리, Typst 버전 정책, 테스트 전략 수립 |
| R3 | 2026-06-09 | MINOR 4건 처리. 섹션 번호 재정렬(7→17), 문장 중복 제거, 차별성 섹션 복원, 의존성 정책 일관성 수정 |
| R4 | 2026-06-09 | CRITICAL 4건 + MAJOR 6건 + MINOR 2건 처리. Preview 캐시 기반 재설계, RenderPool._compile_typst+임시파일관리, 템플릿 합성 방식 정의, Link URL 보안검증, 문서유형 불일치 해소, Layer 2b 위치 명확화, CodeBlock/ListBlock/InlineModel Pydantic 모델 추가, 1.1 지원범위 확장 |
