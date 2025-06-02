import html
import datetime
import os
import json
from typing import List, Dict

def save_html_report(enum_name: str, results: List[Dict], output_dir: str = '.'):
    now = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{enum_name}_Output_{now}.html"
    filepath = os.path.join(output_dir, filename)

    total_files = len(set(r['file'] for r in results))
    total_funcs = len(results)
    total_enums = sum(r['enum_count'] for r in results)
    enum_name_esc = html.escape(enum_name)

    # 차트 데이터 준비
    file_data = {}
    for r in results:
        if r['file'] not in file_data:
            file_data[r['file']] = 0
        file_data[r['file']] += r['enum_count']
    
    chart_data = {
        'files': list(file_data.keys()),
        'counts': list(file_data.values())
    }

    # JavaScript에서 사용할 데이터를 JSON으로 변환
    chart_data_json = json.dumps(chart_data)
    results_json = json.dumps([{
        'func_name': r['func_name'],
        'enum_count': r['enum_count']
    } for r in results])

    # 테이블 행 HTML 생성
    table_rows = []
    for i, r in enumerate(results):
        row = f"""
        <tr>
            <td title="{html.escape(str(r['file']))}">{html.escape(str(r['file']))}</td>
            <td title="{html.escape(str(r['func_name']))}">{html.escape(str(r['func_name']))}</td>
            <td>{html.escape(str(r['enum_count']))}</td>
            <td><button class="btn toggle-btn" onclick="toggleCode({i})" data-state="closed">보기</button></td>
        </tr>
        <tr id="code_{i}" class="code-row" style="display:none">
            <td colspan="4">
                <div class="code-container">
                    <div class="code-preview">
                        <pre class="line-numbers"><code class="language-c">{html.escape(r['code'])}</code></pre>
                    </div>
                </div>
            </td>
        </tr>
        """
        table_rows.append(row)

    html_content = f"""
    <!DOCTYPE html>
    <html lang='ko'>
    <head>
        <meta charset='utf-8'>
        <title>{enum_name_esc} 분석 보고서</title>
        <meta name='viewport' content='width=device-width, initial-scale=1'>
        <script src="https://d3js.org/d3.v7.min.js"></script>
        <link href="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/themes/prism-tomorrow.min.css" rel="stylesheet" />
        <link href="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/plugins/line-numbers/prism-line-numbers.min.css" rel="stylesheet" />
        <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/prism.min.js"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-c.min.js"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/plugins/line-numbers/prism-line-numbers.min.js"></script>
        <style>
            :root {{
                --primary: #0078d7;
                --bg: #f7f7fa;
                --fg: #222;
                --panel: #fff;
                --border: #e0e0e0;
                --hover: #f0f6ff;
            }}
            
            body {{
                font-family: 'Segoe UI', 'Malgun Gothic', Arial, sans-serif;
                background: var(--bg);
                color: var(--fg);
                margin: 0;
                padding: 20px;
                line-height: 1.5;
            }}
            
            .container {{
                max-width: 1200px;
                margin: 0 auto;
            }}

            .header {{
                background: var(--panel);
                padding: 24px;
                border-radius: 12px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.05);
                margin-bottom: 20px;
            }}

            h1 {{
                margin: 0;
                font-size: 1.8em;
                color: var(--fg);
            }}

            .stats {{
                display: flex;
                gap: 20px;
                margin-top: 20px;
            }}

            .stat-item {{
                background: var(--bg);
                padding: 12px 20px;
                border-radius: 8px;
                flex: 1;
            }}

            .stat-label {{
                font-size: 0.9em;
                color: #666;
            }}

            .stat-value {{
                font-size: 1.4em;
                font-weight: bold;
                color: var(--primary);
                margin-top: 4px;
            }}

            .content-grid {{
                display: grid;
                grid-template-columns: 350px 1fr;
                gap: 20px;
                align-items: start;
            }}

            .chart-container {{
                background: var(--panel);
                padding: 20px;
                border-radius: 12px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.05);
            }}

            .chart-title {{
                font-size: 1.1em;
                color: var(--fg);
                margin-bottom: 15px;
                text-align: center;
            }}

            .table-container {{
                background: var(--panel);
                padding: 20px;
                border-radius: 12px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.05);
                overflow-x: auto;
            }}

            table {{
                width: 100%;
                border-collapse: collapse;
                table-layout: fixed;
            }}

            th, td {{
                padding: 12px;
                text-align: left;
                border-bottom: 1px solid var(--border);
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }}

            td:first-child, td:nth-child(2) {{
                max-width: 200px;
            }}

            .code-preview {{
                position: relative;
                margin: 0;
                font-family: 'Fira Code', 'Consolas', 'Menlo', monospace;
                font-size: 13px;
                line-height: 1.4;
                background: #1e1e1e;
                border-radius: 4px;
                overflow: auto;
            }}

            .code-preview pre {{
                margin: 0;
                padding: 15px;
            }}

            .code-preview code {{
                font-family: inherit;
                white-space: pre;
                word-break: normal;
                word-wrap: normal;
            }}

            .code-row {{
                background: var(--bg);
            }}

            .code-row > td {{
                padding: 0;
            }}

            .code-container {{
                position: relative;
                margin: 10px;
            }}

            @media (max-width: 1200px) {{
                .content-grid {{
                    grid-template-columns: 1fr;
                }}
                
                .chart-container {{
                    max-width: 400px;
                    margin: 0 auto;
                }}
            }}

            [data-theme="dark"] .code-preview {{
                background: #1e1e1e;
            }}

            .token.comment {{
                color: #6a9955;
            }}
            .token.function {{
                color: #dcdcaa;
            }}
            .token.keyword {{
                color: #569cd6;
            }}
            .token.string {{
                color: #ce9178;
            }}
            .token.number {{
                color: #b5cea8;
            }}

            .btn {{
                background: var(--primary);
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                cursor: pointer;
                font-size: 0.9em;
            }}

            .btn:hover {{
                opacity: 0.9;
            }}

            .legend {{
                margin-top: 15px;
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
                justify-content: center;
            }}

            .legend-item {{
                display: flex;
                align-items: center;
                gap: 6px;
                font-size: 0.9em;
            }}

            .legend-color {{
                width: 12px;
                height: 12px;
                border-radius: 2px;
            }}

            [data-theme="dark"] {{
                --bg: #1a1a1a;
                --fg: #ffffff;
                --panel: #2d2d2d;
                --border: #404040;
                --hover: #353535;
            }}

            /* 라인 번호 스타일 */
            .line-numbers .line-numbers-rows {{
                border-right: 2px solid #404040;
                padding-right: 10px;
            }}

            .line-numbers-rows > span:before {{
                color: #808080;
            }}

            /* 검색 필드 스타일 */
            .search-container {{
                margin-bottom: 15px;
                display: flex;
                gap: 10px;
                align-items: center;
            }}

            .search-field {{
                flex: 1;
                padding: 8px 12px;
                border: 1px solid var(--border);
                border-radius: 4px;
                font-size: 14px;
            }}

            .search-type {{
                padding: 8px;
                border: 1px solid var(--border);
                border-radius: 4px;
                background: white;
            }}

            /* 검색 결과 하이라이트 */
            .highlight {{
                background-color: #fff3cd;
            }}

            /* 숨겨진 행 */
            tr.hidden {{
                display: none;
            }}

            /* 버튼 상태별 스타일 */
            .toggle-btn[data-state="closed"] {{
                background-color: var(--primary);
            }}
            .toggle-btn[data-state="opened"] {{
                background-color: #666;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🙂 ENUM: <span style="color:var(--primary)">{enum_name_esc}</span></h1>
                <div class="stats">
                    <div class="stat-item">
                        <div class="stat-label">분석 파일 수</div>
                        <div class="stat-value">{total_files}</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-label">함수 수</div>
                        <div class="stat-value">{total_funcs}</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-label">ENUM 사용 총 횟수</div>
                        <div class="stat-value">{total_enums}</div>
                    </div>
                </div>
            </div>

            <div class="content-grid">
                <div class="chart-container">
                    <div class="chart-title">파일별 ENUM 사용 분포</div>
                    <div id="pieChart"></div>
                    <div id="legend" class="legend"></div>
                </div>

                <div class="table-container">
                    <div class="search-container">
                        <select class="search-type" id="searchType">
                            <option value="file">파일명</option>
                            <option value="function">함수명</option>
                        </select>
                        <input type="text" class="search-field" id="searchField" 
                               placeholder="검색어를 입력하세요..." />
                    </div>
                    <table id="resultTable">
                        <thead>
                            <tr>
                                <th>파일명</th>
                                <th>함수명</th>
                                <th style="width:100px">사용 횟수</th>
                                <th style="width:100px">코드 보기</th>
                            </tr>
                        </thead>
                        <tbody>
                            {''.join(table_rows)}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <script>
        // 차트 데이터
        const chartData = {chart_data_json};
        
        // 파이 차트
        const width = 300;
        const height = 300;
        const radius = Math.min(width, height) / 2;

        const svg = d3.select("#pieChart")
            .append("svg")
            .attr("width", width)
            .attr("height", height)
            .append("g")
            .attr("transform", `translate(${{width/2}}, ${{height/2}})`);

        const color = d3.scaleOrdinal()
            .domain(chartData.files)
            .range(['#2196F3', '#FF9800', '#4CAF50', '#F44336', '#9C27B0', '#00BCD4', '#FFEB3B', '#795548']);

        const pie = d3.pie()
            .value(d => d.value)
            .sort(null);

        const arc = d3.arc()
            .innerRadius(0)
            .outerRadius(radius * 0.65);

        const outerArc = d3.arc()
            .innerRadius(radius * 0.7)
            .outerRadius(radius * 0.7);

        const data_ready = pie(chartData.files.map((d, i) => ({{
            key: d,
            value: chartData.counts[i]
        }})));

        // 파이 조각
        const slices = svg.selectAll('path')
            .data(data_ready)
            .join('path')
            .attr('d', arc)
            .attr('fill', d => color(d.data.key))
            .style("opacity", 0.8)
            .style("stroke", "white")
            .style("stroke-width", "2px");

        // 레전드 생성
        const legend = d3.select("#legend")
            .selectAll(".legend-item")
            .data(data_ready)
            .join("div")
            .attr("class", "legend-item");

        legend.append("div")
            .attr("class", "legend-color")
            .style("background-color", d => color(d.data.key));

        legend.append("div")
            .text(d => `${{d.data.key}} (${{d.data.value}}회)`);

        // 툴팁
        const tooltip = d3.select("body")
            .append("div")
            .style("position", "absolute")
            .style("background", "rgba(0,0,0,0.8)")
            .style("color", "white")
            .style("padding", "8px")
            .style("border-radius", "4px")
            .style("font-size", "12px")
            .style("pointer-events", "none")
            .style("opacity", 0);

        slices
            .on("mouseover", function(event, d) {{
                d3.select(this)
                    .style("opacity", 1);
                tooltip.transition()
                    .duration(200)
                    .style("opacity", .9);
                tooltip.html(
                    `파일: ${{d.data.key}}<br/>` +
                    `사용 횟수: ${{d.data.value}}회`
                )
                .style("left", (event.pageX + 10) + "px")
                .style("top", (event.pageY - 28) + "px");
            }})
            .on("mouseout", function() {{
                d3.select(this)
                    .style("opacity", 0.8);
                tooltip.transition()
                    .duration(500)
                    .style("opacity", 0);
            }});

        function toggleCode(idx) {{
            const codeRow = document.getElementById(`code_${{idx}}`);
            const btn = document.querySelector(`button[onclick="toggleCode(${{idx}})"]`);
            const isOpening = codeRow.style.display === 'none';
            
            codeRow.style.display = isOpening ? 'table-row' : 'none';
            btn.textContent = isOpening ? '접기' : '보기';
            btn.dataset.state = isOpening ? 'opened' : 'closed';
            
            if (isOpening) {{
                // 코드가 표시될 때 Prism.js 하이라이팅 실행
                Prism.highlightAllUnder(codeRow);
            }}
        }}

        // 검색 기능
        const searchField = document.getElementById('searchField');
        const searchType = document.getElementById('searchType');
        const resultTable = document.getElementById('resultTable');
        const tbody = resultTable.getElementsByTagName('tbody')[0];
        const rows = tbody.getElementsByTagName('tr');

        function filterTable() {{
            const searchText = searchField.value.toLowerCase();
            const type = searchType.value;
            let columnIndex = type === 'file' ? 0 : 1;
            
            for (let i = 0; i < rows.length; i += 2) {{  // 2씩 증가 (코드 행 제외)
                const cell = rows[i].getElementsByTagName('td')[columnIndex];
                const cellText = cell.textContent.toLowerCase();
                const isMatch = cellText.includes(searchText);
                
                // 메인 행 표시/숨김
                rows[i].classList.toggle('hidden', !isMatch);
                
                // 코드 행 처리
                if (i + 1 < rows.length) {{
                    const codeRow = rows[i + 1];
                    const btn = rows[i].querySelector('.toggle-btn');
                    
                    if (!isMatch) {{
                        // 검색 결과에 없으면 코드를 접고 행을 숨김
                        codeRow.style.display = 'none';
                        codeRow.classList.add('hidden');
                        if (btn) {{
                            btn.textContent = '보기';
                            btn.dataset.state = 'closed';
                        }}
                    }} else {{
                        codeRow.classList.remove('hidden');
                    }}
                }}
                
                // 검색어 하이라이트
                if (searchText) {{
                    cell.innerHTML = cell.textContent.replace(
                        new RegExp(searchText, 'gi'),
                        match => `<span class="highlight">${{match}}</span>`
                    );
                }} else {{
                    cell.innerHTML = cell.textContent;
                }}
            }}
        }}

        searchField.addEventListener('input', filterTable);
        searchType.addEventListener('change', filterTable);
        </script>
    </body>
    </html>
    """

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"HTML 보고서가 생성되었습니다: {filepath}")
