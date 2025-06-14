import hashlib # 해시 라이브러리 추가
from tree_sitter_languages import get_language, get_parser
from tree_sitter import Language, Parser
from utils import remove_preprocessor_directives # 추가된 import

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
    if node.type == 'identifier' or node.type == 'field_identifier': # field_identifier도 추가
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
                 # 함수 선언부에서 실제 함수 이름을 정확히 추출하도록 수정
                func_name_node = decl.child_by_field_name('declarator') # function_declarator의 declarator
                if func_name_node and func_name_node.type == 'identifier':
                    return code[func_name_node.start_byte:func_name_node.end_byte].decode(errors='ignore')
                # 포인터 함수 등의 경우 identifier가 더 깊이 있을 수 있음
                return find_identifier_in_declarator(decl, code)
        parent = parent.parent
    return None

def collect_enum_global_vars(root, code, target_enum):
    """
    전역 선언부(translation_unit 아래의 declaration)와 struct 내부 선언에서
    target_enum을 타입으로 쓰거나 선언의 일부로 사용하는 변수 이름들을 모두 수집하여 반환한다.
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
                    if var:
                        return True, var
                    else:
                        found_enum_type = True
                        break

        if found_enum_type:
            var_name_node = decl_node.child_by_field_name('declarator')
            if not var_name_node:
                init_decl = decl_node.child_by_field_name('init_declarator')
                if init_decl:
                    var_name_node = init_decl.child_by_field_name('declarator')

            if var_name_node:
                var_name = find_identifier_in_declarator(var_name_node, code)
                if var_name:
                    return True, var_name
        return False, None

    # translation_unit 하위에서 모든 declaration 노드 순회
    for child in root.children:
        if child.type == 'declaration':
            f, var = check_declaration(child)
            if f and var:
                enum_vars.add(var)

        if child.type == 'struct_specifier':
            body_node = child.child_by_field_name('body') # field_declaration_list
            if body_node:
                for fdecl_item in body_node.children: # field_declaration or comment etc.
                    if fdecl_item.type == 'field_declaration':
                        # 1. field_declaration 전체에서 target_enum 사용 여부 확인
                        enum_present_in_fdecl, _, _ = has_enum_in_function(fdecl_item, code, target_enum)
                        
                        if enum_present_in_fdecl:
                            # 2. target_enum이 사용되었다면, 이 field_declaration에서 모든 declarator(변수명) 추출
                            # field_declaration의 자식들(type specifiers 다음 declarators)을 순회
                            for fdecl_child in fdecl_item.children:
                                # declarator 역할을 할 수 있는 노드 타입들
                                declarator_types = [
                                    'field_identifier', 'identifier', 
                                    'pointer_declarator', 'array_declarator', 
                                    'function_declarator', 'parenthesized_declarator'
                                ]
                                if fdecl_child.type in declarator_types:
                                    var_name = find_identifier_in_declarator(fdecl_child, code)
                                    if var_name:
                                        enum_vars.add(var_name)
    return enum_vars

def has_enum_in_function(node, code, target_enum):
    """
    node 내부에서 (1) target_enum이 직접 등장하는지
    (2) 자식 노드 검사하며 identifier가 target_enum인지 카운트하는 로직.
    enum_count와 found 여부, 그리고 ENUM이 사용된 라인 번호 목록을 반환
    """
    enum_count = 0
    enum_lines = []  # ENUM이 사용된 라인 번호들을 저장

    def visit_node(n):
        nonlocal enum_count
    
        if n.type in ('comment', 'string_literal', 'string', 'char_literal'):
            return
        
        if n.type == 'identifier':
            text = code[n.start_byte:n.end_byte].decode(errors='ignore')
            if text == target_enum:
                # ENUM이 사용된 라인 번호 계산
                line_number = code.count(b'\n', 0, n.start_byte) + 1
                enum_lines.append(line_number)
                enum_count += 1
        for c in n.children:
            visit_node(c)

    visit_node(node)
    found = (enum_count > 0)
    return found, enum_count, sorted(enum_lines)  # 라인 번호를 정렬하여 반환

def debug_print_function_node(node, code, depth=0, debug=False):
    if not node or not debug:
        return
    indent = '  ' * depth
    node_text = code[node.start_byte:node.end_byte].decode(errors='ignore') if code else ''
    print(f"{indent}{node.type} [{node.start_byte}:{node.end_byte}] {node_text[:50]}")
    field_names = ['type', 'declarator', 'value', 'name', 'body', 'condition', 'consequence', 'alternative']
    for field_name in field_names:
        field = node.child_by_field_name(field_name)
        if field:
            print(f"{indent}  Field '{field_name}':")
            debug_print_function_node(field, code, depth + 2, debug=debug)
    for child_node in node.children: # 변수명 변경 child -> child_node
        # 이미 출력된 필드 자식은 건너뜀
        is_field_child = False
        for field_name in field_names:
            if node.child_by_field_name(field_name) == child_node:
                is_field_child = True
                break
        if not is_field_child:
            debug_print_function_node(child_node, code, depth + 1, debug=debug)

def extract_functions_with_enum(node, code, target_enum, enum_vars=None, debug=False, analyze_callers=False, context_lines=None):
    """
    AST의 node를 재귀 탐색하면서,
    1) 전역에서 enum을 쓰는 변수들(enum_vars) 수집 (최상위 호출 시)
    2) 함수 정의, struct 정의, declaration 노드에서
       (a) target_enum 직접 사용 or
       (b) enum_vars 중 하나라도 사용되는 경우
       결과 리스트에 포함한다.

    context_lines 값이 주어지면, ENUM 사용 라인을 중심으로 해당 줄수만큼
    앞뒤 맥락을 포함한다. 호출자 함수 정보에도 동일하게 적용된다.
    """
    if enum_vars is None:
        if node.type == 'translation_unit':
            enum_vars = collect_enum_global_vars(node, code, target_enum)
            if debug:
                print(f"[DEBUG] 전역에서 수집된 enum 변수들: {enum_vars}")
        else:
            enum_vars = set()

    results = []

    if node.type in ['function_definition', 'struct_specifier', 'declaration']:
        # 1) 노드별 이름 추출
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
            func_parent_name = get_enclosing_function_name(node, code)
            if func_parent_name is None:
                # 전역 선언인 경우에만 변수명 추출
                var_name_node = node.child_by_field_name('declarator')
                if not var_name_node:
                    init_decl = node.child_by_field_name('init_declarator')
                    if init_decl:
                        var_name_node = init_decl.child_by_field_name('declarator')
                if var_name_node:
                    name = find_identifier_in_declarator(var_name_node, code)
            else:
                # 함수 내부 선언일 경우, 함수 단위에서만 결과에 남도록 name을 None으로 유지
                name = None

        # 2) 직접 enum(target_enum) 사용 여부 + 개수 + 라인 번호
        found_direct, enum_count_direct, enum_lines = has_enum_in_function(node, code, target_enum)

        # 3) enum_vars 목록에 든 변수가 쓰였는지 검사
        found_via_var = False
        if enum_vars:
            def visit_for_var(n):
                nonlocal found_via_var
                if found_via_var:
                    return
                if n.type in ['comment', 'string_literal']:
                    return
                if n.type == 'identifier':
                    txt = code[n.start_byte:n.end_byte].decode(errors='ignore')
                    if txt in enum_vars:
                        found_via_var = True
                        return
                for c_node in n.children:
                    if found_via_var:
                        return
                    visit_for_var(c_node)
            visit_for_var(node)

        # 4) "직접 enum 사용"이나 "enum_vars 통해 사용" 중 하나라도 있으면 결과에 추가
        #    단, name이 None인 경우(== 함수 내부 선언이었다면)에는 추가하지 않음
        if (found_direct or found_via_var) and name:
            node_code = code[node.start_byte:node.end_byte].decode(errors="ignore")
            start_line = code.count(b"\n", 0, node.start_byte) + 1
            end_line = start_line + node_code.count("\n")

            snippet_code = node_code
            snippet_start = start_line
            snippet_end = end_line

            if context_lines is not None and enum_lines:
                min_line = max(start_line, min(enum_lines) - context_lines)
                max_line = min(end_line, max(enum_lines) + context_lines)
                rel_start = max(0, min_line - start_line)
                rel_end = max(0, max_line - start_line)
                lines = node_code.splitlines()
                snippet_code = "\n".join(lines[rel_start : rel_end + 1])
                snippet_start = min_line
                snippet_end = max_line

            results.append({
                "func_name": name,
                "code": snippet_code,
                "enum_count": enum_count_direct,
                "start_line": snippet_start,
                "end_line": snippet_end,
                "enum_lines": enum_lines,
                "callers": [],
            })
            if debug:
                print(
                    f"[DEBUG] 포함됨: {name}, direct={enum_count_direct}, via_var={found_via_var}, enum_vars={enum_vars}, lines={enum_lines}"
                )

    # 5) 하위 노드 재귀 호출 (enum_vars를 그대로 넘겨줌)
    for child_node in node.children:
        results.extend(
            extract_functions_with_enum(
                child_node,
                code,
                target_enum,
                enum_vars,
                debug=debug,
                analyze_callers=analyze_callers,
                context_lines=context_lines,
            )
        )

    # 함수 호출 관계 분석 (extract_functions_with_enum이 translation_unit에서 처음 호출될 때 한 번만 실행)
    if node.type == 'translation_unit' and results and analyze_callers:
        # 먼저 모든 함수 정의를 찾아서 위치 정보와 함께 저장
        all_function_definitions = {}
        def find_all_defs(n):
            if n.type == 'function_definition':
                decl = n.child_by_field_name('declarator')
                if decl:
                    func_name = find_identifier_in_declarator(decl, code)
                    if func_name:
                        func_code = code[n.start_byte:n.end_byte].decode(errors='ignore')
                        start_line = code.count(b'\n', 0, n.start_byte) + 1
                        end_line = start_line + func_code.count('\n')
                        all_function_definitions[func_name] = {
                            'node': n,
                            'code': func_code,
                            'start_line': start_line,
                            'end_line': end_line
                        }
            for child_n in n.children:
                find_all_defs(child_n)
        find_all_defs(node)

        # 각 함수를 순회하며 호출하는 함수(caller)를 찾음
        for res_item in results:
            target_func_name = res_item['func_name']
            
            # 전체 AST를 순회하며 target_func_name을 호출하는 함수들을 찾음
            callers_found = [] # 현재 target_func_name에 대한 호출자들
            
            def find_call_sites(n, current_enclosing_func_name=None, current_enclosing_func_node=None):
                if n.type == 'function_definition':
                    decl_node = n.child_by_field_name('declarator')
                    if decl_node:
                        # 현재 탐색 중인 함수의 이름을 가져옴
                        current_enclosing_func_name = find_identifier_in_declarator(decl_node, code)
                        current_enclosing_func_node = n # 현재 함수의 전체 노드 저장

                if n.type == 'call_expression':
                    func_identifier_node = n.child_by_field_name('function')
                    if func_identifier_node and func_identifier_node.type == 'identifier':
                        called_func_name = code[func_identifier_node.start_byte:func_identifier_node.end_byte].decode(errors='ignore')
                        if called_func_name == target_func_name and current_enclosing_func_name and current_enclosing_func_name != target_func_name: # 자기 자신 호출은 제외
                            # 호출자 정보가 all_function_definitions에 있는지 확인
                            if current_enclosing_func_name in all_function_definitions:
                                caller_info_def = all_function_definitions[current_enclosing_func_name]
                                call_line = code.count(b'\n', 0, func_identifier_node.start_byte) + 1

                                snippet_code = caller_info_def['code']
                                snippet_start = caller_info_def['start_line']
                                snippet_end = caller_info_def['end_line']

                                if context_lines is not None:
                                    min_line = max(caller_info_def['start_line'], call_line - context_lines)
                                    max_line = min(caller_info_def['end_line'], call_line + context_lines)
                                    rel_start = max(0, min_line - caller_info_def['start_line'])
                                    rel_end = max(0, max_line - caller_info_def['start_line'])
                                    lines_list = caller_info_def['code'].splitlines()
                                    snippet_code = "\n".join(lines_list[rel_start : rel_end + 1])
                                    snippet_start = min_line
                                    snippet_end = max_line

                                existing_caller_names = [c['func_name'] for c in callers_found]
                                if current_enclosing_func_name not in existing_caller_names:
                                    callers_found.append({
                                        'func_name': current_enclosing_func_name,
                                        'code': snippet_code,
                                        'start_line': snippet_start,
                                        'end_line': snippet_end,
                                        'call_line': call_line
                                    })
                                    if debug:
                                        print(f"[DEBUG] Caller found: {current_enclosing_func_name} calls {target_func_name} at line {call_line}")
                
                for child_n in n.children:
                    find_call_sites(child_n, current_enclosing_func_name, current_enclosing_func_node)

            find_call_sites(node) # translation_unit부터 다시 탐색 시작
            res_item['callers'] = callers_found
            if debug and callers_found:
                 print(f"[DEBUG] Function {target_func_name} is called by: {[c['func_name'] for c in callers_found]}")

    return results


def find_all_identifiers(node, code, debug=False):
    identifiers = []
    def visit_node(n):
        results_list = [] # 변수명 변경 results -> results_list
        if n.type in ['comment', 'string_literal']: return results_list
        if n.type == 'identifier':
            text = code[n.start_byte:n.end_byte].decode(errors='ignore')
            if debug: print(f"Found identifier: {text}")
            results_list.append((n, text))
        for child_node in n.children: # 변수명 변경 child -> child_node
            results_list.extend(visit_node(child_node))
        return results_list
    return visit_node(node)

def has_enum_in_node(node, code, target_enum, debug=False):
    found = False
    enum_count = 0
    identifiers = find_all_identifiers(node, code, debug)
    for id_node, text in identifiers:
        if text == target_enum:
            parent = id_node.parent
            if parent and parent.type not in ['comment', 'string_literal']:
                if debug:
                    parent_type = parent.type if parent else 'none'
                    print(f"Found ENUM '{target_enum}' at position {id_node.start_byte} in {parent_type}")
                found = True
                enum_count += 1
    return found, enum_count

def debug_print_tree(node, code, depth=0):
    indent = '  ' * depth
    node_text = code[node.start_byte:node.end_byte].decode(errors='ignore').replace('\n', '\\n')[:50]
    print(f"{indent}{node.type} [{node.start_byte}:{node.end_byte}] {node_text}")
    field_names = ['type', 'declarator', 'value', 'name', 'body', 'condition', 'consequence', 'alternative']
    for field_name in field_names:
        field_node = node.child_by_field_name(field_name)
        if field_node:
            print(f"{indent}  Field '{field_name}': {field_node.type}")
    for child_node in node.children: # 변수명 변경 child -> child_node
        debug_print_tree(child_node, code, depth + 1)

def extract_functions_with_enum_file(
    code,
    target_enum,
    file_name=None,
    debug=False,
    query_mode=False,
    analyze_callers=False,
    context_lines=None,
):
    # 전처리기 지시문 제거
    cleaned_code = remove_preprocessor_directives(code)
    
    if debug:
        print("\n--- Original Code ---")
        print(code[:500]) # 처음 500자만 출력
        print("\n--- Cleaned Code (after preprocessor removal) ---")
        print(cleaned_code[:500]) # 처음 500자만 출력
        
    code_bytes = bytes(cleaned_code, "utf8") # 수정된 코드로 바이트 변환
    tree = parser.parse(code_bytes)

    if debug:
        print("\nParsed tree structure (from cleaned code):")
        debug_print_tree(tree.root_node, code_bytes)
        print("\nSearching for functions...")

    results = extract_functions_with_enum(
        tree.root_node,
        code_bytes,
        target_enum,
        enum_vars=None,
        debug=debug,
        analyze_callers=analyze_callers,
        context_lines=context_lines,
    )

    unique_results = []
    seen_results_hashes = set() # 해시를 저장할 set
    for r in results:
        # 주의: r['code']는 전처리된 코드의 일부일 수 있음.
        # 원본 코드에서 위치를 찾으려면, 전처리된 코드와 원본 코드 간의 매핑이 필요하나,
        # 여기서는 단순화를 위해 전처리된 코드를 기준으로 결과를 생성.
        # 또는, r['code']를 원본 코드에서 다시 추출하는 방법도 고려할 수 있으나 복잡도 증가.
        # 현재는 전처리된 코드를 그대로 사용.
        code_str = r.get('code', '') 
        
        # 코드 문자열을 UTF-8로 인코딩하여 해시 생성
        code_hash = hashlib.md5(code_str.encode('utf-8')).hexdigest()
        
        # func_name, code_hash, enum_count를 기준으로 중복 식별
        identifier_tuple = (r.get('func_name'), code_hash, r.get('enum_count'))
        
        if identifier_tuple not in seen_results_hashes:
            # 라인 번호 계산 (cleaned_code 기준)
            # 원본 코드의 라인 번호와 달라질 수 있음에 유의
            lines = cleaned_code.split('\n')
            start_pos = cleaned_code.find(code_str) # cleaned_code에서 찾아야 함
            if start_pos != -1:
                start_line = cleaned_code[:start_pos].count('\n') + 1
                end_line = start_line + code_str.count('\n')
                r['start_line'] = start_line
                r['end_line'] = end_line
            else:
                # 만약 못찾는 경우 (이론상 발생하면 안됨), 0으로 설정
                r['start_line'] = 0 
                r['end_line'] = 0
            
            unique_results.append(r)
            seen_results_hashes.add(identifier_tuple)
    
    final_results = []
    for r_unique in unique_results:
        r_unique['file'] = file_name or ''
        final_results.append(r_unique)

    if debug:
        if final_results:
            print(f"\nFound {len(final_results)} unique functions/declarations using the target ENUM")
            for res_debug in final_results:
                print(f"- {res_debug['func_name']} ({res_debug['enum_count']} uses) at lines {res_debug['start_line']}-{res_debug['end_line']}")
        else:
            print("\nNo functions/declarations with target ENUM found")
    return final_results
