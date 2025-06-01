from tree_sitter_languages import get_language, get_parser
from tree_sitter import Language, Parser

c_lang = get_language('c')
parser = get_parser('c')

# 함수 정의와 identifier를 모두 찾는 쿼리로 수정
FUNCTION_QUERY = """
(function_definition
  declarator: (function_declarator
    declarator: (identifier) @function_name)
  body: (compound_statement) @function_body)

(identifier) @identifier
"""

# 쿼리 객체 생성
query = c_lang.query(FUNCTION_QUERY)

def has_enum_in_function(node, code, target_enum):
    """특정 노드 내에서 ENUM 사용을 검사하고 횟수를 계산"""
    found = False
    enum_count = 0
    
    # 주석이나 문자열을 제외한 실제 코드에서의 ENUM 사용만 카운트
    def visit_node(node):
        count = 0
        # 주석이나 문자열은 건너뜀
        if node.type in ['comment', 'string_literal']:
            return 0
            
        # identifier인 경우 ENUM 체크
        if node.type == 'identifier':
            text = code[node.start_byte:node.end_byte].decode(errors='ignore')
            if text == target_enum:
                # 부모 노드가 함수 호출이나 변수 선언 등인지 확인
                parent = node.parent
                if parent and parent.type not in ['comment', 'string_literal']:
                    count += 1
        
        # 자식 노드들 재귀적으로 방문
        for child in node.children:
            count += visit_node(child)
            
        return count
    
    enum_count = visit_node(node)
    found = enum_count > 0
    
    return found, enum_count

def find_identifier_in_declarator(node, code):
    """declarator 노드에서 identifier를 찾는 헬퍼 함수"""
    if node.type == 'identifier':
        return code[node.start_byte:node.end_byte].decode(errors='ignore')
    for child in node.children:
        result = find_identifier_in_declarator(child, code)
        if result:
            return result
    return None

def debug_print_function_node(node, code, depth=0, debug=False):
    """디버깅용: 함수 정의 노드의 구조를 출력"""
    if not node or not debug:
        return
    
    indent = '  ' * depth
    node_text = code[node.start_byte:node.end_byte].decode(errors='ignore') if code else ''
    print(f"{indent}{node.type} [{node.start_byte}:{node.end_byte}] {node_text[:50]}")
    
    # 필드 정보 출력
    field_names = ['type', 'declarator', 'value', 'name', 'body', 'condition', 'consequence', 'alternative']
    for field_name in field_names:
        field = node.child_by_field_name(field_name)
        if field:
            print(f"{indent}  Field '{field_name}':")
            debug_print_function_node(field, code, depth + 2, debug=debug)
    
    # 일반 자식 노드 출력
    for child in node.children:
        if child not in [node.child_by_field_name(f) for f in field_names]:
            debug_print_function_node(child, code, depth + 1, debug=debug)

def extract_functions_with_enum(node, code, target_enum, debug=False):
    results = []
    
    # 함수 정의나 구조체 정의인 경우
    if node.type in ['function_definition', 'struct_specifier']:
        if debug:
            print("\nNode Structure:")
            debug_print_function_node(node, code, debug=debug)
        
        # 이름 찾기
        name = None
        if node.type == 'function_definition':
            declarator = node.child_by_field_name('declarator')
            if declarator:
                name = find_identifier_in_declarator(declarator, code)
        elif node.type == 'struct_specifier':
            name_node = node.child_by_field_name('name')
            if name_node:
                name = code[name_node.start_byte:name_node.end_byte].decode(errors='ignore')
            else:
                # typedef struct의 경우 이름이 없을 수 있음
                name = "(anonymous struct)"
        
        found, enum_count = has_enum_in_function(node, code, target_enum)
        if found:
            node_code = code[node.start_byte:node.end_byte].decode(errors='ignore')
            results.append({
                'func_name': name or '(이름없음)',
                'code': node_code,
                'enum_count': enum_count
            })
    
    for child in node.children:
        results.extend(extract_functions_with_enum(child, code, target_enum, debug=debug))
    return results

def find_all_identifiers(node, code, debug=False):
    """노드에서 모든 identifier를 찾아서 반환 (주석과 문자열 제외)"""
    identifiers = []
    
    def visit_node(node):
        results = []
        # 주석이나 문자열은 건너뜀
        if node.type in ['comment', 'string_literal']:
            return results
            
        if node.type == 'identifier':
            text = code[node.start_byte:node.end_byte].decode(errors='ignore')
            if debug:
                print(f"Found identifier: {text}")
            results.append((node, text))
        
        # 자식 노드들 재귀적으로 방문
        for child in node.children:
            results.extend(visit_node(child))
            
        return results
    
    return visit_node(node)

def has_enum_in_node(node, code, target_enum, debug=False):
    """특정 노드 내에서 ENUM 사용을 검사 (재귀적)"""
    found = False
    enum_count = 0
    
    # 노드 내의 모든 identifier 찾기 (주석과 문자열 제외)
    identifiers = find_all_identifiers(node, code, debug)
    
    # 각 identifier가 target_enum과 일치하는지 검사
    for node, text in identifiers:
        if text == target_enum:
            # 부모 노드가 주석이나 문자열이 아닌 경우에만 카운트
            parent = node.parent
            if parent and parent.type not in ['comment', 'string_literal']:
                if debug:
                    parent_type = parent.type if parent else 'none'
                    print(f"Found ENUM '{target_enum}' at position {node.start_byte} in {parent_type}")
                found = True
                enum_count += 1
    
    return found, enum_count

def debug_print_tree(node, code, depth=0):
    """디버깅용: AST 구조를 출력"""
    indent = '  ' * depth
    node_text = code[node.start_byte:node.end_byte].decode(errors='ignore').replace('\n', '\\n')[:50]
    print(f"{indent}{node.type} [{node.start_byte}:{node.end_byte}] {node_text}")
    
    # 알려진 필드 이름들로 필드 정보 출력
    field_names = ['type', 'declarator', 'value', 'name', 'body', 'condition', 'consequence', 'alternative']
    for field_name in field_names:
        field_node = node.child_by_field_name(field_name)
        if field_node:
            print(f"{indent}  Field '{field_name}': {field_node.type}")
    
    for child in node.children:
        debug_print_tree(child, code, depth + 1)

def extract_functions_with_enum_file(code, target_enum, file_name=None, debug=False, query_mode=False):
    code_bytes = bytes(code, "utf8")
    tree = parser.parse(code_bytes)

    if query_mode:
        # 쿼리 방식 (실험용, 기본값 아님)
        captures = query.captures(tree.root_node)
        function_enum_usage = {}
        current_function = None
        for capture_name, node in captures:
            if capture_name == 'function_name':
                current_function = code_bytes[node.start_byte:node.end_byte].decode(errors='ignore')
                function_enum_usage[current_function] = {
                    'enum_count': 0,
                    'body_node': None,
                    'start_byte': node.start_byte
                }
            elif capture_name == 'function_body':
                if current_function:
                    function_enum_usage[current_function]['body_node'] = node
            elif capture_name == 'identifier':
                identifier_text = code_bytes[node.start_byte:node.end_byte].decode(errors='ignore')
                if identifier_text == target_enum:
                    parent = node
                    while parent:
                        if parent.type == 'function_definition':
                            func_declarator = parent.child_by_field_name('declarator')
                            if func_declarator:
                                func_name = find_identifier_in_declarator(func_declarator, code_bytes)
                                if func_name:
                                    if func_name not in function_enum_usage:
                                        function_enum_usage[func_name] = {
                                            'enum_count': 0,
                                            'body_node': parent.child_by_field_name('body'),
                                            'start_byte': parent.start_byte
                                        }
                                    function_enum_usage[func_name]['enum_count'] += 1
                            break
                        parent = parent.parent
        results = []
        for func_name, usage in function_enum_usage.items():
            if usage['enum_count'] > 0 and usage['body_node']:
                func_code = code_bytes[usage['body_node'].start_byte:usage['body_node'].end_byte].decode(errors='ignore')
                results.append({
                    'func_name': func_name,
                    'code': func_code,
                    'enum_count': usage['enum_count']
                })
        for r in results:
            r['file'] = file_name or ''
        return results
    else:
        # 기존 AST 순회 방식
        if debug:
            print("\nParsed tree structure:")
            debug_print_tree(tree.root_node, code_bytes)
            print("\nSearching for functions...")
        results = extract_functions_with_enum(tree.root_node, code_bytes, target_enum, debug=debug)
        for r in results:
            r['file'] = file_name or ''
        if debug:
            if results:
                print(f"\nFound {len(results)} functions using the target ENUM")
                for r in results:
                    print(f"- {r['func_name']} ({r['enum_count']} uses)")
            else:
                print("\nNo functions with target ENUM found")
        return results