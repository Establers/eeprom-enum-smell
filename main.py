import argparse
import os
import time
from eep_checker import parser
from eep_checker.report import save_html_report
from eep_checker.prompt import make_llm_prompt
from utils import find_c_files, save_split_prompts





def main(progress_callback=None):
    """
    EEPROM ENUM 영향 함수 분석기 메인 함수
    
    Args:
        progress_callback (callable, optional): 진행 상황을 알려주는 콜백 함수.
            callback(status: str, elapsed: float, progress: int) 형식으로 호출됨.
    Returns:
        tuple: (prompt_files, error_logs) - 생성된 프롬프트 파일 목록과 에러 로그 목록
    """
    start_time = time.time()
    error_logs = []
    
    def update_progress(status, progress=None):
        """진행 상황 업데이트"""
        if progress_callback:
            elapsed = time.time() - start_time
            progress_callback(status, elapsed, progress)

    def log_error(message):
        """에러 로깅"""
        error_logs.append(message)
        print(message)

    argp = argparse.ArgumentParser(description='EEPROM ENUM 영향 함수 분석기')
    argp.add_argument('--enum', required=True, help='찾으려는 ENUM 이름')
    argp.add_argument('--from', dest='from_value', required=True, help='변경 전 ENUM 값')
    argp.add_argument('--to', dest='to_value', required=True, help='변경 후 ENUM 값')
    argp.add_argument('--path', required=True, help='분석할 C 프로젝트 폴더 경로')
    argp.add_argument('--debug', action='store_true', help='디버그 정보 출력')
    argp.add_argument('--query', action='store_true', help='쿼리 기반 방식 사용(실험적)')
    argp.add_argument('--target-lines', type=int, help='프롬프트 분할 시 파일당 목표 줄 수')
    args = argp.parse_args()

    # 경로 검증
    if not os.path.exists(args.path):
        log_error(f"[Error] 지정된 경로가 존재하지 않습니다: {args.path}")
        return [], error_logs
    if not os.path.isdir(args.path):
        log_error(f"[Error] 지정된 경로가 디렉터리가 아닙니다: {args.path}")
        return [], error_logs

    update_progress("C, H 파일 검색 중...", 0)
    c_files = find_c_files(args.path)
    if not c_files:
        log_error(f"[Warning] 지정된 경로에서 C/H 파일을 찾을 수 없습니다: {args.path}")
        return [], error_logs
    
    print(f"총 {len(c_files)}개의 C, H 파일을 찾았습니다.")

    all_results = []
    llm_prompts = []
    
    total_files = len(c_files)
    for i, cfile in enumerate(c_files, 1):
        progress = int((i / total_files) * 100)
        rel_path = os.path.relpath(cfile, args.path)
        update_progress(f"C, H 파일 분석 중... ({i}/{total_files})", progress)
        
        # 파일 읽기 시도
        try:
            with open(cfile, encoding='utf-8') as f:
                code = f.read()
        except UnicodeDecodeError:
            try:
                with open(cfile, encoding='latin1', errors='ignore') as f:
                    code = f.read()
                log_error(f"[Warning] UTF-8 디코딩 실패, latin1으로 읽기 시도: {rel_path}")
            except Exception as e:
                log_error(f"[Error] 파일 읽기 실패: {rel_path} → {str(e)}")
                continue
        except Exception as e:
            log_error(f"[Error] 파일 읽기 실패: {rel_path} → {str(e)}")
            continue

        # 파싱 시도
        try:
            parser_results = parser.extract_functions_with_enum_file(
                code, args.enum, 
                file_name=rel_path,
                debug=args.debug,
                query_mode=args.query
            )
        except Exception as e:
            log_error(f"[Warning] 파일 파싱 실패: {rel_path} → {str(e)}")
            continue

        for r in parser_results:
            all_results.append(r)
            if args.debug:
                print(f"함수명 추출 결과: {r['func_name']}")
            prompt = make_llm_prompt(
                r['file'], r['func_name'], args.enum, args.from_value, args.to_value, r['code']
            )
            llm_prompts.append(prompt)

    if not all_results:
        log_error(f"[Warning] ENUM '{args.enum}'을 사용하는 함수를 찾을 수 없습니다.")
        return [], error_logs

    # outputs 폴더 생성
    output_dir = 'outputs'
    os.makedirs(output_dir, exist_ok=True)

    update_progress("HTML 보고서 생성 중...", 95)
    try:
        # HTML 보고서 저장
        save_html_report(args.enum, all_results, output_dir=output_dir)
    except Exception as e:
        log_error(f"[Error] HTML 보고서 생성 실패 → {str(e)}")
        return [], error_logs

    update_progress("프롬프트 파일 생성 중...", 98)
    try:
        # LLM 프롬프트 저장 (분할 포함)
        import datetime
        now = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        base_prompt_path = os.path.join(output_dir, f"{args.enum}_LLM_Prompts_{now}.txt")
        
        # 모든 프롬프트를 하나의 문자열로 결합
        separator = '\n' + '-' * 12 + '\n'
        combined_prompts = separator.join(llm_prompts)
        if combined_prompts:  # 프롬프트가 있는 경우에만 구분자 추가
            combined_prompts = separator + combined_prompts + separator
        
        # 프롬프트 분할 저장
        prompt_files = save_split_prompts(combined_prompts, base_prompt_path, args.target_lines)
    except Exception as e:
        log_error(f"[Error] 프롬프트 파일 생성 실패 → {str(e)}")
        return [], error_logs

    # 결과 출력
    if len(prompt_files) > 1:
        print(f"프롬프트가 {len(prompt_files)}개 파일로 분할되어 저장되었습니다:")
        for f in prompt_files:
            print(f"- {f}")
    else:
        print(f"프롬프트 파일이 생성되었습니다: {prompt_files[0]}")

    elapsed = time.time() - start_time
    update_progress(f"분석 완료! (총 {elapsed:.1f}초)", 100)
    print(f"총 수행 시간: {elapsed:.2f}초")
    
    return prompt_files, error_logs

if __name__ == '__main__':
    main()
