import os
import glob
import re

for txt_path in glob.glob("output_mp3/script_*.txt"):
    with open(txt_path, "r", encoding="utf-8") as f:
        txt = f.read()
        m = re.search(r"원본 구간:\s*([0-9.]+)초", txt)
        if m:
            print(f"{os.path.basename(txt_path)} -> {m.group(1)}")
        else:
            print(f"{os.path.basename(txt_path)} -> NOT FOUND")
        break
