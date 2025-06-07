import sys
import os
import webbrowser
import math
import json
from datetime import datetime
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QFileDialog, QLabel, QMessageBox, QGridLayout,
    QTextEdit, QInputDialog, QSpinBox, QProgressBar, QMenu, QCheckBox,
    QDialog, QDialogButtonBox
)
from PySide6.QtCore import Qt, QMimeData, QThread, Signal
from PySide6.QtGui import QIcon, QClipboard, QDragEnterEvent, QDropEvent, QFontDatabase, QAction, QFont, QActionGroup
import main as eep_checker
from utils import find_c_files
import time

def load_fonts():
    """외부 폰트 로드"""
    font_dir = os.path.join(os.path.dirname(__file__), 'fonts')
    if not os.path.exists(font_dir):
        os.makedirs(font_dir)
    
    font_files = [f for f in os.listdir(font_dir) if f.endswith(('.ttf', '.otf'))]
    loaded_fonts = []
    
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
    progress = Signal(str, float)
    progress_value = Signal(int)
    finished = Signal(list, list)
    error = Signal(str)

    def __init__(self, args, target_lines_cli_param, context_lines_param, encoding):
        super().__init__()
        self.args = args
        self.target_lines_cli_param = target_lines_cli_param
        self.context_lines_param = context_lines_param
        self.encoding = encoding

    def run(self):
        try:
            sys.argv = [
                'main.py',
                '--enum', self.args['enum'],
                '--from', self.args['from_val'],
                '--to', self.args['to_val'],
                '--path', self.args['path'],
                '--encoding', self.encoding
            ]
            
            if self.target_lines_cli_param is not None:
                sys.argv.extend(['--target-lines', str(self.target_lines_cli_param)])

            if self.context_lines_param is not None:
                sys.argv.extend(['--context-lines', str(self.context_lines_param)])
            
            if self.args.get('csv', False):
                sys.argv.append('--csv')
            if self.args.get('include_headers', False):
                sys.argv.append('--include-headers')
            if self.args.get('find_caller', False):
                sys.argv.append('--find-caller')
            
            def progress_callback(status, elapsed, current_progress=None):
                self.progress.emit(status, elapsed)
                if current_progress is not None:
                    self.progress_value.emit(current_progress)
            
            prompt_files, error_logs = eep_checker.main(progress_callback=progress_callback)
            self.finished.emit(prompt_files, error_logs)
            
        except Exception as e:
            self.error.emit(str(e))

class EEPCheckerGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("eeprom enum smell")
        self.setMinimumSize(550, 380)
        
        # 아이콘 설정
        icon_path = os.path.join(os.path.dirname(__file__), 'imgs', 'eeprom.ico')
        self.app_icon = QIcon(icon_path) if os.path.exists(icon_path) else None
        if self.app_icon:
            self.setWindowIcon(self.app_icon)
        
        # 최근 분석 항목 로드
        self.recent_items = self.load_recent_items()
        self.current_encoding = 'utf-8'
        
        # CSV 출력 옵션 상태 추가
        self.csv_enabled = False
        # 호출자 분석 옵션 상태 추가
        self.include_headers_enabled = False
        self.find_caller_enabled = False
        self.context_lines = None
        
        # 메뉴바 생성
        menubar = self.menuBar()
        
        # 파일 메뉴
        file_menu = menubar.addMenu('파일')
        
        # 최근 항목 서브메뉴
        self.recent_menu = QMenu('최근 항목 열기', self)
        self.update_recent_menu()
        file_menu.addMenu(self.recent_menu)
        
        file_menu.addSeparator()
        
        # 출력 설정 메뉴 추가
        output_menu = file_menu.addMenu('출력 설정')
        
        # CSV 출력 액션
        self.csv_action = QAction('CSV 파일 생성', self, checkable=True, checked=self.csv_enabled)
        self.csv_action.triggered.connect(self.toggle_csv_output)
        output_menu.addAction(self.csv_action)
        
        # 헤더 파일 포함 액션 추가
        self.include_headers_action = QAction('헤더 파일(.h) 포함', self, checkable=True, checked=self.include_headers_enabled)
        self.include_headers_action.triggered.connect(self.toggle_include_headers)
        output_menu.addAction(self.include_headers_action)
        
        # 호출자 분석 액션 추가
        self.find_caller_action = QAction('호출자 함수 분석', self, checkable=True, checked=self.find_caller_enabled)
        self.find_caller_action.triggered.connect(self.toggle_find_caller)
        output_menu.addAction(self.find_caller_action)

        # ENUM 주변 줄 수 설정 액션
        self.context_lines_action = QAction('ENUM 주변 줄 수 설정', self, checkable=True)
        self.context_lines_action.triggered.connect(self.set_context_lines)
        output_menu.addAction(self.context_lines_action)
        
        # 인코딩 설정 메뉴 추가
        encoding_menu = file_menu.addMenu('소스코드 인코딩')
        self.encoding_group = QActionGroup(self)
        self.encoding_group.setExclusive(True)

        encodings = [('UTF-8 (기본값)', 'utf-8'), ('EUC-KR', 'euc-kr')]
        for name, enc_val in encodings:
            action = QAction(name, self, checkable=True, data=enc_val)
            if enc_val == self.current_encoding:
                action.setChecked(True)
            action.triggered.connect(self.set_encoding)
            encoding_menu.addAction(action)
            self.encoding_group.addAction(action)
        
        file_menu.addSeparator()
        
        # 프롬프트 분할 설정 액션
        self.split_settings_action = QAction('프롬프트 분할 설정', self, checkable=True)
        self.split_settings_action.setChecked(self.include_headers_enabled)
        self.split_settings_action.triggered.connect(self.show_split_settings_dialog)
        file_menu.addAction(self.split_settings_action)
        
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
            }}
            QLineEdit {{
                padding: 6px;
                border: 1px solid #ddd;
                border-radius: 4px;
                background: white;
                min-height: 20px;
            }}
            QPushButton {{
                padding: 6px 12px;
                border: none;
                border-radius: 4px;
                background-color: #0078d4;
                color: white;
                min-height: 20px;
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
            QMessageBox QPushButton {{
                min-width: 80px;
            }}
            QSpinBox {{
                padding: 4px;
            }}
            QCheckBox {{ spacing: 5px; }}
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
        browse_btn.setFixedWidth(50)  # 너비 증가
        browse_btn.clicked.connect(self.browse_path)
        
        open_btn = QPushButton("열기")
        open_btn.setObjectName("browse")
        open_btn.setFixedWidth(50)  # 동일한 너비 적용
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
                selection-background-color: #0078d4;
                selection-color: white;
            }}
        """)
        self.result_text.setFixedHeight(100)
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
        self.target_lines_config = None
        self.split_by_caller_mode_active = False
        self.lines_for_regular_prompts_in_caller_mode = 2000

        # 최근 프롬프트 파일 경로 저장용
        self.latest_prompt_paths = []

        # 이스터에그 관련 변수 추가
        self._easter_egg_count = 0
        self._last_open_click_time = 0

        self.context_lines_action.setChecked(False)
        self.update_status_bar() # 초기 상태바 업데이트

    def set_encoding(self):
        action = self.sender()
        if action and action.isChecked():
            self.current_encoding = action.data()
        self.update_status_bar()

    def browse_path(self):
        path = QFileDialog.getExistingDirectory(self, "프로젝트 폴더 선택")
        if path:
            self.path_input.setText(os.path.normpath(path))

    def open_path(self):
        """현재 경로를 파일 탐색기로 열기"""
        path = self.path_input.text()
        
        # 이스터에그: 빈 경로에서 빠르게 5번 클릭
        current_time = time.time()
        if not path:
            # 1.5초 이내의 클릭만 카운트
            if current_time - self._last_open_click_time < 1.5:
                self._easter_egg_count += 1
            else:
                self._easter_egg_count = 1
            
            self._last_open_click_time = current_time
            
            # 10번 클릭 달성
            if self._easter_egg_count >= 5:
                self._easter_egg_count = 0  # 카운트 리셋
                msg = QMessageBox(self)
                if self.app_icon:
                    msg.setWindowIcon(self.app_icon)
                msg.setWindowTitle("☕ 지갑 열기!")
                msg.setText("열기를 마니 누르셨네여<br><br>1층에 가서 커피☕ 한잔 사주시나요?<br>")
                
                # 커스텀 버튼 추가
                donate_btn = msg.addButton("커피사기 💖", QMessageBox.AcceptRole)
                donate_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #ff69b4;
                        color: white;
                        padding: 8px 15px;
                        border: none;
                        border-radius: 4px;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background-color: #ff1493;
                    }
                """)
                
                msg.addButton("다음에요 😅", QMessageBox.RejectRole)
                
                if msg.exec() == 0:  # 후원하기 선택
                    return
                return
                
        if path and os.path.exists(path):
            os.startfile(os.path.normpath(path))

    def show_split_settings_dialog(self):
        """프롬프트 분할 설정 대화상자 표시"""
        if not self.split_settings_action.isChecked():
            self.target_lines_config = None
            self.split_by_caller_mode_active = False
            self.lines_for_regular_prompts_in_caller_mode = 2000
            self.update_status_bar()
            return

        dialog = QDialog(self)
        if self.app_icon: dialog.setWindowIcon(self.app_icon)
        dialog.setWindowTitle("프롬프트 분할 설정")
        
        main_layout = QVBoxLayout(dialog)

        # 1. 호출자별 분리 체크박스
        caller_split_checkbox = QCheckBox("호출자 포함 프롬프트 개별 파일로 분리")
        caller_split_checkbox.setChecked(self.split_by_caller_mode_active and self.find_caller_enabled)
        caller_split_checkbox.setEnabled(self.find_caller_enabled)
        if not self.find_caller_enabled:
            caller_split_checkbox.setToolTip("먼저 '파일 > 출력 설정 > 호출자 함수 분석' 옵션을 켜주세요.")
        main_layout.addWidget(caller_split_checkbox)

        # 2. 나머지 프롬프트 분할 설정
        split_rest_checkbox = QCheckBox("호출자가 없는 프롬프트 분할")
        split_rest_checkbox.setChecked(isinstance(self.target_lines_config, (int, str)))
        main_layout.addWidget(split_rest_checkbox)

        # 3. Max Lines 스핀박스
        lines_widget = QWidget()
        lines_layout = QHBoxLayout(lines_widget)
        lines_label = QLabel()
        lines_spin = QSpinBox()
        lines_spin.setRange(100, 20000)
        lines_spin.setSingleStep(100)
        lines_spin.setValue(self.lines_for_regular_prompts_in_caller_mode if self.split_by_caller_mode_active else (self.target_lines_config if isinstance(self.target_lines_config, int) else 2000))
        lines_layout.addWidget(lines_label)
        lines_layout.addWidget(lines_spin)
        main_layout.addWidget(lines_widget)

        def update_lines_ui_state():
            is_caller_mode_active = caller_split_checkbox.isChecked() and self.find_caller_enabled
            is_split_rest = split_rest_checkbox.isChecked()
            
            split_rest_checkbox.setEnabled(is_caller_mode_active)
            lines_spin.setEnabled(is_split_rest)
            
            if is_caller_mode_active:
                if is_split_rest:
                    lines_label.setText("└─ 나머지 프롬프트 Max Lines:")
                    lines_spin.setEnabled(True)
                else:
                    lines_label.setText("└─ 나머지 프롬프트 분할 안함")
                    lines_spin.setEnabled(False)
            else:
                lines_label.setText("Max Lines (분할 안함 시 무시):")
                lines_spin.setEnabled(True)
                split_rest_checkbox.setChecked(True)
        
        caller_split_checkbox.stateChanged.connect(update_lines_ui_state)
        split_rest_checkbox.stateChanged.connect(update_lines_ui_state)
        update_lines_ui_state()

        # OK, Cancel 버튼
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        main_layout.addWidget(button_box)

        if dialog.exec() == QDialog.Accepted:
            self.split_settings_action.setChecked(True)
            # 호출자 모드 설정
            self.split_by_caller_mode_active = caller_split_checkbox.isChecked() and self.find_caller_enabled
            if self.split_by_caller_mode_active:
                if split_rest_checkbox.isChecked():
                    self.target_lines_config = f"caller:{lines_spin.value()}"
                    self.lines_for_regular_prompts_in_caller_mode = lines_spin.value()
                else:
                    self.target_lines_config = "caller"  # 나머지 프롬프트 분할 안함
            else:
                self.target_lines_config = lines_spin.value() if split_rest_checkbox.isChecked() else None
        else:
            self.split_settings_action.setChecked(False)
            self.target_lines_config = None
            self.split_by_caller_mode_active = False
            self.lines_for_regular_prompts_in_caller_mode = 2000

        self.update_status_bar()

    def toggle_csv_output(self):
        """CSV 출력 옵션 토글"""
        self.csv_enabled = self.csv_action.isChecked()
        self.update_status_bar()

    def toggle_include_headers(self):
        """헤더 파일 포함 옵션 토글"""
        self.include_headers_enabled = self.include_headers_action.isChecked()
        self.update_status_bar()

    def toggle_find_caller(self):
        """호출자 함수 분석 옵션 토글"""
        self.find_caller_enabled = self.find_caller_action.isChecked()
        if not self.find_caller_enabled:
            self.split_by_caller_mode_active = False
            if isinstance(self.target_lines_config, str) and self.target_lines_config.startswith("caller"):
                try:
                    self.target_lines_config = int(self.target_lines_config.split(":")[1])
                except:
                    self.target_lines_config = self.lines_for_regular_prompts_in_caller_mode
        self.update_status_bar()

    def set_context_lines(self, checked):
        if checked:
            val, ok = QInputDialog.getInt(
                self,
                "ENUM 주변 줄 수 설정",
                "ENUM 사용 전후 포함할 줄 수",
                value=self.context_lines if self.context_lines is not None else 5,
                minValue=0,
                maxValue=100,
            )
            if ok:
                self.context_lines = val
                self.context_lines_action.setChecked(True)
            else:
                self.context_lines_action.setChecked(False)
                self.context_lines = None
        else:
            self.context_lines = None
        self.update_status_bar()
        
    def update_status_bar(self):
        status_parts = []
        # 인코딩
        status_parts.append(f"인코딩: {self.current_encoding}")
        # CSV
        status_parts.append(f"CSV: {'ON' if self.csv_enabled else 'OFF'}")
        # 헤더
        status_parts.append(f"헤더: {'포함' if self.include_headers_enabled else '제외'}")
        # 호출자 분석
        status_parts.append(f"호출자 분석: {'ON' if self.find_caller_enabled else 'OFF'}")
        # 프롬프트 분할
        split_status = "OFF"
        if self.split_settings_action.isChecked():
            if self.split_by_caller_mode_active and self.find_caller_enabled:
                if isinstance(self.target_lines_config, str):
                    if self.target_lines_config == "caller":
                        split_status = "호출자별 (나머지 분할 안함)"
                    elif self.target_lines_config.startswith("caller:"):
                        split_status = f"호출자별 (나머지: {self.lines_for_regular_prompts_in_caller_mode}줄)"
            elif isinstance(self.target_lines_config, int):
                split_status = f"{self.target_lines_config}줄"
        status_parts.append(f"프롬프트 분할: {split_status}")

        context_status = "함수 전체" if self.context_lines is None else f"±{self.context_lines}줄"
        status_parts.append(f"범위: {context_status}")

        self.status_label.setText(" | ".join(status_parts))

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

        # 경로 검증 (main.py의 find_c_files 함수를 통해)
        try:
            find_c_files(self.path_input.text(), include_headers=self.include_headers_enabled)
        except ValueError as e:
            msg = QMessageBox(self)
            if self.app_icon:
                msg.setWindowIcon(self.app_icon)
            msg.setIcon(QMessageBox.Warning)
            msg.setWindowTitle("경로 오류")
            msg.setText(str(e))
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

        self.update_status_bar() # 분석 시작 전 상태 업데이트
        self.setEnabled(False)
        self.progress_bar.show()  # 진행바 표시
        self.progress_bar.setValue(0)
        
        self.analyzer = AnalyzerThread(
            args={
                'enum': self.enum_input.text(),
                'from_val': self.from_input.text(),
                'to_val': self.to_input.text(),
                'path': self.path_input.text(),
                'csv': self.csv_enabled,
                'include_headers': self.include_headers_enabled,
                'find_caller': self.find_caller_enabled
            },
            target_lines_cli_param=self.target_lines_config,
            context_lines_param=self.context_lines,
            encoding=self.current_encoding
        )
        
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
                              f"{str(e)}",
                              QMessageBox.StandardButton.Ok)

    def show_help(self):
        help_text = """
<h3>eeprom enum smell</h3>

<p><b>프로그램 소개</b></p>
C 코드에서 특정 ENUM 값 분석하는 도구에요.<br>
ENUM 값 변경 시 영향을 받는 함수들을 찾아서<br>
검토에 필요한 프롬프트를 생성해요.<br>

어쨌든 단순 사용 함수 긁어오는 거에요.<br>
LLM API 없으니까 직접 넣어서 써야해요.<br>
API 주면 구현할게요~!<br>
AX DX 하자면서 API 하나 안줘~!

<p><b>사용법</b></p>
1. 검토할 ENUM 값 적고..(다른것도 되긴 됨)<br>
2. 변경 전/후 값 적고<br>
3. 분석 시작<br>
4. HTML 파일 보고 대충 이렇구나 보고<br>
5. txt 파일이나 복사한 프롬프트 가지고 GPT한테 처리<br>

<p><b>단축키</b></p>
• 분석 시작: Ctrl+R<br>
• 프로그램 종료: Ctrl+Q, Alt+F4, Ctrl+W<br>
<br>
재미로 한번 써보세요 ^~^
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
                # 이전 버전 호환성을 위해 encoding 필드가 없는 경우 utf-8로 기본값 설정
                for item in items:
                    if 'encoding' not in item:
                        item['encoding'] = 'utf-8'
                    if 'include_headers' not in item:
                        item['include_headers'] = False
                    if 'find_caller' not in item: # 최근 항목 호환성
                        item['find_caller'] = False
                    if 'split_by_caller_mode_active' not in item: item['split_by_caller_mode_active'] = False
                    if 'target_lines_config' not in item: item['target_lines_config'] = None
                    if 'lines_for_regular_prompts_in_caller_mode' not in item: item['lines_for_regular_prompts_in_caller_mode'] = 2000
                    if 'split_settings_action_checked' not in item: item['split_settings_action_checked'] = item.get('target_lines_config') is not None
                    if 'context_lines' not in item: item['context_lines'] = None
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
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'encoding': self.current_encoding,
            'csv_enabled': self.csv_enabled,
            'include_headers': self.include_headers_action.isChecked(),  # 헤더 파일 포함 설정 저장
            'find_caller': self.find_caller_enabled,
            'target_lines_config': self.target_lines_config,
            'split_by_caller_mode_active': self.split_by_caller_mode_active,
            'lines_for_regular_prompts_in_caller_mode': self.lines_for_regular_prompts_in_caller_mode,
            'split_settings_action_checked': self.split_settings_action.isChecked(),
            'context_lines': self.context_lines,
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
            encoding = item.get('encoding', 'utf-8')
            text = f"{enum_name} ({path}) - {timestamp} [{encoding}]"
            
            action = QAction(text, self)
            action.setData(item)  # 항목 데이터 저장
            action.triggered.connect(self.load_recent_item_triggered)
            self.recent_menu.addAction(action)
        
        self.recent_menu.addSeparator()
        clear_action = self.recent_menu.addAction("최근 항목 지우기")
        clear_action.triggered.connect(self.clear_recent_items)

    def load_recent_item_triggered(self):
        """선택한 최근 항목 불러오기"""
        action = self.sender()
        item = action.data()
        
        self.enum_input.setText(item['enum'])
        self.from_input.setText(item['from'])
        self.to_input.setText(item['to'])
        self.path_input.setText(item['path'])
        
        # 인코딩 설정 복원
        loaded_encoding = item.get('encoding', 'utf-8')
        self.current_encoding = loaded_encoding
        for act in self.encoding_group.actions():
            if act.data() == loaded_encoding:
                act.setChecked(True)
                break
                
        # CSV 설정 복원
        self.csv_enabled = item.get('csv_enabled', False)
        self.csv_action.setChecked(self.csv_enabled)
        
        # 헤더 파일 포함 설정 복원
        self.include_headers_enabled = item.get('include_headers', False)
        self.include_headers_action.setChecked(self.include_headers_enabled)
        
        # 호출자 분석 설정 복원
        self.find_caller_enabled = item.get('find_caller', False)
        self.find_caller_action.setChecked(self.find_caller_enabled)
        
        # 프롬프트 분할 설정 복원
        self.split_by_caller_mode_active = item.get('split_by_caller_mode_active', False)
        self.target_lines_config = item.get('target_lines_config', None)
        self.lines_for_regular_prompts_in_caller_mode = item.get('lines_for_regular_prompts_in_caller_mode', 2000)

        self.context_lines = item.get('context_lines', None)
        self.context_lines_action.setChecked(self.context_lines is not None)

        # split_settings_action 체크 상태 결정
        self.split_settings_action.setChecked(item.get('split_settings_action_checked', self.target_lines_config is not None))
            
        self.update_status_bar()

    def clear_recent_items(self):
        """최근 항목 모두 지우기"""
        self.recent_items = []
        self.save_recent_items()
        self.update_recent_menu()
        self.update_status_bar()

    def analysis_finished(self, prompt_files, error_logs):
        """분석 완료 시 처리"""
        try:
            # 결과 텍스트 초기화
            result_text = []

            # 에러/경고 메시지 추가
            if error_logs:
                result_text.append("=== 경고/에러 메시지 ===")
                result_text.extend(error_logs)
                result_text.append("")

            # 결과 파일 정보 추가
            if prompt_files:
                # HTML 파일 찾기
                enum_name = self.enum_input.text()
                output_dir = 'outputs'
                html_files = [f for f in os.listdir(output_dir) 
                            if f.startswith(f"{enum_name}_Output_") and f.endswith('.html')]
                
                if html_files:
                    html_path = os.path.abspath(os.path.join(output_dir, sorted(html_files)[-1]))
                    all_prompt_paths = [os.path.abspath(p) for p in prompt_files]
                    
                    # 통계 정보 표시
                    with open(html_path, 'r', encoding='utf-8') as f:
                        html_content = f.read()
                        # HTML에서 통계 정보 추출
                        import re
                        stats = {}
                        stats['total_files'] = int(re.search(r'<div class="stat-value">(\d+)</div>\s*</div>\s*<div class="stat-item">\s*<div class="stat-label">함수 수', html_content).group(1))
                        stats['total_funcs'] = int(re.search(r'<div class="stat-value">(\d+)</div>\s*</div>\s*<div class="stat-item">\s*<div class="stat-label">ENUM', html_content).group(1))
                        stats['total_enums'] = int(re.search(r'<div class="stat-value">(\d+)</div>\s*</div>\s*</div>', html_content).group(1))
                        
                        result_text.append(f"=== {enum_name} 분석 결과 ===")
                        result_text.append(f"분석 파일 수: {stats['total_files']}")
                        result_text.append(f"함수 수: {stats['total_funcs']}")
                        result_text.append(f"ENUM 사용 총 횟수: {stats['total_enums']}")
                        result_text.append("")
                    
                    result_text.append("=== 생성된 파일 ===")
                    result_text.append(f"HTML: {html_path}")
                    
                    # CSV 파일 찾기 (CSV 옵션이 켜져있을 때만)
                    if self.csv_enabled:
                        csv_files = [f for f in os.listdir(output_dir)
                                   if f.startswith(f"{enum_name}_Output_") and f.endswith('.csv')]
                        if csv_files:
                            csv_path = os.path.abspath(os.path.join(output_dir, sorted(csv_files)[-1]))
                            result_text.append(f"CSV: {csv_path}")
                    
                    if len(all_prompt_paths) > 1:
                        result_text.append("프롬프트 파일:")
                        for path in sorted(all_prompt_paths):
                            result_text.append(f"- {path}")
                    else:
                        result_text.append(f"프롬프트: {all_prompt_paths[0]}")
                    
                    # 복사 버튼 활성화
                    self.copy_btn.setEnabled(True)
                    
                    # 최신 프롬프트 파일들 저장
                    self.latest_prompt_paths = sorted(all_prompt_paths)
                    
                    # HTML 파일 브라우저로 열기
                    webbrowser.open(f'file://{html_path}')
            
            # 결과 텍스트 설정
            self.result_text.setText('\n'.join(result_text))
            
        except Exception as e:
            QMessageBox.critical(self, "오류", f"결과 처리 중 오류가 발생했습니다: {str(e)}",
                               QMessageBox.StandardButton.Ok)
            self.status_label.setText('오류 발생')
        
        finally:
            self.setEnabled(True)
            self.progress_bar.hide()
            # 분석 완료 후 상태 메시지 (성공/실패에 따라 다르게)
            if not error_logs and prompt_files:
                status_msg = f"분석 완료 (인코딩: {self.current_encoding}"
                if self.csv_enabled:
                    status_msg += ", CSV 출력 포함"
                if self.find_caller_enabled:
                    status_msg += ", 호출자 분석 활성"
                status_msg += ")"
                self.status_label.setText(status_msg)
            elif not error_logs and not prompt_files:
                self.status_label.setText(f"분석 완료: 일치 항목 없음 (인코딩: {self.current_encoding})")
            # 에러가 있으면 analysis_error에서 이미 '오류 발생'으로 설정됨
            self.update_status_bar() # 최종 상태 반영

def main():
    app = QApplication(sys.argv)
    
    # 전역 폰트 설정
    loaded_fonts = load_fonts()
    default_font_name = loaded_fonts[0] if loaded_fonts else 'Malgun Gothic'
    print(f"설정된 폰트: {default_font_name}")
    f = QFont(default_font_name, 9)
    f.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    app.setFont(f)
    
    window = EEPCheckerGUI()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main() 