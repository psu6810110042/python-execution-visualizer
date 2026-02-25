import ast


class CodeParser:

    @staticmethod
    def parse(code: str):
        try:
            tree = ast.parse(code)
            return tree
        except SyntaxError as e:
            raise e
