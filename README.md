# 🔍 EEPROM ENUM SMELL

안녕하세요! C 코드에서 ENUM 사용을 분석하는 도구예요 ✨

## 💫 이런 거 할 수 있어요

- 🎯 ENUM 사용 함수 자동 검출
- 📊 HTML 보고서 생성 (파일/함수별 사용 현황)
- 📝 CSV 보고서 생성 (선택사항)
- 🤖 GPT 프롬프트 자동 생성

## 🚀 이렇게 써보세요

### 💻 CLI로 쓰기

```bash
python main.py --enum ENUM_NAME --from OLD_VALUE --to NEW_VALUE --path PROJECT_PATH [options]
```

옵션들이에요:
- `--encoding`: 소스 파일 인코딩이요 (기본값: utf-8)
- `--csv`: CSV 보고서도 만들어드려요
- `--include-headers`: 헤더 파일(.h)도 포함할까요? (기본: C 파일만)
- `--find-caller`: 호출자 함수도 분석해드려요
- `--target-lines`: 프롬프트 나눌 때 파일당 줄 수 또는 "caller" 모드 설정
  - 숫자: 일반 분할 모드 (예: 2000)
  - caller: 호출자별 분리 모드
  - caller:숫자: 호출자별 분리 + 나머지 프롬프트 분할 (예: caller:2000)

### 🖥️ GUI로 쓰기 (더 쉬워요!)

```bash
python gui.py
```

GUI에서는 더 편하게 설정할 수 있어요:
- 파일 > 출력 설정 > 호출자 함수 분석: 호출자 분석 켜기/끄기
- 파일 > 프롬프트 분할 설정: 분할 방식 선택
  - 호출자별 분리: 호출자가 있는 함수는 별도 파일로
  - 나머지 분할: 호출자가 없는 함수들도 줄 수로 분할

## 📦 결과물

- `{ENUM}_Output_{timestamp}.html`: 분석 보고서예요
- `{ENUM}_Output_{timestamp}.csv`: CSV 보고서 (선택했을 때만)
- `{ENUM}_LLM_Prompts_{timestamp}.txt`: GPT한테 물어볼 프롬프트

## ⚡ 필요한 것들

- Python 3.11 이상
- PySide6
- tree-sitter
- tree-sitter-languages

## 📜 라이선스

MIT License로 자유롭게 써주세요! 💝