import csv
import os
import datetime

def save_csv_report(enum_name: str, results: list, output_dir: str = '.'):
    """분석 결과를 CSV 파일로 저장합니다.
    
    Args:
        enum_name (str): 분석한 ENUM 이름
        results (list): 분석 결과 리스트
        output_dir (str): 출력 디렉토리 경로
    
    Returns:
        str: 생성된 CSV 파일의 경로
    """
    now = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{enum_name}_Output_{now}.csv"
    filepath = os.path.join(output_dir, filename)
    
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        # 헤더 작성
        writer.writerow(['파일명', '함수명', 'ENUM 사용 횟수', '코드'])
        
        # 데이터 작성
        for r in results:
            writer.writerow([
                r.get('file', ''),
                r.get('func_name', ''),
                r.get('enum_count', 0),
                r.get('code', '').replace('\n', '\\n')  # 줄바꿈 이스케이프
            ])
    
    print(f"CSV 보고서가 생성되었습니다: {filepath}")
    return filepath 