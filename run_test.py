from pathlib import Path
import tempfile
from scripts.approve import approve_gate_1, approve_gate_2, approve_gate_3, _read_frontmatter

# Gate 1 test
with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
    f.write("---\njob_id: JOB-G1\nstatus: created\n---\n# Test\n")
    tmp = Path(f.name)

approve_gate_1(tmp, "tester")
fm, body = _read_frontmatter(tmp)
assert fm["status"] == "approved_gate_1"
assert fm["approved_by"] == "tester"
print("Gate 1: PASS")

# Gate 2 reject test
with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
    f.write("---\njob_id: JOB-G2\nstatus: audit_passed\n---\n# Test\n")
    tmp2 = Path(f.name)

approve_gate_2(tmp2, "tester", reject=True)
fm2, body2 = _read_frontmatter(tmp2)
assert fm2["status"] == "gate_2_rejected"
assert fm2["gate_2_rejected_by"] == "tester"
print("Gate 2 reject: PASS")

# Gate 3 test
with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
    f.write("---\njob_id: JOB-G3\nstatus: staged\n---\n# Test\n")
    tmp3 = Path(f.name)

approve_gate_3(tmp3, "tester")
fm3, body3 = _read_frontmatter(tmp3)
assert fm3["status"] == "promoted"
assert fm3["approved_gate_3_by"] == "tester"
print("Gate 3: PASS")
print("All Gate functions: PASS")
