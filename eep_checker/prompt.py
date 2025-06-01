def make_llm_prompt(file_name, func_name, enum_name, from_value, to_value, code):
    prompt = f"""
[File: {file_name}]  | Function: {func_name}] | Enum: {enum_name}: {from_value} → {to_value}]

1) 함수 목적·역할
2) {enum_name} 사용 위치·의미
3) 값 변경이 미치는 영향  
   - 분기/로직  
   - 호출·반환  
4) 수정·테스트 포인트

```c
{code}
```

"""
    return prompt 