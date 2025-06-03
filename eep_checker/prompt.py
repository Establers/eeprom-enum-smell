def make_llm_prompt(file_name, func_name, enum_name, from_value, to_value, code, callers=None):
    prompt = f"""
[File: {file_name}]  |  Function: {func_name}  |  Enum: {enum_name}:{from_value} → {to_value}]

1. 함수 역할 (Function: {func_name})
2. {enum_name}이(가) {func_name} 함수 내에서 쓰인 위치 및 의미
3. {enum_name} 값 변경 시 {func_name} 함수에 미치는 영향
   - 원인
   - 분기/로직 변화
   - 호출/반환 값 변화 가능성
4. {func_name} 함수 수정 제안 및 테스트 포인트
5. 심각도 (Function: {func_name})
   - 이유와 ★★★☆☆ (3/5) 등으로 간략하게 표시

```c
// Code for: {func_name}
{code}
```
"""

    if callers:
        prompt += "\n\n--- 이 함수를 호출하는 함수들 ---"
        for caller in callers:
            prompt += f"""

[Caller Function: {caller['func_name']} (in {file_name}) - Calls {func_name} at line {caller['call_line']}]

1. {caller['func_name']} 함수의 역할 및 {func_name} 함수 호출부 분석
2. {func_name} 함수의 변경이 {caller['func_name']} 함수에 미칠 수 있는 영향
3. {caller['func_name']} 함수에서 필요한 수정이나 확인 사항

```c
// Code for: {caller['func_name']}
{caller['code']}
```
"""
    return prompt 