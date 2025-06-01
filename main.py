import argparse
import os
import time
from eep_checker import parser
from eep_checker.report import save_html_report
from eep_checker.prompt import make_llm_prompt


def split_prompt_content(content, target_lines=None):
    """프롬프트 내용을 구분자(=====)로 분할하고, 목표 줄 수에 맞게 재조합"""
    # target_lines가 None이면 분할하지 않음
    if target_lines is None:
        return [content]

    # 구분자로 프롬프트 분할
    separator = '\n' + '=' * 80 + '\n'
    sections = content.strip().split(separator)
    sections = [s.strip() for s in sections if s.strip()]  # 빈 섹션 제거
    
    # 각 섹션의 줄 수 계산
    sections_with_lines = []
    for section in sections:
        lines = section.split('\n')
        first_lines = lines[:6] if len(lines) >= 6 else lines  # 처음 6줄 확인
        
        # 프롬프트 특징 확인
        has_file = any('[파일' in line or '[File' in line for line in first_lines)
        has_func = any('[함수' in line or '[Function' in line for line in first_lines)
        has_enum = any('[ENUM' in line or '[enum' in line for line in first_lines)
        has_change = any('[변경' in line or '[Change' in line for line in first_lines)
        has_code = '--- 함수 코드 ---' in section
        
        # 프롬프트 판별 (파일명 또는 함수명이 있고, ENUM이나 함수 코드가 있으면 프롬프트로 인정)
        is_prompt = (has_file or has_func) and (has_enum or has_code)
        
        sections_with_lines.append({
            'content': section,
            'lines': len(lines),
            'is_prompt': is_prompt,
            'first_lines': '\n'.join(first_lines),  # 디버그용
            'features': {  # 디버그용
                '파일명 태그': has_file,
                '함수명 태그': has_func,
                'ENUM 태그': has_enum,
                '변경 태그': has_change,
                '함수 코드': has_code
            }
        })
    
    # 목표 줄 수에 맞게 섹션 그룹화
    parts = []
    current_part = []
    current_lines = 0
    
    for section in sections_with_lines:
        # 현재 파트가 비어있으면 무조건 추가
        if not current_part:
            current_part.append(section)
            current_lines = section['lines']
            continue
        
        # 현재 섹션을 추가했을 때 목표 줄 수를 크게 초과하면 새 파트 시작
        if current_lines + section['lines'] > target_lines * 1.2:  # 20% 여유 허용
            parts.append(current_part)
            current_part = [section]
            current_lines = section['lines']
        else:
            current_part.append(section)
            current_lines += section['lines']
    
    # 마지막 파트 처리
    if current_part:
        parts.append(current_part)
    
    # 각 파트를 문자열로 변환하고 구분자 추가
    formatted_parts = []
    for part in parts:
        # 실제 프롬프트 섹션 수 계산
        prompt_count = sum(1 for s in part if s['is_prompt'])
        content = separator.join(s['content'] for s in part)
        formatted_parts.append((content, prompt_count))
        
        # 디버그 출력
        print(f"\n=== 파트 정보 (프롬프트 수: {prompt_count}) ===")
        for s in part:
            print(f"처음 몇 줄:\n{s['first_lines']}")
            print("특징:")
            for feature, present in s['features'].items():
                print(f"- {feature}: {'있음' if present else '없음'}")
            print(f"프롬프트 여부: {s['is_prompt']}")
            print(f"줄 수: {s['lines']}")
            print("---")
    
    return formatted_parts if formatted_parts else [(content, 1)]


def save_split_prompts(content, base_path, target_lines=None):
    """프롬프트를 분할하여 저장"""
    # 구분자 정의
    separator = '\n' + '=' * 80 + '\n'

    # target_lines가 None이면 분할하지 않고 바로 저장
    if target_lines is None:
        with open(base_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return [base_path]

    parts = split_prompt_content(content, target_lines)
    saved_files = []
    
    if len(parts) == 1:
        # 분할이 필요없는 경우 원래 파일로 저장
        with open(base_path, 'w', encoding='utf-8') as f:
            f.write(parts[0][0])  # content만 저장
        return [base_path]
    
    # 여러 파일로 분할하여 저장
    base_name, ext = os.path.splitext(base_path)
    for i, (part_content, prompt_count) in enumerate(parts, 1):
        # 파일 이름에 실제 프롬프트 수 포함
        part_path = f"{base_name}_part{i}_{prompt_count}prompts{ext}"
        with open(part_path, 'w', encoding='utf-8') as f:
            f.write(separator + part_content + separator)  # 구분자 추가
        saved_files.append(part_path)
    
    return saved_files


def find_c_files(root_dir):
    c_files = []
    for dirpath, _, filenames in os.walk(root_dir):
        for f in filenames:
            if f.endswith('.c'):
                c_files.append(os.path.join(dirpath, f))
    return c_files


def main(progress_callback=None):
    """
    EEPROM ENUM 영향 함수 분석기 메인 함수
    
    Args:
        progress_callback (callable, optional): 진행 상황을 알려주는 콜백 함수.
            callback(status: str, elapsed: float) 형식으로 호출됨.
    """
    start_time = time.time()
    
    def update_progress(status):
        """진행 상황 업데이트"""
        if progress_callback:
            elapsed = time.time() - start_time
            progress_callback(status, elapsed)

    argp = argparse.ArgumentParser(description='EEPROM ENUM 영향 함수 분석기')
    argp.add_argument('--enum', required=True, help='찾으려는 ENUM 이름')
    argp.add_argument('--from', dest='from_value', required=True, help='변경 전 ENUM 값')
    argp.add_argument('--to', dest='to_value', required=True, help='변경 후 ENUM 값')
    argp.add_argument('--path', required=True, help='분석할 C 프로젝트 폴더 경로')
    argp.add_argument('--debug', action='store_true', help='디버그 정보 출력')
    argp.add_argument('--query', action='store_true', help='쿼리 기반 방식 사용(실험적)')
    argp.add_argument('--target-lines', type=int, help='프롬프트 분할 시 파일당 목표 줄 수')
    args = argp.parse_args()

    update_progress("C 파일 검색 중...")
    c_files = find_c_files(args.path)
    print(f"총 {len(c_files)}개의 C 파일을 찾았습니다.")

    all_results = []
    llm_prompts = []
    
    update_progress(f"C 파일 분석 중... (0/{len(c_files)})")
    for i, cfile in enumerate(c_files, 1):
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
        
        update_progress(f"C 파일 분석 중... ({i}/{len(c_files)})")

    # outputs 폴더 생성
    output_dir = 'outputs'
    os.makedirs(output_dir, exist_ok=True)

    update_progress("HTML 보고서 생성 중...")
    # HTML 보고서 저장
    save_html_report(args.enum, all_results, output_dir=output_dir)

    update_progress("프롬프트 파일 생성 중...")
    # LLM 프롬프트 저장 (분할 포함)
    import datetime
    now = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    base_prompt_path = os.path.join(output_dir, f"{args.enum}_LLM_Prompts_{now}.txt")
    
    # 모든 프롬프트를 하나의 문자열로 결합
    separator = '\n' + '=' * 80 + '\n'
    combined_prompts = separator.join(llm_prompts)
    if combined_prompts:  # 프롬프트가 있는 경우에만 구분자 추가
        combined_prompts = separator + combined_prompts + separator
    
    # 프롬프트 분할 저장
    prompt_files = save_split_prompts(combined_prompts, base_prompt_path, args.target_lines)
    
    # 결과 출력
    if len(prompt_files) > 1:
        print(f"프롬프트가 {len(prompt_files)}개 파일로 분할되어 저장되었습니다:")
        for f in prompt_files:
            print(f"- {f}")
    else:
        print(f"프롬프트 파일이 생성되었습니다: {prompt_files[0]}")

    elapsed = time.time() - start_time
    update_progress(f"분석 완료! (총 {elapsed:.1f}초)")
    print(f"총 수행 시간: {elapsed:.2f}초")
    
    return prompt_files

if __name__ == '__main__':
    main()
