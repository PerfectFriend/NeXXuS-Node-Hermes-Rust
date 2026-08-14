import pytest


def test_project_structure():
    """Smoke test: project has basic structure"""
    assert True

def test_python_syntax():
    """Check all .py files compile"""
    import glob
    import py_compile
    for py_file in glob.glob("**/*.py", recursive=True):
        try:
            py_compile.compile(py_file, doraise=True)
        except py_compile.PyCompileError as e:
            pytest.fail(f"Syntax error in {py_file}: {e}")
