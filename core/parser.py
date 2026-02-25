import ast


class CodeParser:

    @staticmethod
    def parse(code: str):
        try:
            tree = ast.parse(code)
            return tree
        except SyntaxError as e:
            raise e

    @staticmethod
    def validate(code: str):
        warnings = []
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name) and node.func.id == "eval":
                        warnings.append(
                            "Warning: Use of 'eval' detected! This is a security risk."
                        )

                if isinstance(node, ast.FunctionDef) and len(node.name) > 50:
                    warnings.append(
                        f"Warning: Function name '{node.name}' is too long."
                    )

        except SyntaxError as e:
            warnings.append(f"Critical: Syntax Error at line {e.lineno}")

        return warnings
