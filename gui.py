import sys
import os
import webbrowser
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QFileDialog, QLabel, QMessageBox, QGridLayout,
    QTextEdit
)
from PySide6.QtCore import Qt, QMimeData
from PySide6.QtGui import QIcon, QClipboard, QDragEnterEvent, QDropEvent
import main as eep_checker

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

class EEPCheckerGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ENUM 사용 분석기")
        self.setMinimumWidth(500)
        self.setFixedHeight(350)  # 높이 고정
        
        # 아이콘 설정
        icon_path = os.path.join(os.path.dirname(__file__), 'imgs', 'eeprom.ico')
        self.app_icon = QIcon(icon_path) if os.path.exists(icon_path) else None
        if self.app_icon:
            self.setWindowIcon(self.app_icon)
        
        # 메뉴바 생성
        menubar = self.menuBar()
        
        # 파일 메뉴
        file_menu = menubar.addMenu('파일')
        
        # 분석 시작 액션
        analyze_action = file_menu.addAction('분석 시작')
        analyze_action.setShortcut('Ctrl+R')
        analyze_action.triggered.connect(self.analyze)
        
        # 종료 액션
        exit_action = file_menu.addAction('종료')
        exit_action.setShortcut('Alt+F4')
        exit_action.triggered.connect(self.close)
        
        # 도움말 메뉴
        help_menu = menubar.addMenu('도움말')
        
        # 프로그램 정보
        about_action = help_menu.addAction('프로그램 정보')
        about_action.triggered.connect(self.show_help)

        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QMenuBar {
                background-color: #f5f5f5;
                border-bottom: 1px solid #ddd;
            }
            QMenuBar::item {
                padding: 4px 10px;
                background-color: transparent;
            }
            QMenuBar::item:selected {
                background-color: #e0e0e0;
            }
            QMenu {
                background-color: #ffffff;
                border: 1px solid #ddd;
            }
            QMenu::item {
                padding: 4px 20px;
            }
            QMenu::item:selected {
                background-color: #e0e0e0;
            }
            QLabel {
                font-size: 12px;
                color: #333;
                min-width: 80px;
            }
            QLineEdit {
                padding: 6px;
                border: 1px solid #ddd;
                border-radius: 4px;
                background: white;
                font-size: 12px;
                min-height: 20px;
            }
            QPushButton {
                padding: 6px 12px;
                border: none;
                border-radius: 4px;
                background-color: #0078d4;
                color: white;
                font-size: 12px;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
            QPushButton#browse {
                background-color: #444;
                padding: 6px 8px;
                min-width: 60px;
            }
            QPushButton#browse:hover {
                background-color: #666;
            }
            QPushButton#copy {
                background-color: #ccddcc;  /* 비활성화 상태의 초기 색상 */
            }
            QPushButton#copy:enabled {
                background-color: #107c41;  /* 활성화 상태의 색상 */
            }
            QPushButton#copy:enabled:hover {
                background-color: #0b5a2d;
            }
            QStatusBar {
                font-size: 11px;
            }
        """)

        # 중앙 위젯 설정
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(12)
        layout.setContentsMargins(15, 15, 15, 15)

        # 입력 필드 그리드 레이아웃
        grid = QGridLayout()
        grid.setSpacing(10)  # 그리드 간격 고정

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
        browse_btn = QPushButton("찾기")
        browse_btn.setObjectName("browse")
        browse_btn.clicked.connect(self.browse_path)
        grid.addWidget(path_label, 2, 0)
        grid.addWidget(self.path_input, 2, 1, 1, 2)
        grid.addWidget(browse_btn, 2, 3)

        layout.addLayout(grid)

        # 버튼 영역
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)  # 버튼 간격 고정
        
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
        result_area.setSpacing(10)  # 간격 고정
        result_area.setContentsMargins(0, 0, 0, 15)  # 상하 여백 고정

        # 결과 텍스트 영역 (QTextEdit 사용)
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)  # 읽기 전용
        self.result_text.setStyleSheet("""
            QTextEdit {
                padding: 15px;
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 4px;
                min-height: 60px;
                font-family: 'Segoe UI', 'Malgun Gothic', sans-serif;
                font-size: 12px;
                selection-background-color: #0078d4;
                selection-color: white;
            }
        """)
        self.result_text.setFixedHeight(80)  # 높이 고정
        self.result_text.setPlaceholderText("분석 결과가 여기에 표시됩니다.")
        result_area.addWidget(self.result_text)

        layout.addLayout(result_area)
        layout.addStretch()

        # 상태 표시줄
        self.statusBar().showMessage('준비')

    def browse_path(self):
        path = QFileDialog.getExistingDirectory(self, "프로젝트 폴더 선택")
        if path:
            self.path_input.setText(os.path.normpath(path))

    def analyze(self):
        # 입력 검증
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

        self.statusBar().showMessage('분석 중...')
        self.setEnabled(False)
        
        try:
            # 기존 main.py의 분석 로직 실행
            sys.argv = [
                'main.py',
                '--enum', self.enum_input.text(),
                '--from', self.from_input.text(),
                '--to', self.to_input.text(),
                '--path', self.path_input.text()
            ]
            eep_checker.main()

            # 결과 파일 찾기
            enum_name = self.enum_input.text()
            output_dir = 'outputs'
            html_files = [f for f in os.listdir(output_dir) 
                         if f.startswith(f"{enum_name}_Output_") and f.endswith('.html')]
            prompt_files = [f for f in os.listdir(output_dir) 
                          if f.startswith(f"{enum_name}_LLM_Prompts_") and f.endswith('.txt')]

            if html_files and prompt_files:
                html_path = os.path.abspath(os.path.join(output_dir, sorted(html_files)[-1]))
                prompt_path = os.path.abspath(os.path.join(output_dir, sorted(prompt_files)[-1]))
                
                # 결과 표시
                self.result_text.setText(
                    f"분석 완료!\nHTML: {html_path}\n프롬프트: {prompt_path}"
                )
                
                # 복사 버튼 활성화
                self.copy_btn.setEnabled(True)
                
                # 최신 프롬프트 파일 저장
                self.latest_prompt_path = prompt_path
                
                # HTML 파일 브라우저로 열기
                webbrowser.open(f'file://{html_path}')

            self.statusBar().showMessage('분석 완료')
            
        except Exception as e:
            QMessageBox.critical(self, "오류", f"분석 중 오류가 발생했습니다: {str(e)}",
                               QMessageBox.StandardButton.Ok)
            self.statusBar().showMessage('오류 발생')
        
        finally:
            self.setEnabled(True)

    def copy_prompt(self):
        try:
            with open(self.latest_prompt_path, 'r', encoding='utf-8') as f:
                content = f.read()
            QApplication.clipboard().setText(content)
            self.statusBar().showMessage('프롬프트가 클립보드에 복사되었습니다', 3000)
        except Exception as e:
            QMessageBox.warning(self, "복사 오류", 
                              f"프롬프트 복사 중 오류가 발생했습니다: {str(e)}",
                              QMessageBox.StandardButton.Ok)

    def show_help(self):
        help_text = """
<h3>ENUM 사용 분석기</h3>

<p><b>프로그램 소개</b></p>
이 프로그램은 C 코드에서 특정 ENUM 값의 사용을 분석하는 도구입니다.<br>
ENUM 값 변경 시 영향을 받는 함수들을 찾아내고,<br>
변경에 필요한 프롬프트를 생성합니다.<br>

<p><b>주요 기능</b></p>
• C 코드에서 ENUM 사용 위치 검색<br>
• HTML 형식의 분석 보고서 생성<br>
• LLM 프롬프트 자동 생성<br>
• 드래그 & 드롭 지원<br>

<p><b>사용 방법</b></p>
1. ENUM 이름 입력<br>
2. 변경하려는 ENUM 값 입력 (변경 전/후)<br>
3. 분석할 프로젝트 폴더 선택<br>
   - 직접 경로 입력/복사<br>
   - 폴더 드래그 & 드롭<br>
   - 찾아보기 버튼 사용<br>
4. '분석 시작' 버튼 클릭<br>

<p><b>결과 확인</b></p>
• HTML 보고서가 자동으로 브라우저에서 열림<br>
• 프롬프트 내용은 클립보드로 복사 가능<br>

<p><b>개발자 정보</b></p>
개발자: 박재환
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

def main():
    app = QApplication(sys.argv)
    window = EEPCheckerGUI()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main() 