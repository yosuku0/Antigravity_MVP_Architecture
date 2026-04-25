from apps.tools.mcp_registry import registry

def test_mcp_registry():
    tools = registry.get_all_tools()
    assert len(tools) > 0
    assert any(t.name == "filesystem_read_file" for t in tools)
    
    # Test execution
    res = tools[0]._run(path="test.txt")
    assert "filesystem" in res
    assert "called" in res
    
    print("PASS: MCP registry works")

if __name__ == "__main__":
    test_mcp_registry()
