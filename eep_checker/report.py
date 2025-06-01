import datetime
import os
from typing import List, Dict

def save_html_report(enum_name: str, results: List[Dict], output_dir: str = '.'):
    now = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{enum_name}_Output_{now}.html"
    filepath = os.path.join(output_dir, filename)

    total_files = len(set(r['file'] for r in results))
    total_funcs = len(results)
    total_enums = sum(r['enum_count'] for r in results)

    html = f"""
    <html><head><meta charset='utf-8'><title>{enum_name} 분석 보고서</title></head><body>
    <h1>ENUM 분석 보고서: {enum_name}</h1>
    <ul>
      <li>분석 파일 수: {total_files}</li>
      <li>함수 수: {total_funcs}</li>
      <li>ENUM 사용 총 횟수: {total_enums}</li>
    </ul>
    <table border='1' cellpadding='4' style='border-collapse:collapse;'>
      <tr><th>파일명</th><th>함수명</th><th>ENUM 사용 횟수</th><th>코드 미리보기</th></tr>
    """
    for r in results:
        code_preview = r['code'][:200].replace('<', '&lt;').replace('>', '&gt;').replace('\n', '<br>')
        html += f"<tr><td>{r['file']}</td><td>{r['func_name']}</td><td>{r['enum_count']}</td><td><pre>{code_preview}...</pre></td></tr>"
    html += "</table></body></html>"

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"HTML 보고서가 생성되었습니다: {filepath}")
