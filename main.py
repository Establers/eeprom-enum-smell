import argparse
import os
import time
from eep_checker import parser
from eep_checker.report import save_html_report
from eep_checker.csv_report import save_csv_report
from eep_checker.prompt import make_llm_prompt
from utils import find_c_files, save_split_prompts, get_analysis_stats, print_analysis_stats

def get_analysis_stats(enum_name: str, results: list) -> dict:
    """분석 결과의 통계 정보를 반환합니다.
    
    Args:
        enum_name (str): 분석한 ENUM 이름
        results (list): 분석 결과 리스트
    
    Returns:
        dict: 통계 정보를 담은 딕셔너리
    """
    total_files = len(set(r['file'] for r in results))
    total_funcs = len(results)
    total_enums = sum(r['enum_count'] for r in results)
    
    return {
        'enum_name': enum_name,
        'total_files': total_files,
        'total_funcs': total_funcs,
        'total_enums': total_enums
    }

def print_analysis_stats(stats: dict):
    """분석 통계를 출력합니다."""
    print(f"\n=== {stats['enum_name']} 분석 결과 ===")
    print(f"분석 파일 수: {stats['total_files']}")
    print(f"함수 수: {stats['total_funcs']}")
    print(f"ENUM 사용 총 횟수: {stats['total_enums']}\n")

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
    argp.add_argument('--encoding', default='utf-8', help='소스 파일 인코딩 (기본값: utf-8)')
    argp.add_argument('--debug', action='store_true', help='디버그 정보 출력')
    argp.add_argument('--query', action='store_true', help='쿼리 기반 방식 사용(실험적)')
    argp.add_argument('--target-lines', type=str, default=None, help='프롬프트 분할 시 파일당 목표 줄 수 (숫자) 또는 "caller" 모드 지정')
    argp.add_argument('--context-lines', type=int, default=None, help='ENUM 사용 전후 포함할 줄 수 (기본: 전체 함수)')
    argp.add_argument('--csv', action='store_true', help='분석 결과를 CSV 파일로도 저장')
    argp.add_argument('--include-headers', action='store_true', help='헤더 파일(.h)도 분석에 포함')
    argp.add_argument('--find-caller', action='store_true', default=False, help='호출자 함수 분석 기능 사용 (기본값: 비활성화)')
    args = argp.parse_args()

    # 경로 검증
    if not os.path.exists(args.path):
        log_error(f"[Error] 지정된 경로가 존재하지 않습니다: {args.path}")
        return [], error_logs
    if not os.path.isdir(args.path):
        log_error(f"[Error] 지정된 경로가 디렉터리가 아닙니다: {args.path}")
        return [], error_logs

    update_progress(f"C, H 파일 검색 중 (인코딩: {args.encoding})...", 0)
    c_files = find_c_files(args.path, include_headers=args.include_headers)
    if not c_files:
        log_error(f"[Warning] 지정된 경로에서 C/H 파일을 찾을 수 없습니다: {args.path}")
        return [], error_logs
    
    print(f"총 {len(c_files)}개의 {'C/H' if args.include_headers else 'C'} 파일을 찾았습니다.")

    all_results = []
    llm_prompts_data = []
    
    total_files = len(c_files)
    for i, cfile in enumerate(c_files, 1):
        progress = int((i / total_files) * 100)
        rel_path = os.path.relpath(cfile, args.path)
        update_progress(f"열심히 파일 분석 중... ({i}/{total_files})", progress)
        
        # 파일 읽기 시도 (지정된 인코딩 사용)
        try:
            # with open(cfile, 'r', encoding=args.encoding, errors='strict') as f:
            with open(cfile, 'r', encoding=args.encoding, errors='replace') as f:
                code = f.read()
        except UnicodeDecodeError as e:
            log_error(f"[Error] 파일 읽기 실패 ({args.encoding} 인코딩): {rel_path} → {str(e)}")
            continue
        except Exception as e:
            log_error(f"[Error] 파일 읽기 실패: {rel_path} → {str(e)}")
            continue

        # 파싱 시도
        try:
            parser_results = parser.extract_functions_with_enum_file(
                code,
                args.enum,
                file_name=rel_path,
                debug=args.debug,
                query_mode=args.query,
                analyze_callers=args.find_caller,
                context_lines=args.context_lines,
            )
        except Exception as e:
            log_error(f"[Warning] 파일 파싱 실패: {rel_path} → {str(e)}")
            continue

        for r in parser_results:
            all_results.append(r)
            if args.debug:
                print(f"함수명 추출 결과: {r['func_name']}")
            prompt_text = make_llm_prompt(
                r['file'], r['func_name'], args.enum, args.from_value, args.to_value, r['code'],
                callers=r.get('callers')
            )
            llm_prompts_data.append({'text': prompt_text, 'has_callers': bool(r.get('callers'))})

    if not all_results:
        log_error(f"[Warning] ENUM '{args.enum}'을(를) 사용하는 함수를 찾을 수 없습니다.")
        return [], error_logs

    # 통계 정보 수집 및 출력
    stats = get_analysis_stats(args.enum, all_results)
    print_analysis_stats(stats)

    # outputs 폴더 생성
    output_dir = 'outputs'
    os.makedirs(output_dir, exist_ok=True)

    update_progress("HTML 보고서 생성 중...", 95)
    try:
        # HTML 보고서 저장
        save_html_report(args.enum, all_results, output_dir=output_dir)
        
        # CSV 보고서 저장 (--csv 옵션이 있을 때만)
        if args.csv:
            update_progress("CSV 보고서 생성 중...", 97)
            try:
                save_csv_report(args.enum, all_results, output_dir=output_dir)
            except Exception as e:
                log_error(f"[Error] CSV 보고서 생성 실패 → {str(e)}")
    except Exception as e:
        log_error(f"[Error] HTML 보고서 생성 실패 → {str(e)}")
        return [], error_logs

    update_progress("프롬프트 파일 생성 중...", 98)
    try:
        # LLM 프롬프트 저장 (분할 포함)
        import datetime
        now = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        base_prompt_path = os.path.join(output_dir, f"{args.enum}_LLM_Prompts_{now}.txt")
        
        parsed_split_mode = "lines" # 기본 분할 모드
        parsed_target_lines_for_regular = None

        if args.target_lines:
            val_lower = args.target_lines.lower()
            if val_lower.startswith("caller"):
                if args.find_caller:
                    parsed_split_mode = "caller"
                    parts = val_lower.split(':', 1)
                    if len(parts) > 1 and parts[1].isdigit():
                        num = int(parts[1])
                        if num > 0:
                            parsed_target_lines_for_regular = num
                        else:
                            log_error(f'[Warning] "--target-lines caller:N"에서 N은 양의 정수여야 합니다. (입력: {args.target_lines}). 호출자 없는 파일은 분할하지 않습니다.')
                            # parsed_target_lines_for_regular is None (분할 안함)
                    # "caller"만 입력된 경우, parsed_target_lines_for_regular는 None (호출자 없는 파일 분할 안함)
                else:
                    log_error(f'[Warning] "--target-lines {args.target_lines}" 옵션은 "--find-caller" 옵션과 함께 사용해야 합니다. 기본 분할 없음으로 진행합니다.')
                    # parsed_split_mode = "lines", parsed_target_lines_for_regular = None (분할 안 함)
            else:
                try:
                    num_val = int(args.target_lines)
                    if num_val > 0:
                        parsed_target_lines_for_regular = num_val
                    else:
                        log_error("[Warning] '--target-lines' 값은 양의 정수여야 합니다. 기본 라인 분할 없음으로 진행합니다.")
                        # parsed_target_lines_for_regular is None (분할 안 함)
                except ValueError:
                    log_error(f'[Warning] "--target-lines" 값 "{args.target_lines}"이(가) 유효한 숫자나 "caller" 또는 "caller:N" 형식이 아닙니다. 기본 분할 없음으로 진행합니다.')
                    # parsed_split_mode = "lines", parsed_target_lines_for_regular = None (분할 안 함)
        
        # 프롬프트 분할 저장
        prompt_files = save_split_prompts(
            prompts_data_list=llm_prompts_data, 
            base_path=base_prompt_path, 
            split_mode=parsed_split_mode, 
            target_lines_for_regular_files=parsed_target_lines_for_regular,
            find_caller_active=args.find_caller
        )
    except Exception as e:
        log_error(f"[Error] 프롬프트 파일 생성 실패 → {str(e)}")
        return [], error_logs

    # 결과 출력
    if prompt_files:
        if len(prompt_files) > 1:
            print(f"프롬프트가 {len(prompt_files)}개 파일로 분할되어 저장되었습니다:")
            for f_path in prompt_files: # 변수명 변경
                print(f"- {f_path}")
        else:
            print(f"프롬프트 파일이 생성되었습니다: {prompt_files[0]}")
    else:
        # llm_prompts_data는 있지만 파일이 생성 안된 경우 (예: 모든 프롬프트가 비어있거나 오류로 저장 실패)
        if llm_prompts_data:
            print("프롬프트 내용이 있었으나 파일로 저장되지 못했습니다. 에러 로그를 확인해주세요.")
        # else: all_results 자체가 없어서 llm_prompts_data도 비어있는 경우는 이미 위에서 처리됨

    elapsed = time.time() - start_time
    update_progress(f"분석 완료! (총 {elapsed:.1f}초)", 100)
    print(f"총 수행 시간: {elapsed:.2f}초")
    
    return prompt_files, error_logs

if __name__ == '__main__':
    main()
