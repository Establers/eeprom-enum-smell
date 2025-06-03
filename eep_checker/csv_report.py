import csv
import os
import datetime
from typing import List, Dict

def save_csv_report(enum_name: str, results: List[Dict], output_dir: str = '.'):
    """분석 결과를 CSV 파일로 저장합니다.
    
    Args:
        enum_name (str): 분석한 ENUM 이름
        results (List[Dict]): 분석 결과 리스트
        output_dir (str): 출력 디렉토리 경로
    
    Returns:
        str: 생성된 CSV 파일의 경로
    """
    now = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{enum_name}_Output_{now}.csv"
    filepath = os.path.join(output_dir, filename)
    
    with open(filepath, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        # 헤더 작성
        writer.writerow([
            '타입', '파일경로', '함수명', 'ENUM 사용횟수 (호출대상인 경우)',
            '시작 라인', '끝 라인', 'ENUM 사용 라인 (호출대상인 경우)', '호출 대상 함수', '호출 라인 (호출자인 경우)',
            '코드'
        ])
        
        # 데이터 작성
        for r in results:
            # ENUM 사용 라인들을 쉼표로 구분된 문자열로 변환
            enum_lines_str = ', '.join(map(str, r['enum_lines']))
            
            # 1. Enum 사용 함수 정보 기록
            writer.writerow([
                'Enum 사용 함수', # 타입
                r['file'],
                r['func_name'],
                r['enum_count'],
                r['start_line'],
                r['end_line'],
                enum_lines_str,
                '', # 호출 대상 함수 (본인이므로 비워둠)
                '', # 호출 라인 (본인이므로 비워둠)
                r['code'].replace('\n', '\\n')
            ])

            # 2. 호출자(Caller) 정보 기록
            if r.get('callers'):
                for caller in r['callers']:
                    writer.writerow([
                        '호출 함수', # 타입
                        r['file'], # 호출자가 포함된 파일 (Enum 사용 함수와 동일 파일 가정)
                        caller['func_name'],
                        '', # Enum 사용 횟수 (호출자이므로 비워둠)
                        caller['start_line'],
                        caller['end_line'],
                        '', # Enum 사용 라인 (호출자이므로 비워둠)
                        r['func_name'], # 호출 대상 함수명
                        caller['call_line'], # 호출 라인
                        caller['code'].replace('\n', '\\n')
                    ])
    
    print(f"CSV 보고서가 생성되었습니다: {filepath}")
    return filepath 