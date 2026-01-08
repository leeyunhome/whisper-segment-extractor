
import os
import sys

base_name = "20260102_173000_80902ef1_mp3"
script_path = f"script_{base_name}.txt"

print(f"--- Content of {script_path} ---")
try:
    if os.path.exists(script_path):
        with open(script_path, 'r', encoding='utf-8') as f:
            print(f.read())
    else:
        print("Script file not found.")
except Exception as e:
    print(f"Error reading script: {e}")
    
# Also print file size to verify it's not empty
if os.path.exists(script_path):
    print(f"File size: {os.path.getsize(script_path)} bytes")

sys.stdout.flush()
