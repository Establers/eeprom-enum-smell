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

def find_identifier_in_declarator(node, code):
    """declarator 노드에서 identifier(변수명 혹은 함수명)를 찾아 반환"""
    if node.type == 'identifier':
        return code[node.start_byte:node.end_byte].decode(errors='ignore')
    for child in node.children:
        result = find_identifier_in_declarator(child, code)
        if result:
            return result
    return None

def get_enclosing_function_name(node, code):
    """
    현재 노드에서 가장 가까운 부모 중 function_definition이 있으면
    그 함수 이름을 리턴. 없으면 None.
    """
    parent = node.parent
    while parent:
        if parent.type == 'function_definition':
            decl = parent.child_by_field_name('declarator')
            if decl: # declarator가 없을 수도 있음 (예: 익명 함수)
                 return find_identifier_in_declarator(decl, code)
        parent = parent.parent
    return None

def collect_enum_global_vars(root, code, target_enum):
    """
    전역 선언부(translation_unit 아래의 declaration)와 struct 내부 선언에서
    target_enum을 타입으로 쓰고 있는 변수 이름들을 모두 수집하여 반환한다.
    """
    enum_vars = set()

    # helper: declaration 노드 안에서 "target_enum"을 쓰고 있는지 판별하고, 그 선언의 declarator에서 변수 이름 추출
    def check_declaration(decl_node):
        found_enum_type = False
        # 먼저 재귀로 자식 탐색 (identifier가 하위 노드에 있을 수 있음)
        for child in decl_node.children:
            if child.type == 'identifier':
                text = code[child.start_byte:child.end_byte].decode(errors='ignore')
                if text == target_enum:
                    found_enum_type = True
                    break
            # declaration 내부의 다른 declaration은 검사하지 않음 (무한 루프 방지)
            elif child.type not in ['declaration', 'field_declaration']:
                f, var = check_declaration(child) # 자식 노드에서 enum을 찾으면 그 결과를 사용
                if f: # var는 None일 수 있으므로 f만 체크
                    # child 내부에서 이미 변수명이 잡혔으면 재귀 종료
                    # 단, 이 때 var가 None이면 현재 decl_node에서 변수명을 찾아야 함
                    if var:
                        return True, var
                    else: # 자식에서 enum은 찾았지만 변수명은 못 찾은 경우, 현재 노드에서 찾는다.
                        found_enum_type = True # enum을 찾았다고 표시
                        break


        if found_enum_type:
            # 선언문의 declarator(변수 선언문)에서 실제 변수명 찾아서 반환
            # 보통 declaration → init_declarator → declarator → identifier 구조
            # 또는 declaration → declarator → identifier
            var_name_node = decl_node.child_by_field_name('declarator')
            if not var_name_node: # init_declarator 안에 declarator가 있을 수 있음
                init_decl = decl_node.child_by_field_name('init_declarator')
                if init_decl:
                    var_name_node = init_decl.child_by_field_name('declarator')

            if var_name_node:
                var_name = find_identifier_in_declarator(var_name_node, code)
                if var_name: # var_name이 None이 아닐 경우에만 반환
                    return True, var_name
        return False, None

    # translation_unit 하위에서 모든 declaration 노드 순회
    for child in root.children:
        if child.type == 'declaration':
            f, var = check_declaration(child)
            if f and var:
                enum_vars.add(var)

        # (추가) struct_specifier 내부의 declaration도 검사
        if child.type == 'struct_specifier':
            # struct_specifier → field_declaration_list(구조체 멤버 선언 목록) →
            #   여러 field_declaration → 각 declaration 형태일 수 있음
            # Tree-sitter C 문법에 따라 body 필드는 field_declaration_list를 가리킬 수 있음
            body_node = child.child_by_field_name('body')
            if body_node and body_node.type == 'field_declaration_list':
                for field_decl_node in body_node.children:
                    if field_decl_node.type == 'field_declaration':
                        # field_declaration의 자식으로 declaration 또는 직접 declarator가 올 수 있음
                        # type, declarator 필드를 직접 확인
                        type_node = field_decl_node.child_by_field_name('type')
                        declarator_node = field_decl_node.child_by_field_name('declarator')

                        # 타입 노드에서 enum 사용 검사
                        if type_node:
                            temp_found, _ = has_enum_in_function(type_node, code, target_enum)
                            if temp_found and declarator_node:
                                var_name = find_identifier_in_declarator(declarator_node, code)
                                if var_name:
                                    enum_vars.add(var_name)
                        # field_declaration 자체가 declaration을 포함할 수도 있음 (더 복잡한 구조)
                        for sub_child in field_decl_node.children:
                            if sub_child.type == 'declaration': # 거의 드문 케이스
                                f, var = check_declaration(sub_child)
                                if f and var:
                                    enum_vars.add(var)
    return enum_vars

def has_enum_in_function(node, code, target_enum):
    """
    node 내부에서 (1) target_enum이 직접 등장하는지
    (2) 자식 노드 검사하며 identifier가 target_enum인지 카운트하는 로직.
    enum_count와 found 여부만 반환(변수는 따로 처리)
    """
    enum_count = 0

    def visit_node(n):
        nonlocal enum_count

        # (A) 주석이나 문자열은 건너뜀
        if n.type in ['comment', 'string_literal']:
            return

        # (B) identifier인 경우 target_enum 비교
        if n.type == 'identifier':
            text = code[n.start_byte:n.end_byte].decode(errors='ignore')
            if text == target_enum:
                # 바로 parent가 선언문이든 함수 호출이든 상관없이 카운트
                enum_count += 1

        # 자식 노드 재귀 탐색
        for c in n.children:
            visit_node(c)

    visit_node(node)
    found = (enum_count > 0)
    return found, enum_count

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

def extract_functions_with_enum(node, code, target_enum, enum_vars=None, debug=False):
    """
    AST의 node를 재귀 탐색하면서,
    1) 전역에서 enum을 쓰는 변수들(enum_vars) 수집 (최상위 호출 시)
    2) 함수 정의, struct 정의, declaration 노드에서
       (a) target_enum 직접 사용 or
       (b) enum_vars 중 하나라도 사용되는 경우
       결과 리스트에 포함
    """
    if enum_vars is None: # 최초 호출 시 또는 enum_vars가 명시적으로 None으로 전달된 경우
        if node.type == 'translation_unit':
            enum_vars = collect_enum_global_vars(node, code, target_enum)
            if debug:
                print(f"[DEBUG] 전역에서 수집된 enum 변수들: {enum_vars}")
        else:
            # translation_unit이 아닌 노드에서 시작하지만 enum_vars가 None인 경우,
            # 이는 잘못된 호출일 수 있으나, 일단 빈 set으로 초기화하여 오류 방지.
            # 또는, 이전에 상위에서 collect_enum_global_vars를 호출해야 함을 의미.
            # 여기서는 현재 노드를 기준으로 다시 수집 시도 (더 안전한 방법)
            # temp_root = node
            # while temp_root.parent:
            #     temp_root = temp_root.parent
            # if temp_root.type == 'translation_unit':
            #      enum_vars = collect_enum_global_vars(temp_root, code, target_enum)
            # else: # translation_unit을 찾을 수 없는 경우
            enum_vars = set() # 안전하게 빈 집합으로 시작
    # else: enum_vars가 이미 전달된 경우 (재귀 호출)

    results = []

    # (2) 검토 대상 노드인지 확인
    if node.type in ['function_definition', 'struct_specifier', 'declaration']:
        # 노드 이름(함수명/struct명/전역 선언 변수명) 추출
        name = None
        if node.type == 'function_definition':
            decl = node.child_by_field_name('declarator')
            if decl:
                name = find_identifier_in_declarator(decl, code)
        elif node.type == 'struct_specifier':
            name_node = node.child_by_field_name('name')
            if name_node:
                name = code[name_node.start_byte:name_node.end_byte].decode(errors='ignore')
            else:
                name = "(anonymous struct)"
        elif node.type == 'declaration':
            # 지역 선언/전역 선언 모두 여기로 들어옴
            func_parent_name = get_enclosing_function_name(node, code)
            if func_parent_name:
                # 함수 내부의 지역 선언 → 그 함수 이름으로 보고
                name = func_parent_name
            else:
                # 함수 외부의 전역 선언 → 기존처럼 변수명
                # (주의) 이 declaration이 enum_vars 수집 대상이었다면,
                # 해당 변수명 자체가 func_name이 됨.
                var_name_node = node.child_by_field_name('declarator')
                if not var_name_node:
                    init_decl = node.child_by_field_name('init_declarator')
                    if init_decl:
                        var_name_node = init_decl.child_by_field_name('declarator')
                if var_name_node:
                    name = find_identifier_in_declarator(var_name_node, code)


        # (3) node 내부에서 직접 enum이 쓰였는지 확인
        found_direct, enum_count_direct = has_enum_in_function(node, code, target_enum)

        # (4) node 내부에서 enum_vars 중 하나라도 사용되는지 확인
        #     (AST를 다시 돌면서 identifier가 enum_vars에 속하는지 검사)
        found_via_var = False
        # enum_vars가 None일 수 있으므로 체크
        if enum_vars:
            def visit_for_var(n):
                nonlocal found_via_var
                if found_via_var: # 이미 찾았으면 더 탐색 안함
                    return

                # 주석이나 문자열은 건너뜀
                if n.type in ['comment', 'string_literal']:
                    return

                if n.type == 'identifier':
                    txt = code[n.start_byte:n.end_byte].decode(errors='ignore')
                    if txt in enum_vars:
                        found_via_var = True
                        return # 찾았으면 재귀 중단
                for c in n.children:
                    if found_via_var: # 하위 호출 전에도 체크
                        return
                    visit_for_var(c)

            visit_for_var(node)

        # (5) 둘 중 하나라도 참이면 결과에 추가
        if found_direct or found_via_var:
            node_code = code[node.start_byte:node.end_byte].decode(errors='ignore')
            # enum_count는 직접 등장 횟수만 카운트
            results.append({
                'func_name': name or '(이름없음)',
                'code': node_code,
                'enum_count': enum_count_direct
            })
            if debug:
                print(f"[DEBUG] 포함됨: {name}, direct={enum_count_direct}, via_var={found_via_var}, enum_vars_at_this_point: {enum_vars}")

    # (6) 자식 노드 재귀 순회 (enum_vars를 그대로 넘겨줌)
    for child in node.children:
        # 이미 results에 포함된 노드의 자식은 다시 검사할 필요가 없을 수도 있음.
        # 하지만, 함수 정의 내부에 또 다른 함수 정의(nested function, C에선 비표준)나
        # struct 정의 등이 있을 수 있으므로, 일단 모든 자식을 순회.
        # 중복을 피하기 위해, results에 추가할 때 func_name과 code가 동일한 경우 건너뛰는 로직 추가 가능.
        # 여기서는 일단 모든 자식 노드에 대해 재귀 호출.
        results.extend(extract_functions_with_enum(child, code, target_enum, enum_vars, debug=debug)) # enum_vars 전달

    return results

def find_all_identifiers(node, code, debug=False):
    """노드에서 모든 identifier를 찾아서 반환 (주석과 문자열 제외)"""
    identifiers = []

    def visit_node(n): # 인자 이름 변경 (node -> n)
        results = []
        # 주석이나 문자열은 건너뜀
        if n.type in ['comment', 'string_literal']:
            return results

        if n.type == 'identifier':
            text = code[n.start_byte:n.end_byte].decode(errors='ignore')
            if debug:
                print(f"Found identifier: {text}")
            results.append((n, text)) # node 대신 n 사용

        # 자식 노드들 재귀적으로 방문
        for child in n.children:
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
    for id_node, text in identifiers: # node, text -> id_node, text
        if text == target_enum:
            # 부모 노드가 주석이나 문자열이 아닌 경우에만 카운트
            parent = id_node.parent # node.parent -> id_node.parent
            if parent and parent.type not in ['comment', 'string_literal']:
                if debug:
                    parent_type = parent.type if parent else 'none'
                    print(f"Found ENUM '{target_enum}' at position {id_node.start_byte} in {parent_type}") # node.start_byte -> id_node.start_byte
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
    """
    파일 단위로 AST를 만들어 extract_functions_with_enum을 호출한 뒤
    결과에 file 이름을 붙여 반환
    """
    code_bytes = bytes(code, "utf8")
    tree = parser.parse(code_bytes)

    # query_mode는 사용하지 않으므로 해당 분기 제거 또는 주석 처리
    # if query_mode:
    #     ...
    # else:
    # 기존 AST 순회 방식
    if debug:
        print("\nParsed tree structure:")
        debug_print_tree(tree.root_node, code_bytes)
        print("\nSearching for functions...")

    # extract_functions_with_enum 호출 시 enum_vars를 명시적으로 None으로 시작
    results = extract_functions_with_enum(tree.root_node, code_bytes, target_enum, enum_vars=None, debug=debug)

    # 결과에서 중복 제거 (func_name과 code 기준으로)
    unique_results = []
    seen_results = set()
    for r in results:
        # 정렬 등을 위해 튜플로 변환 가능한 항목만 사용
        # 예를 들어, r['code']가 매우 길거나 특수문자가 많으면 문제가 될 수 있음.
        # 간단히 func_name과 enum_count 정도로만 식별하거나, code의 일부 해시를 사용하는 방법도 고려.
        # 여기서는 func_name과 code의 시작 100자 정도로 식별 시도.
        identifier_tuple = (r.get('func_name'), r.get('code', '')[:100], r.get('enum_count'))
        if identifier_tuple not in seen_results:
            unique_results.append(r)
            seen_results.add(identifier_tuple)
    
    final_results = []
    for r_unique in unique_results:
        # file 이름은 중복 제거 후 최종 결과에만 추가
        r_unique['file'] = file_name or ''
        final_results.append(r_unique)


    if debug:
        if final_results:
            print(f"\nFound {len(final_results)} unique functions/declarations using the target ENUM")
            for res_debug in final_results:
                print(f"- {res_debug['func_name']} ({res_debug['enum_count']} uses)")
        else:
            print("\nNo functions/declarations with target ENUM found")
    return final_results