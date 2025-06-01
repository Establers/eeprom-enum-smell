import sys
import os
import webbrowser
import math
import json
from datetime import datetime
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QFileDialog, QLabel, QMessageBox, QGridLayout,
    QTextEdit, QInputDialog, QSpinBox, QProgressBar, QMenu
)
from PySide6.QtCore import Qt, QMimeData, QThread, Signal
from PySide6.QtGui import QIcon, QClipboard, QDragEnterEvent, QDropEvent, QFontDatabase, QAction
import main as eep_checker

def load_fonts():
    """외부 폰트 로드"""
    font_dir = os.path.join(os.path.dirname(__file__), 'fonts')
    if not os.path.exists(font_dir):
        os.makedirs(font_dir)
    
    # 폰트 파일 목록
    font_files = [f for f in os.listdir(font_dir) if f.endswith(('.ttf', '.otf'))]
    loaded_fonts = []
    
    # 각 폰트 파일 로드
    for font_file in font_files:
        font_path = os.path.join(font_dir, font_file)
        font_id = QFontDatabase.addApplicationFont(font_path)
        if font_id != -1:
            loaded_fonts.extend(QFontDatabase.applicationFontFamilies(font_id))
    
    return loaded_fonts

class PathLineEdit(QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setReadOnly(False)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if os.path.isdir(path):
                self.setText(os.path.normpath(path))

class AnalyzerThread(QThread):
    """분석 작업을 수행하는 스레드"""
    progress = Signal(str, float)  # 진행 상황과 경과 시간을 전달하는 시그널
    progress_value = Signal(int)  # 진행률을 전달하는 시그널 (0-100)
    finished = Signal(list)  # 완료 시 프롬프트 파일 목록을 전달하는 시그널
    error = Signal(str)  # 에러 메시지를 전달하는 시그널

    def __init__(self, args, target_lines):
        super().__init__()
        self.args = args
        self.target_lines = target_lines

    def run(self):
        try:
            # 명령줄 인자 설정
            sys.argv = [
                'main.py',
                '--enum', self.args['enum'],
                '--from', self.args['from'],
                '--to', self.args['to'],
                '--path', self.args['path']
            ]
            
            if self.target_lines is not None:
                sys.argv.extend(['--target-lines', str(self.target_lines)])
            
            def progress_callback(status, elapsed, progress=None):
                """진행 상황 업데이트 콜백"""
                self.progress.emit(status, elapsed)
                if progress is not None:
                    self.progress_value.emit(progress)
            
            prompt_files = eep_checker.main(progress_callback=progress_callback)
            self.finished.emit(prompt_files)
            
        except Exception as e:
            self.error.emit(str(e))

class EEPCheckerGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("eeprom enum smell")
        self.setMinimumWidth(500)
        self.setFixedHeight(360)
        
        # 폰트 로드
        loaded_fonts = load_fonts()
        default_font = loaded_fonts[0] if loaded_fonts else 'Segoe UI'

        # 아이콘 설정
        icon_path = os.path.join(os.path.dirname(__file__), 'imgs', 'eeprom.ico')
        self.app_icon = QIcon(icon_path) if os.path.exists(icon_path) else None
        if self.app_icon:
            self.setWindowIcon(self.app_icon)
        
        # 최근 분석 항목 로드
        self.recent_items = self.load_recent_items()
        
        # 메뉴바 생성
        menubar = self.menuBar()
        
        # 파일 메뉴
        file_menu = menubar.addMenu('파일')
        
        # 최근 항목 서브메뉴
        self.recent_menu = QMenu('최근 항목 열기', self)
        self.update_recent_menu()
        file_menu.addMenu(self.recent_menu)
        
        file_menu.addSeparator()
        
        # 프롬프트 분할 설정 액션
        self.split_settings_action = file_menu.addAction('프롬프트 분할 설정')
        self.split_settings_action.setCheckable(True)
        self.split_settings_action.triggered.connect(self.show_split_settings)
        
        # 분석 시작 액션
        analyze_action = file_menu.addAction('분석 시작')
        analyze_action.setShortcut('Ctrl+R')
        analyze_action.triggered.connect(self.analyze)
        
        file_menu.addSeparator()
        
        # 종료 액션
        exit_action = file_menu.addAction('종료')
        exit_action.setShortcuts(['Ctrl+Q', 'Alt+F4', 'Ctrl+W'])
        exit_action.triggered.connect(self.close)
        
        # 도움말 메뉴
        help_menu = menubar.addMenu('도움말')
        
        # 프로그램 정보
        about_action = help_menu.addAction('프로그램 정보')
        about_action.triggered.connect(self.show_help)
        
        # 라이센스 정보
        license_action = help_menu.addAction('라이센스 정보')
        license_action.triggered.connect(self.show_license)

        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: #f5f5f5;
            }}
            QMenuBar {{
                background-color: #f5f5f5;
                border-bottom: 1px solid #ddd;
                font-family: '{default_font}', 'Malgun Gothic', sans-serif;
            }}
            QMenuBar::item {{
                padding: 4px 10px;
                background-color: transparent;
            }}
            QMenuBar::item:selected {{
                background-color: #e0e0e0;
            }}
            QMenu {{
                background-color: #ffffff;
                border: 1px solid #ddd;
                font-family: '{default_font}', 'Malgun Gothic', sans-serif;
            }}
            QMenu::item {{
                padding: 4px 20px;
            }}
            QMenu::item:selected {{
                background-color: #e0e0e0;
            }}
            QLabel {{
                color: #333;
                min-width: 80px;
                font-family: '{default_font}', 'Malgun Gothic', sans-serif;
            }}
            QLineEdit {{
                padding: 6px;
                border: 1px solid #ddd;
                border-radius: 4px;
                background: white;
                min-height: 20px;
                font-family: '{default_font}', 'Malgun Gothic', sans-serif;
            }}
            QPushButton {{
                padding: 6px 12px;
                border: none;
                border-radius: 4px;
                background-color: #0078d4;
                color: white;
                min-height: 20px;
                font-family: '{default_font}', 'Malgun Gothic', sans-serif;
            }}
            QPushButton:hover {{
                background-color: #106ebe;
            }}
            QPushButton:disabled {{
                background-color: #cccccc;
            }}
            QPushButton#browse {{
                background-color: #444;
                padding: 6px 8px;
                min-width: 60px;
            }}
            QPushButton#browse:hover {{
                background-color: #666;
            }}
            QPushButton#copy {{
                background-color: #ccddcc;
            }}
            QPushButton#copy:enabled {{
                background-color: #107c41;
            }}
            QPushButton#copy:enabled:hover {{
                background-color: #0b5a2d;
            }}
            QStatusBar {{
                font-family: '{default_font}', 'Malgun Gothic', sans-serif;
            }}
            QMessageBox {{
                font-family: '{default_font}', 'Malgun Gothic', sans-serif;
            }}
            QMessageBox QPushButton {{
                min-width: 80px;
            }}
            QSpinBox {{
                font-family: '{default_font}', 'Malgun Gothic', sans-serif;
                padding: 4px;
            }}
        """)

        # 중앙 위젯 설정
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(12)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setAlignment(Qt.AlignTop)  # 상단 정렬 설정

        # 입력 필드 그리드 레이아웃
        grid = QGridLayout()
        grid.setSpacing(10)
        grid.setAlignment(Qt.AlignTop)  # 그리드도 상단 정렬

        # ENUM 이름 입력
        enum_label = QLabel("ENUM 이름")
        self.enum_input = QLineEdit()
        grid.addWidget(enum_label, 0, 0)
        grid.addWidget(self.enum_input, 0, 1, 1, 3)

        # 변경 전/후 값 입력
        from_label = QLabel("변경 전")
        self.from_input = QLineEdit()
        to_label = QLabel("변경 후")
        self.to_input = QLineEdit()
        grid.addWidget(from_label, 1, 0)
        grid.addWidget(self.from_input, 1, 1)
        grid.addWidget(to_label, 1, 2)
        grid.addWidget(self.to_input, 1, 3)

        # 프로젝트 경로 선택
        path_label = QLabel("프로젝트 경로")
        self.path_input = PathLineEdit()
        self.path_input.setPlaceholderText("폴더를 드래그하거나 경로를 입력/복사하세요")
        
        # 찾기/열기 버튼 컨테이너
        path_buttons = QHBoxLayout()
        path_buttons.setSpacing(5)
        
        browse_btn = QPushButton("찾기")
        browse_btn.setObjectName("browse")
        browse_btn.setFixedWidth(40)  # 버튼 너비 축소
        browse_btn.clicked.connect(self.browse_path)
        
        open_btn = QPushButton("열기")
        open_btn.setObjectName("browse")
        open_btn.setFixedWidth(40)  # 버튼 너비 축소
        open_btn.clicked.connect(self.open_path)
        
        path_buttons.addWidget(browse_btn)
        path_buttons.addWidget(open_btn)
        
        grid.addWidget(path_label, 2, 0)
        grid.addWidget(self.path_input, 2, 1, 1, 2)
        grid.addLayout(path_buttons, 2, 3)

        layout.addLayout(grid)

        # 버튼 영역
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        # button_layout.setAlignment(Qt.AlignLeft)  # 버튼도 왼쪽 정렬
        
        # 분석 버튼
        analyze_btn = QPushButton("분석 시작")
        analyze_btn.setFixedHeight(32)
        analyze_btn.clicked.connect(self.analyze)
        button_layout.addWidget(analyze_btn)
        
        # 복사 버튼 (처음부터 표시하되 비활성화)
        self.copy_btn = QPushButton("프롬프트 내용 복사")
        self.copy_btn.setObjectName("copy")
        self.copy_btn.clicked.connect(self.copy_prompt)
        self.copy_btn.setEnabled(False)  # 비활성화 상태로 시작
        self.copy_btn.setFixedHeight(32)
        button_layout.addWidget(self.copy_btn)
        
        layout.addLayout(button_layout)

        # 결과 영역
        result_area = QVBoxLayout()
        result_area.setSpacing(10)
        result_area.setContentsMargins(0, 0, 0, 0)
        result_area.setAlignment(Qt.AlignTop)  # 결과 영역도 상단 정렬

        # 결과 텍스트 영역
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setStyleSheet(f"""
            QTextEdit {{
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 4px;
                min-height: 60px;
                font-family: '{default_font}', 'Malgun Gothic', sans-serif;

                selection-background-color: #0078d4;
                selection-color: white;
            }}
        """)
        self.result_text.setFixedHeight(80)
        self.result_text.setPlaceholderText("분석 결과가 여기에 표시됩니다.")
        result_area.addWidget(self.result_text)

        layout.addLayout(result_area)
        
        # 진행바 (항상 표시하되 숨김 상태로 시작)
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(2)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                background-color: #f0f0f0;
                margin: 0;
                padding: 0;
            }
            QProgressBar::chunk {
                background-color: #0078d4;
            }
        """)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)
        
        # 남는 공간을 하단에 추가
        layout.addStretch(1)

        # 상태바 설정
        status_bar = self.statusBar()
        status_bar.setStyleSheet("""
            QStatusBar {
                padding: 0;
                margin: 0;
            }
        """)
        
        # 진행 상태 라벨
        self.status_label = QLabel()
        status_bar.addWidget(self.status_label, 1)

        # 프롬프트 분할 설정 초기값
        self.target_lines = None  # 기본적으로 분할하지 않음

    def browse_path(self):
        path = QFileDialog.getExistingDirectory(self, "프로젝트 폴더 선택")
        if path:
            self.path_input.setText(os.path.normpath(path))

    def open_path(self):
        """현재 경로를 파일 탐색기로 열기"""
        path = self.path_input.text()
        if path and os.path.exists(path):
            os.startfile(os.path.normpath(path))

    def show_split_settings(self):
        """프롬프트 분할 설정 대화상자 표시"""
        if not self.split_settings_action.isChecked():
            self.target_lines = None  # 분할 비활성화
            return

        msg = QMessageBox(self)
        if self.app_icon:
            msg.setWindowIcon(self.app_icon)
        msg.setWindowTitle("프롬프트 분할 설정")
        msg.setText("프롬프트를 여러 파일로 분할")
        
        # 스핀박스로 줄 수 입력받기
        layout = msg.layout()
        lines_widget = QWidget()
        lines_layout = QHBoxLayout(lines_widget)
        
        lines_label = QLabel("파일당 최대 줄 수:")
        lines_spin = QSpinBox()
        lines_spin.setRange(100, 10000)
        lines_spin.setValue(2000)  # 기본값
        lines_spin.setSingleStep(100)
        
        lines_layout.addWidget(lines_label)
        lines_layout.addWidget(lines_spin)
        
        # 메시지 박스에 위젯 추가
        layout.addWidget(lines_widget, 1, 1)
        
        msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        
        if msg.exec() == QMessageBox.Ok:
            self.target_lines = lines_spin.value()
        else:
            self.split_settings_action.setChecked(False)
            self.target_lines = None

    def analyze(self):
        if not all([self.enum_input.text(), self.from_input.text(), 
                   self.to_input.text(), self.path_input.text()]):
            msg = QMessageBox(self)
            if self.app_icon:
                msg.setWindowIcon(self.app_icon)
            msg.setIcon(QMessageBox.Warning)
            msg.setWindowTitle("입력 오류")
            msg.setText("모든 필드를<br>입력해주세요")
            msg.setStyleSheet("""
                QMessageBox {
                    background-color: #f5f5f5;
                }
                QPushButton {
                    min-width: 30px;
                    padding: 5px;
                }
            """)
            msg.exec()
            return

        # 분석 시작 전에 최근 항목에 추가
        self.add_recent_item()

        self.status_label.setText('분석 시작...')
        self.setEnabled(False)
        self.progress_bar.show()  # 진행바 표시
        self.progress_bar.setValue(0)
        
        # 분석 스레드 생성 및 시작
        self.analyzer = AnalyzerThread(
            args={
                'enum': self.enum_input.text(),
                'from': self.from_input.text(),
                'to': self.to_input.text(),
                'path': self.path_input.text()
            },
            target_lines=self.target_lines
        )
        
        # 시그널 연결
        self.analyzer.progress.connect(self.update_progress)
        self.analyzer.progress_value.connect(self.progress_bar.setValue)
        self.analyzer.finished.connect(self.analysis_finished)
        self.analyzer.error.connect(self.analysis_error)
        
        # 스레드 시작
        self.analyzer.start()

    def update_progress(self, status, elapsed):
        """진행 상황 업데이트"""
        self.status_label.setText(f"{status} ({elapsed:.1f}초)")

    def analysis_error(self, error_msg):
        """분석 중 에러 발생 시 처리"""
        QMessageBox.critical(self, "오류", f"분석 중 오류가 발생했습니다: {error_msg}",
                           QMessageBox.StandardButton.Ok)
        self.status_label.setText('오류 발생')
        self.setEnabled(True)
        self.progress_bar.hide()

    def analysis_finished(self, prompt_files):
        """분석 완료 시 처리"""
        try:
            # 결과 파일 찾기
            enum_name = self.enum_input.text()
            output_dir = 'outputs'
            html_files = [f for f in os.listdir(output_dir) 
                         if f.startswith(f"{enum_name}_Output_") and f.endswith('.html')]
            
            if html_files and prompt_files:
                html_path = os.path.abspath(os.path.join(output_dir, sorted(html_files)[-1]))
                all_prompt_paths = [os.path.abspath(p) for p in prompt_files]
                
                # 결과 표시
                result_text = f"분석 완료!\nHTML: {html_path}\n"
                if len(all_prompt_paths) > 1:
                    result_text += "프롬프트 파일:\n"
                    for path in sorted(all_prompt_paths):
                        result_text += f"{path}\n"
                else:
                    result_text += f"프롬프트: {all_prompt_paths[0]}"
                
                self.result_text.setText(result_text)
                
                # 복사 버튼 활성화
                self.copy_btn.setEnabled(True)
                
                # 최신 프롬프트 파일들 저장
                self.latest_prompt_paths = sorted(all_prompt_paths)
                
                # HTML 파일 브라우저로 열기
                webbrowser.open(f'file://{html_path}')
        
        except Exception as e:
            QMessageBox.critical(self, "오류", f"결과 처리 중 오류가 발생했습니다: {str(e)}",
                               QMessageBox.StandardButton.Ok)
            self.status_label.setText('오류 발생')
        
        finally:
            self.setEnabled(True)
            self.progress_bar.hide()

    def copy_prompt(self):
        """모든 프롬프트 내용을 순서대로 합쳐서 복사"""
        try:
            content = []
            for path in self.latest_prompt_paths:
                with open(path, 'r', encoding='utf-8') as f:
                    content.append(f.read())
            
            QApplication.clipboard().setText('\n'.join(content))
            self.status_label.setText('프롬프트가 클립보드에 복사되었습니다')
        except Exception as e:
            QMessageBox.warning(self, "복사 오류", 
                              f"프롬프트 복사 중 오류가 발생했습니다: {str(e)}",
                              QMessageBox.StandardButton.Ok)

    def show_help(self):
        help_text = """
<h3>eeprom enum smell</h3>

<p><b>프로그램 소개</b></p>
C 코드에서 특정 ENUM 값의 사용을 분석하는 도구입니다.<br>
ENUM 값 변경 시 영향을 받는 함수들을 찾아내고,<br>
검토에 필요한 프롬프트를 생성합니다.<br>
단순 사용 함수 긁어오는 겁니다.<br>
LLM API 없으니까 직접 넣어서 써야합니다.<br>
DX하는 회사에서 API도 안주는 ~

<p><b>주요 기능</b></p>
• C 코드에서 ENUM 사용 위치 검색<br>
• HTML 형식의 분석 보고서 생성<br>
• LLM 프롬프트 자동 생성<br>
• 프롬프트 자동 분할 기능<br>
• 실시간 진행 상황 표시<br>
• 드래그 & 드롭 지원

<p><b>사용 방법</b></p>
1. ENUM 이름 입력<br>
2. 변경하려는 ENUM 값 입력 (변경 전/후)<br>
3. 분석할 프로젝트 폴더 선택<br>
   - 직접 경로 입력/복사<br>
   - 폴더 드래그 & 드롭<br>
   - 찾아보기 버튼 사용<br>
4. 필요시 프롬프트 분할 설정 (파일 메뉴)<br>
5. '분석 시작' 버튼 클릭

<p><b>결과 확인</b></p>
• HTML 보고서가 자동으로 브라우저에서 열림<br>
• 프롬프트 내용은 클립보드로 복사 가능<br>
• 분할된 프롬프트는 자동으로 여러 파일로 저장<br>
• 실시간으로 진행 상황과 소요 시간 확인 가능<br>

<p><b>단축키</b></p>
• 분석 시작: Ctrl+R<br>
• 프로그램 종료: Ctrl+Q, Alt+F4, Ctrl+W
"""
        msg = QMessageBox(self)
        msg.setWindowTitle("프로그램 정보")
        msg.setText(help_text)
        if self.app_icon:
            msg.setWindowIcon(self.app_icon)
        msg.setStyleSheet("""
            QMessageBox {
                background-color: #f5f5f5;
            }
            QLabel {
                min-width: 400px;
            }
        """)
        msg.exec()

    def show_license(self):
        """라이센스 정보 표시"""
        license_text = """
<h3>오픈소스 라이브러리 정보</h3>

이 프로그램은 다음의 오픈소스 라이브러리들을 사용합니다:<br>

• PySide6 (Qt for Python) - LGPL v3<br>
• tree-sitter - MIT<br>
• tree-sitter-languages - MIT<br>
• D3.js - BSD 3-Clause<br>
• Prism.js - MIT<br>

<p><small>상세한 라이센스 정보는 프로그램의 LICENSE 파일을 참조하시기 바랍니다.</small></p>
"""
        msg = QMessageBox(self)
        msg.setWindowTitle("라이센스 정보")
        msg.setText(license_text)
        if self.app_icon:
            msg.setWindowIcon(self.app_icon)
        msg.setStyleSheet("""
            QMessageBox {
                background-color: #f5f5f5;
            }
            QLabel {
                min-width: 400px;
                min-height: 200px;
            }
        """)
        msg.exec()

    def load_recent_items(self):
        """최근 분석 항목 로드"""
        try:
            config_path = os.path.join(os.path.dirname(__file__), 'recent_items.json')
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    items = json.load(f)
                return items
        except Exception:
            pass
        return []

    def save_recent_items(self):
        """최근 분석 항목 저장"""
        try:
            config_path = os.path.join(os.path.dirname(__file__), 'recent_items.json')
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.recent_items, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"최근 항목 저장 실패: {e}")

    def add_recent_item(self):
        """현재 분석 항목을 최근 목록에 추가"""
        current_item = {
            'enum': self.enum_input.text(),
            'from': self.from_input.text(),
            'to': self.to_input.text(),
            'path': self.path_input.text(),
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # 동일한 항목이 있으면 제거
        self.recent_items = [item for item in self.recent_items 
                           if not (item['enum'] == current_item['enum'] and 
                                 item['path'] == current_item['path'])]
        
        # 최근 항목을 맨 앞에 추가
        self.recent_items.insert(0, current_item)
        
        # 최대 10개만 유지
        self.recent_items = self.recent_items[:10]
        
        # 저장 및 메뉴 업데이트
        self.save_recent_items()
        self.update_recent_menu()

    def update_recent_menu(self):
        """최근 항목 메뉴 업데이트"""
        self.recent_menu.clear()
        
        if not self.recent_items:
            no_items = self.recent_menu.addAction("최근 항목 없음")
            no_items.setEnabled(False)
            return
        
        for item in self.recent_items:
            # 메뉴 텍스트 생성
            enum_name = item['enum']
            path = os.path.basename(item['path'])
            timestamp = item.get('timestamp', '날짜 없음')
            text = f"{enum_name} ({path}) - {timestamp}"
            
            action = QAction(text, self)
            action.setData(item)  # 항목 데이터 저장
            action.triggered.connect(self.load_recent_item)
            self.recent_menu.addAction(action)
        
        self.recent_menu.addSeparator()
        clear_action = self.recent_menu.addAction("최근 항목 지우기")
        clear_action.triggered.connect(self.clear_recent_items)

    def load_recent_item(self):
        """선택한 최근 항목 불러오기"""
        action = self.sender()
        item = action.data()
        
        self.enum_input.setText(item['enum'])
        self.from_input.setText(item['from'])
        self.to_input.setText(item['to'])
        self.path_input.setText(item['path'])

    def clear_recent_items(self):
        """최근 항목 모두 지우기"""
        self.recent_items = []
        self.save_recent_items()
        self.update_recent_menu()

def main():
    app = QApplication(sys.argv)
    window = EEPCheckerGUI()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main() 