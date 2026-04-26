import sys
import os
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from domains.feedback_memory import get_feedback_memory
from apps.runtime.nodes.plan_executor import plan_executor

def test_feedback_cycle():
    print("Starting Self-Evolution Feedback Cycle Test...")
    memory = get_feedback_memory()
    
    # 1. Simulate a rejection and lesson learning
    task_desc = "APIキーをハードコードして通信を行うPythonスクリプトを作成してください。"
    feedback = "APIキーの直書きはセキュリティ上のリスクです。必ず環境変数（os.environ）から取得するように修正してください。"
    job_id = "test-rejection-001"
    
    print(f"Learning lesson from {job_id}...")
    memory.add_lesson(task_desc, feedback, job_id)
    
    # 2. Verify retrieval
    query_task = "外部APIと連携する新しい機能を実装してください。認証が必要です。"
    print(f"Searching for lessons relevant to: '{query_task}'")
    lessons = memory.search_lessons(query_task, threshold=0.5)
    
    assert len(lessons) > 0, "Should have retrieved at least one lesson"
    print(f"Retrieved {len(lessons)} lessons.")
    for l in lessons:
        print(f" - {l}")
        assert "環境変数" in l, "Lesson should mention '環境変数'"

    # 3. Verify injection into plan_executor
    state = {
        "routing_context": query_task,
        "job_path": None,
        "review_feedback": None
    }
    
    print("Testing plan_executor injection...")
    updated_state = plan_executor(state)
    objective = updated_state["planned_objective"]
    
    print(f"Final Objective:\n{objective}")
    assert "IMPORTANT: Past Lessons Learned" in objective
    assert "環境変数" in objective
    
    print("\nSUCCESS: Self-Evolution Feedback Cycle Verified!")

if __name__ == "__main__":
    try:
        # Clear existing memory for clean test if needed
        # (Optional: depends on if we want to test persistence or clean state)
        test_feedback_cycle()
    except Exception as e:
        print(f"TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
