from tree_sitter import Language

Language.build_library(
    'build/my-languages.so',    # 출력 경로
    ['tree-sitter-c']           # C 언어만 사용
)

C_LANGUAGE = Language('build/my-languages.so', 'c')