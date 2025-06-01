def make_llm_prompt(file_name, func_name, enum_name, from_value, to_value, code):
    prompt = f"""
[파일명: {file_name}]
[함수명: {func_name}]
[ENUM: {enum_name}]
[변경: {from_value} → {to_value}]

아래 함수는 {enum_name}을(를) 사용합니다. 이 ENUM 값이 {from_value}에서 {to_value}로 바뀔 때 영향받는 부분을 검토해 주세요.

--- 함수 코드 ---
{code}
"""
    return prompt 