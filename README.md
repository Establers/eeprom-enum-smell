# ENUM 사용 분석기 (EEP Checker)

C 코드에서 특정 ENUM 값의 사용을 분석하고 시각화하는 도구입니다. 코드베이스에서 ENUM이 사용된 위치와 빈도를 파악하여 ENUM 값 변경 시 영향도를 분석하는 데 도움을 줍니다.

## 주요 기능

- 📊 ENUM 사용 분석
  - 파일별, 함수별 ENUM 사용 횟수 집계
  - 구조체 정의 내 ENUM 사용 분석
  - 함수 내부 ENUM 사용 분석

- 📈 시각적 보고서 생성
  - 파일별 ENUM 사용 분포 (파이 차트)
  - 상세 사용 위치 테이블
  - 코드 미리보기 (구문 강조 지원)
  - 반응형 웹 디자인
  - 다크 모드 지원

- 🤖 LLM 프롬프트 생성
  - ENUM 값 변경에 대한 영향도 분석용 프롬프트 자동 생성

## 설치 방법

1. Python 3.8 이상이 필요합니다.

2. 필요한 패키지 설치:
```bash
pip install tree-sitter tree-sitter-languages
```

## 사용 방법

```bash
python main.py --enum [ENUM_NAME] --from [OLD_VALUE] --to [NEW_VALUE] --path [PROJECT_PATH]
```

### 매개변수 설명

- `--enum`: 분석할 ENUM 이름
- `--from`: 변경 전 ENUM 값
- `--to`: 변경 후 ENUM 값
- `--path`: 분석할 C 프로젝트 경로
- `--debug`: (선택) 디버그 정보 출력
- `--query`: (선택) 실험적 쿼리 기반 분석 사용

### 예시

```bash
python main.py --enum MY_ENUM --from 1 --to 2 --path /path/to/project
```

## 출력 결과

1. HTML 보고서 (`outputs/[ENUM_NAME]_Output_[TIMESTAMP].html`)
   - 파일별 ENUM 사용 분포 차트
   - 함수별 상세 사용 정보
   - 인터랙티브 코드 미리보기

2. LLM 프롬프트 (`outputs/[ENUM_NAME]_LLM_Prompts_[TIMESTAMP].txt`)
   - ENUM 값 변경 영향도 분석을 위한 프롬프트

## 프로젝트 구조

- `main.py`: CLI 인터페이스 및 메인 로직
- `eep_checker/`
  - `parser.py`: C 코드 파싱 (tree-sitter 기반)
  - `report.py`: HTML 보고서 생성
  - `prompt.py`: LLM 프롬프트 생성

## 기술 스택

- Python 3.8+
- tree-sitter: C 코드 파싱
- D3.js: 데이터 시각화
- Prism.js: 코드 구문 강조


