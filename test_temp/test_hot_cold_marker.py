# HOT
import os
import tempfile
import time
from lord_of_code import update_file_markers

def test_update_file_markers_hot():
    # Create a temporary file
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as f:
        f.write('# Some code\nprint("hello")\n')
        temp_path = f.name

    try:
        # Set modification time to now (so it's hot)
        now = time.time()
        os.utime(temp_path, (now, now))
        
        # Call the function with a threshold of 2 days (so hot)
        update_file_markers(temp_path, hot_threshold_seconds=2*24*3600)
        
        # Read the file and check for # HOT at the top
        with open(temp_path, 'r') as f:
            lines = f.readlines()
        
        # The first line should be '# HOT\n' or '# HOT' (if no newline at end of file)
        assert lines[0].strip() == '# HOT', f"Expected first line to be '# HOT', got {lines[0]!r}"
    finally:
        os.unlink(temp_path)

def test_update_file_markers_cold():
    # Create a temporary file
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as f:
        f.write('# Some code\nprint("hello")\n')
        temp_path = f.name

    try:
        # Set modification time to 3 days ago (so cold)
        three_days_ago = time.time() - (3*24*3600)
        os.utime(temp_path, (three_days_ago, three_days_ago))
        
        # Call the function with a threshold of 2 days (so cold)
        update_file_markers(temp_path, hot_threshold_seconds=2*24*3600)
        
        # Read the file and check for # COLD at the top
        with open(temp_path, 'r') as f:
            lines = f.readlines()
        
        # The first line should be '# COLD\n' or '# COLD'
        assert lines[0].strip() == '# COLD', f"Expected first line to be '# COLD', got {lines[0]!r}"
    finally:
        os.unlink(temp_path)

def test_update_file_markers_existing_hot_to_cold():
    # Create a temporary file with an existing # HOT marker
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as f:
        f.write('# HOT\n# Some code\nprint("hello")\n')
        temp_path = f.name

    try:
        # Set modification time to 3 days ago (so cold)
        three_days_ago = time.time() - (3*24*3600)
        os.utime(temp_path, (three_days_ago, three_days_ago))
        
        # Call the function with a threshold of 2 days (so cold)
        update_file_markers(temp_path, hot_threshold_seconds=2*24*3600)
        
        # Read the file and check that the # HOT marker is replaced by # COLD
        with open(temp_path, 'r') as f:
            lines = f.readlines()
        
        # The first line should be '# COLD\n'
        assert lines[0].strip() == '# COLD', f"Expected first line to be '# COLD', got {lines[0]!r}"
        # The second line should be the original second line
        assert lines[1] == '# Some code\n', f"Expected second line to be '# Some code\\n', got {lines[1]!r}"
    finally:
        os.unlink(temp_path)

def test_update_file_markers_existing_cold_to_hot():
    # Create a temporary file with an existing # COLD marker
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as f:
        f.write('# COLD\n# Some code\nprint("hello")\n')
        temp_path = f.name

    try:
        # Set modification time to now (so hot)
        now = time.time()
        os.utime(temp_path, (now, now))
        
        # Call the function with a threshold of 2 days (so hot)
        update_file_markers(temp_path, hot_threshold_seconds=2*24*3600)
        
        # Read the file and check that the # COLD marker is replaced by # HOT
        with open(temp_path, 'r') as f:
            lines = f.readlines()
        
        # The first line should be '# HOT\n'
        assert lines[0].strip() == '# HOT', f"Expected first line to be '# HOT', got {lines[0]!r}"
        # The second line should be the original second line
        assert lines[1] == '# Some code\n', f"Expected second line to be '# Some code\\n', got {lines[1]!r}"
    finally:
        os.unlink(temp_path)

def test_update_file_markers_no_marker_adds_hot():
    # Create a temporary file with no marker
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as f:
        f.write('# Some code\nprint("hello")\n')
        temp_path = f.name

    try:
        # Set modification time to now (so hot)
        now = time.time()
        os.utime(temp_path, (now, now))
        
        # Call the function with a threshold of 2 days (so hot)
        update_file_markers(temp_path, hot_threshold_seconds=2*24*3600)
        
        # Read the file and check that # HOT is added at the top
        with open(temp_path, 'r') as f:
            lines = f.readlines()
        
        # The first line should be '# HOT\n'
        assert lines[0].strip() == '# HOT', f"Expected first line to be '# HOT', got {lines[0]!r}"
        # The second line should be the original first line
        assert lines[1] == '# Some code\n', f"Expected second line to be '# Some code\\n', got {lines[1]!r}"
    finally:
        os.unlink(temp_path)

if __name__ == '__main__':
    # Simple test runner
    import sys
    import traceback
    
    tests = [
        test_update_file_markers_hot,
        test_update_file_markers_cold,
        test_update_file_markers_existing_hot_to_cold,
        test_update_file_markers_existing_cold_to_hot,
        test_update_file_markers_no_marker_adds_hot,
    ]
    
    failed = 0
    for test in tests:
        try:
            test()
            print(f'PASS: {test.__name__}')
        except Exception as e:
            print(f'FAIL: {test.__name__}')
            print(f'  {e}')
            traceback.print_exc()
            failed += 1
    
    if failed == 0:
        print('All tests passed')
        sys.exit(0)
    else:
        print(f'{failed} tests failed')
        sys.exit(1)