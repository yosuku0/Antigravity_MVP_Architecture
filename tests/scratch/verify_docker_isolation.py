import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from utils.docker_executor import run_in_docker

def verify_isolation():
    print("=== Step 1: Connectivity Check ===")
    res1 = run_in_docker("print('hello from docker')")
    print(f"Stdout: {res1.get('stdout').strip()}")
    assert res1["success"]
    assert "hello from docker" in res1["stdout"]
    print("  Connectivity OK")

    print("\n=== Step 2: Write Restriction Check ===")
    test_file_name = "docker_test_write.txt"
    # Try to write to /mnt/artifacts (mounted)
    res2 = run_in_docker(f"with open('{test_file_name}', 'w') as f: f.write('written from docker')")
    assert res2["success"]
    
    host_file = Path("work/artifacts") / test_file_name
    if host_file.exists():
        content = host_file.read_text().strip()
        print(f"File created on host: {host_file}")
        assert content == "written from docker"
        print("  Write to mounted dir OK")
        # Cleanup
        host_file.unlink()
    else:
        print("!! File not found on host!")
        assert False

    print("\n=== Step 3: Isolation Check (Host file access) ===")
    # Try to read .env from host (not mounted)
    # Inside container, /mnt/artifacts is the only mount. 
    # Attempting to access ../../.env or similar should fail if outside mount.
    res3 = run_in_docker("import os; print(os.path.exists('../../.env'))")
    # It should not exist inside container at that relative path
    print(f"Does ../../.env exist in container? {res3.get('stdout').strip()}")
    assert "False" in res3.get("stdout")
    
    res4 = run_in_docker("with open('/etc/hostname', 'r') as f: print(f.read().strip())")
    print(f"Container hostname: {res4.get('stdout').strip()}")
    assert res4["success"]
    
    # Try to access a known host-only file via escape (should fail)
    # The mount is at /mnt/artifacts. ../../ should be / inside container.
    res5 = run_in_docker("import os; print(os.path.exists('/mnt/artifacts/../../.env'))")
    print(f"Access host .env via escape? {res5.get('stdout').strip()}")
    assert "False" in res5.get("stdout")
    print("  Isolation OK")

if __name__ == "__main__":
    try:
        verify_isolation()
        print("\nAll isolation tests passed!")
    except Exception as e:
        print(f"\nTest failed: {e}")
        sys.exit(1)
