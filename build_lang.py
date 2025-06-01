# build_lang.py

from tree_sitter import Language
import os

# 빌드될 파일 위치
BUILD_DIR = "build"
SO_FILE = os.path.join(BUILD_DIR, "my-languages.so")

# C 문법 경로 (기본값은 프로젝트 루트에 있는 tree-sitter-c)
GRAMMAR_DIR = "tree-sitter-c"

# 디렉토리 없으면 생성
os.makedirs(BUILD_DIR, exist_ok=True)

# 빌드 실행
print(f"Building language library: {SO_FILE}")
Language.build_library(
    SO_FILE,
    [GRAMMAR_DIR]
)
print("Build completed.")