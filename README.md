# who-used-this-eep 🕵️‍♂️

> "EEPROM enum 하나 바꿨을 뿐인데… 왜 내 코드가 터지죠?"

---

## 🤔 이게 뭐야?

`who-used-this-eep`는 EEPROM에서 특정 enum 값을 사용할 때,  
**그 enum이 쓰인 모든 코드 위치를 자동으로 찾아주는 툴**입니다.

- `GetEEPROMValue(EEPROM_SOMETHING)` 같은 코드에서
- `EEPROM_SOMETHING`이 쓰인 모든 함수, 조건문, switch 등을 추적해서
- **“이 값 바꾸면 어디 터질까?”** 를 사전에 알려줍니다.

---

## 🛠️ 예시 시나리오

```c
uint8_t mode = GetEEPROMValue(EEPROM_BOOT_MODE);

if (mode == 0) { ... }
else if (mode == 1) { ... }
else { error(); }  // ← 여기, 문제가 생길 수 있음!
```
EEPROM_BOOT_MODE에 새 값을 추가하고 싶은데...
이게 어디서 쓰이는지 수십 개 파일을 눈으로 뒤지고 있진 않나요?

who-used-this-eep가 대신 찾아줍니다.
그리고 위험한 패턴은 자동으로 알려줘요.

## 🔍 기능
GetEEPROMValue(ENUM) 호출 코드 자동 탐지

해당 enum이 쓰인 함수 전체 블록 추출

조건 분기(if, switch) 내 사용 여부 확인

위험한 비교/분기 로직 자동 감지

(선택) LLM을 활용해 특정 값 추가 시 문제 가능성 평가

## 🧪 사용법 (예정)
```python
# 분석 실행
python3 main.py --enum EEPROM_BOOT_MODE

# 결과 출력
✅  Found in: config/init.c:23
⚠️  Potential issue in: boot/mode.c:77
❗  Fallback error handling in: main.c:102
```

## 📦 설치

## ⚠️ 주의사항
- C 코드만 지원합니다
- GetEEPROMValue(enum) 형식이 아니라면 분석이 제한될 수 있어요
- 아직 완벽한 정적 분석기는 아닙니다! 보조용으로 사용해주세요

## 😎 왜 만들었냐면요
EEPROM 값 하나 바꾸고 나서… 바꾼 값 빨리 검토하려고

## ✨ 미래 계획
GitHub Actions 등 과 연동한 PR 자동 검사


