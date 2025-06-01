import argparse
import os
import time
from eep_checker import parser
from eep_checker.report import save_html_report
from eep_checker.prompt import make_llm_prompt


def find_c_files(root_dir):
    c_files = []
    for dirpath, _, filenames in os.walk(root_dir):
        for f in filenames:
            if f.endswith('.c'):
                c_files.append(os.path.join(dirpath, f))
    return c_files


def main():
    start_time = time.time()
    argp = argparse.ArgumentParser(description='EEPROM ENUM 영향 함수 분석기')
    argp.add_argument('--enum', required=True, help='찾으려는 ENUM 이름')
    argp.add_argument('--from', dest='from_value', required=True, help='변경 전 ENUM 값')
    argp.add_argument('--to', dest='to_value', required=True, help='변경 후 ENUM 값')
    argp.add_argument('--path', required=True, help='분석할 C 프로젝트 폴더 경로')
    argp.add_argument('--debug', action='store_true', help='디버그 정보 출력')
    argp.add_argument('--query', action='store_true', help='쿼리 기반 방식 사용(실험적)')
    args = argp.parse_args()

    c_files = find_c_files(args.path)
    print(f"총 {len(c_files)}개의 C 파일을 찾았습니다.")

    all_results = []
    llm_prompts = []
    for cfile in c_files:
        with open(cfile, encoding='utf-8', errors='ignore') as f:
            code = f.read()
        parser_results = parser.extract_functions_with_enum_file(
            code, args.enum, 
            file_name=os.path.relpath(cfile, args.path),
            debug=args.debug,
            query_mode=args.query
        )
        for r in parser_results:
            all_results.append(r)
            if args.debug:
                print(f"함수명 추출 결과: {r['func_name']}")
            prompt = make_llm_prompt(
                r['file'], r['func_name'], args.enum, args.from_value, args.to_value, r['code']
            )
            llm_prompts.append(prompt)

    # outputs 폴더 생성
    output_dir = 'outputs'
    os.makedirs(output_dir, exist_ok=True)

    # HTML 보고서 저장
    save_html_report(args.enum, all_results, output_dir=output_dir)

    # LLM 프롬프트 txt로 저장
    import datetime
    now = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    prompt_filename = os.path.join(output_dir, f"{args.enum}_LLM_Prompts_{now}.txt")
    with open(prompt_filename, 'w', encoding='utf-8') as f:
        for p in llm_prompts:
            f.write(p)
            f.write('\n' + ('='*80) + '\n')
    print(f"LLM 프롬프트 파일이 생성되었습니다: {prompt_filename}")

    elapsed = time.time() - start_time
    print(f"총 수행 시간: {elapsed:.2f}초")

if __name__ == '__main__':
    main()
