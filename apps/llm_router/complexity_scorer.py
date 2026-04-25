"""Simplified complexity scorer for MVP."""
import re

def classify_task(task_text: str) -> dict:
    """
    Classify task complexity based on heuristics.
    Returns: {"level": str, "recommended_context": str}
    """
    task_lower = task_text.lower()
    
    # Complexity indicators
    complex_indicators = [
        "research", "analyze", "investigate", "survey", "compare", 
        "architecture", "design", "complex", "large", "multi-step"
    ]
    code_indicators = [
        "implement", "code", "function", "class", "script", 
        "debug", "refactor", "test", "write"
    ]
    
    score = 0
    for indicator in complex_indicators:
        if indicator in task_lower:
            score += 1
    
    # Simple rules
    if score >= 1 or len(task_text) > 200:
        return {"level": "moderate", "recommended_context": "nim_fast"}
    elif any(ind in task_lower for ind in code_indicators):
        # Code tasks often benefit from better models, but NIM-fast is cheap
        return {"level": "moderate", "recommended_context": "nim_fast"}
    else:
        return {"level": "trivial", "recommended_context": "classify_local"}

if __name__ == "__main__":
    print(classify_task("Implement a hello world function"))
    print(classify_task("Research and analyze the latest AI trends in 2025"))
