def make_llm_prompt(file_name, func_name, enum_name, from_value, to_value, code):
    prompt = f"""
[File: {file_name}]  | Function: {func_name}] | Enum: {enum_name}: {from_value} → {to_value}]

1. 함수 역할
2. {enum_name}이 쓰인 위치 및 의미
3. 값 변경 시 영향
   - 분기/로직
   - 호출/반환
4. 고칠 부분·테스트 포인트

```c
{code}
```
※ 답변은 “간결하게, 핵심 위주”로 작성해 주세요.
"""
    return prompt 