# HOT
import os
import tempfile
import shutil
from pathlib import Path
import sys
sys.path.insert(0, '/home/thomas/LivingCode')

def test_update_hot_cold_markers():
    # Create a temporary directory
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a test file with # COLD
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("# COLD\nprint('hello')\n")
        
        # Also create a file without # COLD
        test_file2 = Path(tmpdir) / "test2.py"
        test_file2.write_text("print('world')\n")
        
        # Create a subdirectory
        subdir = Path(tmpdir) / "sub"
        subdir.mkdir()
        test_file3 = subdir / "test3.py"
        test_file3.write_text("# COLD\n# Another line\n")
        
        # Import the function from the lord_of_code module
        from lord_of_code import update_hot_cold_markers
        
        # Run the function
        update_hot_cold_markers(tmpdir)
        
        # Check the changes
        assert test_file.read_text() == "# COLD\nprint('hello')\n"
        assert test_file2.read_text() == "print('world')\n"
        assert test_file3.read_text() == "# COLD\n# Another line\n"

if __name__ == "__main__":
    test_update_hot_cold_markers()
    print("All tests passed")
