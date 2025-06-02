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

def split_prompt_content(content, target_lines=None):
    """
    프롬프트 내용을 구분자로 분할하고 목표 줄 수에 맞게 재조합합니다.
    
    Args:
        content (str): 분할할 프롬프트 내용
        target_lines (int, optional): 파일당 목표 줄 수
        
    Returns:
        list: (content, prompt_count) 튜플의 리스트
    """
    # target_lines가 None이면 분할하지 않음
    if target_lines is None:
        return [(content, 1)]

    # 구분자로 프롬프트 분할
    separator = '\n' + '-' * 12 + '\n'
    sections = content.strip().split(separator)
    sections = [s.strip() for s in sections if s.strip()]  # 빈 섹션 제거
    
    # 각 섹션의 줄 수 계산
    sections_with_lines = []
    for section in sections:
        lines = section.split('\n')
        first_lines = lines[:6] if len(lines) >= 6 else lines  # 처음 6줄 확인
        
        # 프롬프트 특징 확인
        has_file = any('File:' in line for line in first_lines)
        has_func = any('Function:' in line for line in first_lines)
        has_enum = any('Enum:' in line for line in first_lines)
        has_change = any('→' in line for line in first_lines)
        has_code = '```c' in section
        
        # 프롬프트 판별 (헤더 라인에 File, Function, Enum이 모두 있고 코드 블록이 있으면 프롬프트로 인정)
        header_complete = has_file and has_func and has_enum and has_change
        is_prompt = header_complete and has_code
        
        sections_with_lines.append({
            'content': section,
            'lines': len(lines),
            'is_prompt': is_prompt,
            'first_lines': '\n'.join(first_lines),  # 디버그용
            'features': {  # 디버그용
                'File 태그': has_file,
                'Function 태그': has_func,
                'Enum 태그': has_enum,
                '변경 태그': has_change,
                '코드 블록': has_code,
                '헤더 완전성': header_complete
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
    """
    프롬프트를 분할하여 저장합니다.
    
    Args:
        content (str): 저장할 프롬프트 내용
        base_path (str): 기본 저장 경로
        target_lines (int, optional): 파일당 목표 줄 수
        
    Returns:
        list: 저장된 파일 경로 목록
    """
    separator = '\n' + '-' * 12 + '\n'
    instruction_text = """답변은 함수별로 구분된 섹션”으로, 각 항목마다 핵심만 짧은 문장으로 작성하세요. 
특히 5번 심각도는 “1점(낮음) ~ 5점(높음)” 중 하나로 표현하거나 “높음/중간/낮음”으로 표시해 주십시오.
    
"""

    if target_lines is None:
        with open(base_path, 'w', encoding='utf-8') as f:
            f.write(instruction_text + content)
        return [base_path]

    parts = split_prompt_content(content, target_lines)
    saved_files = []
    
    if len(parts) == 1:
        with open(base_path, 'w', encoding='utf-8') as f:
            f.write(instruction_text + parts[0][0])
        return [base_path]
    
    base_name, ext = os.path.splitext(base_path)
    for i, (part_content, prompt_count) in enumerate(parts, 1):
        part_path = f"{base_name}_part{i}_{prompt_count}prompts{ext}"
        with open(part_path, 'w', encoding='utf-8') as f:
            f.write(instruction_text + separator + part_content + separator)
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