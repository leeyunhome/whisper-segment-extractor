
import os
import subprocess
import re

def parse_history(history_path):
    with open(history_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    blocks = content.split('######')
    data = {}
    
    for block in blocks:
        path_match = re.search(r'file_path\s*=\s*["\'](.+?)["\']', block)
        if not path_match: continue
        
        path = os.path.basename(path_match.group(1))
        
        start_match = re.search(r'start_time\s*=\s*\((.+?)\)\s*\*\s*1000', block)
        end_match = re.search(r'end_time\s*=\s*\((.+?)\)\s*\*\s*1000', block)
        
        if start_match and end_match:
            start_expr = start_match.group(1)
            end_expr = end_match.group(1)
            start_seconds = eval(start_expr)
            end_seconds = eval(end_expr)
            
            data[path] = (start_seconds, end_seconds)
            
    return data

def verify():
    history = parse_history("extract_history.txt")
    print(f"Loaded {len(history)} manual records.")
    
    files = [os.path.join("source_mp3", f) for f in history.keys()]
    extracted_data = {}
    
    # Run robust_extract.py
    # We need to capture the output of robust_extract.py to parse the proposed cuts
    # OR we can just import it. Importing is easier.
    
    try:
        from robust_extract import RobustExtractor
        extractor = RobustExtractor()
        
        print("\nRunning RobustExtractor...")
        for f in files:
            if not os.path.exists(f):
                print(f"File not found: {f}")
                continue
                
            print(f"Processing {f}...")
            start, end = extractor.extract(f, output_dir=None) # Don't save for now, just dry run logic
            extracted_data[os.path.basename(f)] = (start, end)
            
    except ImportError:
        print("Could not import RobustExtractor. Make sure robust_extract.py is in the directory.")
        return

    print("\n" + "="*60)
    print("VERIFICATION RESULTS")
    print("="*60)
    
    for filename, manual in history.items():
        if filename not in extracted_data:
            print(f"❌ {filename}: Skipped (not processed)")
            continue
            
        auto = extracted_data[filename]
        
        start_diff = auto[0] - manual[0]
        end_diff = auto[1] - manual[1]
        
        print(f"📄 {filename}")
        print(f"   Manual: {manual[0]:.2f}s ~ {manual[1]:.2f}s (Dur: {manual[1]-manual[0]:.2f}s)")
        print(f"   Auto  : {auto[0]:.2f}s ~ {auto[1]:.2f}s (Dur: {auto[1]-auto[0]:.2f}s)")
        print(f"   Diff  : Start {start_diff:+.2f}s, End {end_diff:+.2f}s")
        
        if abs(start_diff) < 2.0 and abs(end_diff) < 2.0:
            print("   ✅ PASS (within 2s)")
        else:
            print("   ⚠️  FAIL (diff > 2s)")
        print("-" * 40)

if __name__ == "__main__":
    verify()
