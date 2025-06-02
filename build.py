import PyInstaller.__main__
import os
import shutil

def build_app():
    # 기존 빌드 폴더 정리
    if os.path.exists('dist'):
        shutil.rmtree('dist')
    if os.path.exists('build'):
        shutil.rmtree('build')
        
    # PyInstaller 옵션 설정
    opts = [
        'gui.py',                     # 메인 스크립트
        '--name=eeprom_enum_smell',   # 실행 파일 이름
        '--onedir',                   # onedir 모드
        '--windowed',                 # 콘솔창 없이 실행
        '--icon=imgs/eeprom.ico',     # 아이콘
        '--add-data=imgs;imgs',       # 이미지 리소스
        '--add-data=fonts;fonts',     # 폰트 리소스
        '--hidden-import=tree_sitter',
        '--hidden-import=tree_sitter_languages',
        '--collect-all=tree_sitter_languages',  # tree-sitter 관련 파일 모두 포함
        '--copy-metadata=tree_sitter_languages',  # 메타데이터 포함
        '--copy-metadata=tree_sitter',
        '--noconfirm',               # 기존 빌드 폴더 자동 삭제
        '--debug=imports',           # 임포트 디버그 정보 출력
    ]
    
    # PyInstaller 실행
    PyInstaller.__main__.run(opts)
    
    # outputs 폴더 생성
    dist_path = os.path.join('dist', 'eeprom_enum_smell')
    os.makedirs(os.path.join(dist_path, 'outputs'), exist_ok=True)
    
    print("\n=== 빌드 완료 ===")
    print(f"실행 파일 위치: {os.path.abspath(dist_path)}")
    print("\n주의: tree-sitter 언어 파일이 필요할 수 있습니다.")
    print("처음 실행 시 자동으로 다운로드됩니다.")

if __name__ == '__main__':
    build_app() 