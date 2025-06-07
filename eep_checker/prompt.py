def make_llm_prompt(file_name, func_name, enum_name, from_value, to_value, code, callers=None):
    """Return a concise prompt for LLM analysis."""

    prompt = f"""
[File: {file_name}] | Function: {func_name} | Enum: {enum_name} {from_value} → {to_value}]

- {func_name}의 역할과 {enum_name} 사용 위치를 2문장 이내로 요약
- {enum_name} 변경 시 예상 영향과 놓치기 쉬운 엣지 케이스 정리
- 수정 제안과 테스트 포인트를 핵심 위주로 제시
- 변경 심각도를 ★1~5로 표시하고 간단한 이유 덧붙이기

```c
// Code for: {func_name}
{code}
```
"""

    if callers:
        prompt += "\n\n--- 호출자 함수 요약 ---"
        for caller in callers:
            prompt += f"""

[Caller: {caller['func_name']} in {file_name}, line {caller['call_line']}]

- {caller['func_name']}의 역할과 {func_name} 호출 이유를 2문장 이내로 설명
- {func_name} 수정 시 {caller['func_name']}에 미칠 영향과 확인 포인트

```c
// Code for: {caller['func_name']}
{caller['code']}
```
"""
    return prompt 