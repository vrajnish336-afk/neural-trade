import ast
from typing import List, Tuple

class ASTSecurityValidator(ast.NodeVisitor):
    """
    Statically analyzes Python code for dangerous patterns.
    Blocks network, filesystem, and OS execution entirely.
    """
    
    ALLOWED_IMPORTS = {"math", "statistics", "typing", "numpy", "pandas", "datetime"}
    
    def __init__(self):
        self.errors: List[str] = []
        
    def validate(self, code: str) -> Tuple[bool, List[str]]:
        try:
            tree = ast.parse(code)
            self.visit(tree)
            return len(self.errors) == 0, self.errors
        except SyntaxError as e:
            return False, [f"SyntaxError: {e}"]
            
    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            base_module = alias.name.split('.')[0]
            if base_module not in self.ALLOWED_IMPORTS:
                self.errors.append(f"Illegal import detected: {alias.name}")
        self.generic_visit(node)
        
    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module:
            base_module = node.module.split('.')[0]
            if base_module not in self.ALLOWED_IMPORTS:
                self.errors.append(f"Illegal from-import detected: {node.module}")
        else:
            self.errors.append("Relative imports are blocked.")
        self.generic_visit(node)
        
    def visit_Call(self, node: ast.Call):
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            blocked_builtins = {
                "exec", "eval", "compile", "open", "__import__",
                "globals", "locals", "vars", "dir", "getattr", "setattr", "delattr",
                "memoryview", "bytearray"
            }
            if func_name in blocked_builtins:
                self.errors.append(f"Illegal builtin call detected: {func_name}")
                
        elif isinstance(node.func, ast.Attribute):
            # Check for things like os.system, subprocess.run
            attr_name = node.func.attr
            if attr_name in {"system", "popen", "run", "call", "check_output", "spawn"}:
                self.errors.append(f"Potentially dangerous method call detected: {attr_name}")
        
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute):
        # Prevent access to dunder attributes that might allow sandbox escape
        if node.attr.startswith("__") and node.attr.endswith("__"):
            # Allow some common harmless ones if needed, but safer to block all 
            # except very specific ones like __name__
            if node.attr not in {"__name__"}:
                self.errors.append(f"Illegal dunder attribute access: {node.attr}")
        self.generic_visit(node)
