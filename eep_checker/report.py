import html
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
    enum_name_esc = html.escape(enum_name)

    html_head = f"""
    <!DOCTYPE html>
    <html lang='ko'>
    <head>
      <meta charset='utf-8'>
      <title>{enum_name_esc} 분석 보고서</title>
      <meta name='viewport' content='width=device-width, initial-scale=1'>
      <style>
        body {{
          font-family: 'Segoe UI', 'Malgun Gothic', Arial, sans-serif;
          background: var(--bg, #f7f7fa);
          color: var(--fg, #222);
          margin: 0;
          padding: 0;
        }}
        .container {{
          max-width: 1100px;
          margin: 40px auto 40px auto;
          background: var(--panel, #fff);
          border-radius: 16px;
          box-shadow: 0 4px 24px rgba(0,0,0,0.08);
          padding: 32px 32px 24px 32px;
        }}
        h1 {{
          margin-top: 0;
          font-size: 2.2em;
          letter-spacing: -1px;
        }}
        .summary-list {{
          list-style: none;
          padding: 0;
          margin: 0 0 24px 0;
          display: flex;
          gap: 32px;
        }}
        .summary-list li {{
          font-size: 1.1em;
          background: var(--chip, #e9e9f3);
          border-radius: 8px;
          padding: 8px 18px;
          display: inline-block;
        }}
        .toolbar {{
          display: flex;
          gap: 16px;
          margin-bottom: 18px;
          align-items: center;
        }}
        .toolbar input[type='text'] {{
          font-size: 1em;
          padding: 6px 12px;
          border-radius: 6px;
          border: 1px solid #bbb;
          width: 220px;
        }}
        .toolbar button {{
          background: #222;
          color: #fff;
          border: none;
          border-radius: 6px;
          padding: 7px 18px;
          font-size: 1em;
          cursor: pointer;
          transition: background 0.2s;
        }}
        .toolbar button:hover {{
          background: #444;
        }}
        .toolbar .dark-toggle {{
          background: #fff;
          color: #222;
          border: 1px solid #bbb;
        }}
        .toolbar .dark-toggle.active {{
          background: #222;
          color: #fff;
        }}
        table {{
          width: 100%;
          border-collapse: collapse;
          margin-bottom: 16px;
          table-layout: fixed;
        }}
        th, td {{
          padding: 10px 8px;
          border-bottom: 1px solid #e0e0e0;
          text-align: left;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }}
        th {{
          background: var(--chip, #e9e9f3);
          cursor: pointer;
          user-select: none;
        }}
        tr:hover {{
          background: #f0f6ff;
        }}
        td:not(:last-child) {{
          min-width: 120px;
          max-width: 260px;
        }}
        td:last-child {{
          width: 60%;
          min-width: 200px;
          white-space: normal;
        }}
        .code-preview {{
          background: #181c24;
          color: #e6e6e6;
          border-radius: 8px;
          padding: 10px;
          font-family: 'Fira Mono', 'Consolas', 'Menlo', monospace;
          font-size: 0.98em;
          max-height: 120px;
          overflow: auto;
          margin: 0;
          display: none;
        }}
        .show-btn {{
          background: #0078d7;
          color: #fff;
          border: none;
          border-radius: 5px;
          padding: 4px 12px;
          font-size: 0.95em;
          cursor: pointer;
          margin-bottom: 2px;
        }}
        .show-btn:hover {{
          background: #005fa3;
        }}
        :root[data-theme='dark'] {{
          --bg: #181c24;
          --fg: #e6e6e6;
          --panel: #23293a;
          --chip: #23293a;
        }}
      </style>
      <script>
        // 다크모드 토글
        function toggleDarkMode(btn) {{
          const root = document.documentElement;
          const isDark = root.getAttribute('data-theme') === 'dark';
          if (isDark) {{
            root.removeAttribute('data-theme');
            btn.classList.remove('active');
            localStorage.setItem('eep_dark', '0');
          }} else {{
            root.setAttribute('data-theme', 'dark');
            btn.classList.add('active');
            localStorage.setItem('eep_dark', '1');
          }}
        }}
        window.onload = function() {{
          // 다크모드 상태 복원
          if (localStorage.getItem('eep_dark') === '1') {{
            document.documentElement.setAttribute('data-theme', 'dark');
            document.getElementById('darkBtn').classList.add('active');
          }}
        }}
        // 코드 미리보기 토글
        function toggleCode(idx) {{
          var el = document.getElementById('code_' + idx);
          if (el.style.display === 'block') {{
            el.style.display = 'none';
          }} else {{
            el.style.display = 'block';
          }}
        }}
        // 테이블 정렬
        function sortTable(n) {{
          var table = document.getElementById('resultTable');
          var rows = Array.from(table.rows).slice(1);
          var asc = table.getAttribute('data-sort') !== 'col' + n + '_asc';
          rows.sort(function(a, b) {{
            var x = a.cells[n].innerText.toLowerCase();
            var y = b.cells[n].innerText.toLowerCase();
            if (!isNaN(x) && !isNaN(y)) {{ x = Number(x); y = Number(y); }}
            return asc ? (x > y ? 1 : x < y ? -1 : 0) : (x < y ? 1 : x > y ? -1 : 0);
          }});
          for (var i = 0; i < rows.length; i++) table.tBodies[0].appendChild(rows[i]);
          table.setAttribute('data-sort', 'col' + n + (asc ? '_asc' : '_desc'));
        }}
        // 검색/필터
        function filterTable() {{
          var input = document.getElementById('searchInput').value.toLowerCase();
          var table = document.getElementById('resultTable');
          var rows = table.getElementsByTagName('tr');
          for (var i = 1; i < rows.length; i++) {{
            var show = false;
            for (var j = 0; j < 4; j++) {{
              if (rows[i].cells[j].innerText.toLowerCase().indexOf(input) > -1) show = true;
            }}
            rows[i].style.display = show ? '' : 'none';
          }}
        }}
      </script>
    </head>
    <body>
      <div class='container'>
        <h1>EEPROM ENUM 분석 보고서: <span style='color:#0078d7'>{enum_name_esc}</span></h1>
        <ul class='summary-list'>
          <li>분석 파일 수: <b>{total_files}</b></li>
          <li>함수 수: <b>{total_funcs}</b></li>
          <li>ENUM 사용 총 횟수: <b>{total_enums}</b></li>
        </ul>
        <div class='toolbar'>
          <input type='text' id='searchInput' onkeyup='filterTable()' placeholder='검색(파일명, 함수명, 코드...)'>
          <button id='darkBtn' class='dark-toggle' onclick='toggleDarkMode(this)'>🌙 다크모드</button>
        </div>
        <table id='resultTable'>
          <colgroup>
            <col style='width:18%'>
            <col style='width:18%'>
            <col style='width:14%'>
            <col style='width:auto'>
          </colgroup>
          <thead>
            <tr>
              <th onclick='sortTable(0)'>파일명</th>
              <th onclick='sortTable(1)'>함수명</th>
              <th onclick='sortTable(2)'>ENUM 사용 횟수</th>
              <th>코드 미리보기</th>
            </tr>
          </thead>
          <tbody>
    """

    html_rows = ""
    for idx, r in enumerate(results):
        file_esc = html.escape(str(r['file']))
        func_esc = html.escape(str(r['func_name']))
        enum_esc = html.escape(str(r['enum_count']))
        code_preview = r['code'][:2000].replace('<', '&lt;').replace('>', '&gt;').replace('\n', '<br>')
        html_rows += f"<tr>"
        html_rows += f"<td class='ellipsis2'><span title='{file_esc}'>{file_esc}</span></td>"
        html_rows += f"<td class='ellipsis2'><span title='{func_esc}'>{func_esc}</span></td>"
        html_rows += f"<td class='ellipsis2'><span title='{enum_esc}'>{enum_esc}</span></td>"
        html_rows += f"<td><button class='show-btn' onclick='toggleCode({idx})'>코드 보기</button>"
        html_rows += f"<pre class='code-preview' id='code_{idx}'>{code_preview}</pre></td>"
        html_rows += f"</tr>"

    html_tail = f"""
          </tbody>
        </table>
        <div style='text-align:right;color:#888;font-size:0.95em;margin-top:18px;'>
          Powered by <b>EEP Checker</b> &middot; {now}
        </div>
      </div>
    </body>
    </html>
    """

    html_content = html_head + html_rows + html_tail

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"HTML 보고서가 생성되었습니다: {filepath}")
