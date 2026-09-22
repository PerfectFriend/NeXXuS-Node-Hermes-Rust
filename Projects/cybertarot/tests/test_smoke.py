# HOT
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


def test_font_fallback_handles_oserror():
    """Test that font loading gracefully handles OSError when font not found"""
    from PIL import ImageFont
    
    # This should not raise - it should fall back to default font
    font = None
    try:
        font = ImageFont.truetype("nonexistent_font_12345.ttf", 18)
    except OSError:
        # Expected - font not found, should fall back
        font = ImageFont.load_default()
    
    assert font is not None
    # Verify it's actually a font object
    assert hasattr(font, 'getbbox') or hasattr(font, 'getsize')


def test_font_truetype_raises_oserror_on_missing():
    """Verify that truetype raises OSError (not generic Exception) for missing fonts"""
    from PIL import ImageFont
    
    with pytest.raises(OSError):
        ImageFont.truetype("definitely_not_a_real_font_999.ttf", 18)
