import os

def find_c_files(root_dir, include_headers=False):
    """
    지정된 디렉토리에서 C/H 파일을 찾습니다.
    
    Args:
        root_dir (str): 검색할 루트 디렉토리 경로
        include_headers (bool): 헤더 파일(.h)도 포함할지 여부
        
    Returns:
        list: 발견된 C/H 파일 경로 목록
        
    Raises:
        ValueError: 시스템 루트 디렉토리가 지정된 경우
    """
    # 시스템 경로 검증
    root_dir = os.path.normpath(root_dir)
    
    # 실제 루트 디렉토리인지 확인
    if root_dir.rstrip('\\') in [chr(d) + ':' for d in range(ord('C'), ord('G')+1)]:
        raise ValueError("시스템 루트\n디렉터리 불가")
    
    c_files = []
    for dirpath, _, filenames in os.walk(root_dir):
        # 숨김 폴더 제외
        if any(part.startswith('.') for part in dirpath.split(os.sep)):
            continue
            
        for f in filenames:
            # 헤더 파일은 옵션에 따라 포함
            if f.endswith('.c') or (include_headers and f.endswith('.h')):
                c_files.append(os.path.join(dirpath, f))
    return c_files

def split_prompt_content(prompts_data_list, split_mode, target_lines_for_regular_files, find_caller_active):
    """
    프롬프트 내용을 다양한 모드(줄 수, 호출자 유무)에 따라 분할하고 재조합합니다.
    
    Args:
        prompts_data_list (list): {'text': str, 'has_callers': bool} 형태의 딕셔너리 리스트
        split_mode (str): "lines" 또는 "caller"
        target_lines_for_regular_files (int, optional): "lines" 모드 또는 "caller" 모드에서 호출자 없는 프롬프트 그룹의 목표 줄 수
        find_caller_active (bool): 호출자 분석 기능 활성화 여부
        
    Returns:
        list: (content_str, prompt_count, is_caller_specific_file) 튜플의 리스트
    """
    separator = '\n' + '-' * 12 + '\n'
    formatted_parts = []

    if split_mode == "caller" and find_caller_active:
        prompts_with_callers = []
        prompts_without_callers_text_list = []

        for item in prompts_data_list:
            if item['has_callers']:
                prompts_with_callers.append(item['text'])
            else:
                prompts_without_callers_text_list.append(item['text'])
        
        # 1. 호출자가 있는 프롬프트는 각각 별도 파일로
        for i, prompt_text in enumerate(prompts_with_callers):
            # 각 프롬프트는 단일 섹션으로 간주, is_prompt는 여기서 중요하지 않음 (LLM 프롬프트 자체가 하나의 유닛)
            # 실제 프롬프트 개수는 1개로 고정 (하나의 함수 + 호출자들 정보가 한 세트)
            formatted_parts.append((separator + prompt_text + separator, 1, True)) 

        # 2. 호출자가 없는 프롬프트들은 모아서 기존처럼 라인 수 기반 분할 (또는 분할 안함)
        if prompts_without_callers_text_list:
            combined_no_callers_text = separator.join(prompts_without_callers_text_list)
            if combined_no_callers_text:
                 combined_no_callers_text = separator + combined_no_callers_text + separator

            if target_lines_for_regular_files is None: # 분할 안함
                if combined_no_callers_text.strip(): # 내용이 있을 때만 추가
                    # 이 그룹의 실제 프롬프트(함수) 개수는 len(prompts_without_callers_text_list)
                    formatted_parts.append((combined_no_callers_text, len(prompts_without_callers_text_list), False))
            else: # 라인 수 기반 분할
                # 기존 로직을 재활용하기 위해, prompts_without_callers_text_list를 다시 sections_with_lines 형태로 변환
                sections_no_callers = []
                for section_text in prompts_without_callers_text_list:
                    lines = section_text.split('\n')
                    sections_no_callers.append({
                        'content': section_text,
                        'lines': len(lines),
                        'is_prompt': True # 각 항목을 하나의 프롬프트로 간주
                    })
                
                # 목표 줄 수에 맞게 섹션 그룹화 (기존 로직 일부 사용)
                current_part_content_list = []
                current_lines = 0
                current_prompt_count = 0

                for section_info in sections_no_callers:
                    if not current_part_content_list: # 현재 파트가 비어있으면 무조건 추가
                        current_part_content_list.append(section_info['content'])
                        current_lines = section_info['lines']
                        current_prompt_count = 1
                    elif current_lines + section_info['lines'] > target_lines_for_regular_files * 1.2: # 20% 여유
                        formatted_parts.append((separator + separator.join(current_part_content_list) + separator, current_prompt_count, False))
                        current_part_content_list = [section_info['content']]
                        current_lines = section_info['lines']
                        current_prompt_count = 1
                    else:
                        current_part_content_list.append(section_info['content'])
                        current_lines += section_info['lines']
                        current_prompt_count += 1
                
                if current_part_content_list: # 마지막 파트
                    formatted_parts.append((separator + separator.join(current_part_content_list) + separator, current_prompt_count, False))
        
        if not formatted_parts and prompts_data_list: # 모든 프롬프트가 비어있었지만 원본 데이터는 있었던 경우 등
             # 이 경우, 모든 프롬프트가 호출자가 없었고, 분할 기준도 없었을 수 있음.
             # prompts_data_list의 모든 text를 합쳐서 하나의 파트로.
            all_texts = [item['text'] for item in prompts_data_list if item['text'].strip()]
            if all_texts:
                content = separator + separator.join(all_texts) + separator
                formatted_parts.append((content, len(all_texts), False))

    else: # "lines" 모드 또는 caller 분석 비활성화 시: 기존 로직 (모든 프롬프트를 합쳐서 라인 수로 분할)
        all_prompt_texts = [item['text'] for item in prompts_data_list if item['text'].strip()]
        if not all_prompt_texts:
            return [] # 분할할 내용 없음

        combined_content = separator + separator.join(all_prompt_texts) + separator
        if target_lines_for_regular_files is None:
            return [(combined_content, len(all_prompt_texts), False)]

        # 기존의 sections_with_lines와 유사하게 만듦 (단, is_prompt는 LLM 프롬프트 단위로 항상 True)
        sections = []
        for prompt_text_item in all_prompt_texts:
            lines = prompt_text_item.split('\n')
            sections.append({
                'content': prompt_text_item,
                'lines': len(lines),
                'is_prompt': True 
            })

        parts_collector = []
        current_part_texts = []
        current_lines = 0
        current_prompt_count = 0
        for section in sections:
            if not current_part_texts:
                current_part_texts.append(section['content'])
                current_lines = section['lines']
                current_prompt_count = 1
            elif current_lines + section['lines'] > target_lines_for_regular_files * 1.2:
                parts_collector.append((separator + separator.join(current_part_texts) + separator, current_prompt_count, False))
                current_part_texts = [section['content']]
                current_lines = section['lines']
                current_prompt_count = 1
            else:
                current_part_texts.append(section['content'])
                current_lines += section['lines']
                current_prompt_count += 1
        
        if current_part_texts:
            parts_collector.append((separator + separator.join(current_part_texts) + separator, current_prompt_count, False))
        
        formatted_parts = parts_collector

    # 디버그 출력 부분은 생략 (필요시 추가)
    # print(f"\n=== 분할 결과 ({len(formatted_parts)} 파트) ===")
    # for i, (content, p_count, is_caller_f) in enumerate(formatted_parts):
    #     print(f"Part {i+1}: Prompts={p_count}, IsCallerFile={is_caller_f}, Lines approx ~{content.count('\n')}") 

    return formatted_parts if formatted_parts else []


def save_split_prompts(prompts_data_list, base_path, split_mode, target_lines_for_regular_files, find_caller_active):
    """
    프롬프트를 분할하여 저장합니다.
    
    Args:
        prompts_data_list (list): {'text': str, 'has_callers': bool} 형태의 딕셔너리 리스트
        base_path (str): 기본 저장 경로
        split_mode (str): "lines" 또는 "caller"
        target_lines_for_regular_files (int, optional): "lines" 모드 또는 호출자 없는 파일의 목표 줄 수
        find_caller_active (bool): 호출자 분석 기능 활성화 여부
        
    Returns:
        list: 저장된 파일 경로 목록
    """
    instruction_text = """답변은 함수별로 구분된 섹션으로 작성해주세요! 5번 심각도는 1점(낮음) ~ 5점(높음)과 별모양으로 표시해 주십시오.
    
"""
    if not prompts_data_list:
        # 내용이 없으면 빈 파일 하나만 만들거나, 아무것도 안 만들도록 선택 가능.
        # 여기서는 아무것도 안 만들고 빈 리스트 반환
        print("저장할 프롬프트 내용이 없습니다.")
        return []

    # split_mode가 "lines"이고 target_lines_for_regular_files가 None이면 분할하지 않고 단일 파일로 저장
    if split_mode == "lines" and target_lines_for_regular_files is None:
        all_texts_combined = '\n' + '-' * 12 + '\n'.join([item['text'] for item in prompts_data_list if item['text'].strip()]) + '\n' + '-' * 12 + '\n'
        if not all_texts_combined.strip('\n' + '-' * 12 + '\n '): # 실제 내용이 있는지 확인
             print("저장할 프롬프트 내용이 없습니다 (공백 제외).")
             return []
        with open(base_path, 'w', encoding='utf-8') as f:
            f.write(instruction_text + all_texts_combined)
        return [base_path]

    # content는 이미 prompts_data_list로 받음
    parts = split_prompt_content(prompts_data_list, split_mode, target_lines_for_regular_files, find_caller_active)
    
    if not parts:
        print("분할된 프롬프트 파트가 없습니다.")
        return []

    saved_files = []
    base_name, ext = os.path.splitext(base_path)
    
    # 단일 파트이고 caller 특정 파일이 아닌 경우, 원본 base_path 사용
    if len(parts) == 1 and not parts[0][2]: # (content, prompt_count, is_caller_specific_file)
        with open(base_path, 'w', encoding='utf-8') as f:
            f.write(instruction_text + parts[0][0])
        return [base_path]
    
    # 여러 파트이거나 caller 특정 파일인 경우, 파일명에 인덱스/타입 추가
    caller_file_idx = 1
    regular_file_idx = 1
    for i, (part_content, prompt_count, is_caller_file) in enumerate(parts):
        if not part_content.strip('\n' + '-' * 12 + '\n '): # 실제 내용이 있는지 확인
            continue

        if is_caller_file: # 호출자 관련 파일
            part_path = f"{base_name}_caller_part{caller_file_idx}_{prompt_count}prompts{ext}"
            caller_file_idx += 1
        else: # 일반 분할 파일 (호출자 없거나, lines 모드)
            part_path = f"{base_name}_part{regular_file_idx}_{prompt_count}prompts{ext}"
            regular_file_idx += 1
            
        with open(part_path, 'w', encoding='utf-8') as f:
            # 각 파트의 시작과 끝에 구분자를 이미 split_prompt_content에서 추가했으므로 여기서는 instruction_text만 추가
            f.write(instruction_text + part_content) 
        saved_files.append(part_path)
    
    return saved_files

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

if __name__ == '__main__':
    # 이 파일이 직접 실행될 때의 테스트 코드 (필요시 작성)
    pass