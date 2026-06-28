import json
import os

transcript_path = r"C:\Users\20752\.gemini\antigravity\brain\9b7ada9e-a0db-438b-8732-64ca5b0eb5da\.system_generated\logs\transcript.jsonl"

if not os.path.exists(transcript_path):
    print("Transcript file not found.")
    exit(1)

keywords = ["测试账号", "apitest", "密码", "password", "账号"]

print("=== Searching Past Transcript ===")
with open(transcript_path, "r", encoding="utf-8") as f:
    for line_idx, line in enumerate(f):
        try:
            data = json.loads(line)
        except Exception:
            continue
        
        content = data.get("content", "")
        if not content:
            tool_calls = data.get("tool_calls", [])
            content = str(tool_calls)
            
        found = False
        matching_lines = []
        for l in content.split("\n"):
            if any(kw.lower() in l.lower() for kw in keywords):
                matching_lines.append(l.strip()[:150])
                found = True
        
        if found:
            source = data.get("source", "SYSTEM")
            step_type = data.get("type", "UNKNOWN")
            print(f"\n[Line {line_idx} | {source} | {step_type}]")
            for ml in matching_lines[:10]:  # print first 10 matching lines
                safe_ml = ml.encode('gbk', errors='replace').decode('gbk')
                print(f"  -> {safe_ml}")

