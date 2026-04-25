from agentmemory import create_memory, search_memory

def test_agentmemory():
    try:
        # Clear if exists? No easy way in simulation, but we'll use unique name
        col = "test_col_v1"
        create_memory(col, "Hello world", metadata={"test": "data"})
        results = search_memory(col, "world")
        print(f"Results: {results}")
        assert len(results) > 0
        print("PASS: agentmemory works")
    except Exception as e:
        print(f"FAIL: agentmemory failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_agentmemory()
