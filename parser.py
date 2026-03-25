import tree_sitter_python
from tree_sitter import Language, Parser, Node

# Initialize the Python language from tree-sitter bindings
PY_LANGUAGE = Language(tree_sitter_python.language())
parser = Parser(PY_LANGUAGE)

def extract_function(file_path: str, function_name: str) -> str:
    """
    Reads a Python file, parses it into an AST, and extracts only the
    source code of the specified function. This ensures we truncate context
    and only pass the required function to the LLM.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            code = f.read()
    except Exception as e:
        return f"Error reading file {file_path}: {e}"

    # Parse the code into an AST
    tree = parser.parse(bytes(code, "utf8"))
    
    def walk(node: Node) -> str | None:
        """Recursively walk the AST to find the function_definition with the matching name."""
        if node.type == 'function_definition':
            for child in node.children:
                if child.type == 'identifier' and child.text.decode('utf8') == function_name:
                    return node.text.decode('utf8')
        
        for child in node.children:
            result = walk(child)
            if result:
                return result
        return None

    extracted = walk(tree.root_node)
    if extracted:
        return extracted
    return f"Error: Function '{function_name}' not found in '{file_path}'."
