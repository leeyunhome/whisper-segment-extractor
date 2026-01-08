
import os
import sys

log_file = 'debug_log.txt'

if not os.path.exists(log_file):
    print(f"{log_file} does not exist.")
    sys.exit(0)

print(f"Size: {os.path.getsize(log_file)} bytes")

# Try to detect encoding or just try common ones
encodings = ['utf-16le', 'utf-8', 'cp949', 'latin-1']

content = None
decoded_enc = None

raw_data = open(log_file, 'rb').read()

for enc in encodings:
    try:
        content = raw_data.decode(enc)
        decoded_enc = enc
        print(f"Successfully decoded with {enc}")
        break
    except Exception as e:
        print(f"Failed to decode with {enc}: {e}")

if content:
    print("--- Log Content Start ---")
    try:
        # Avoid printing characters that might crash console
        print(content.encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding))
    except:
        print(content)
    print("--- Log Content End ---")
else:
    print("Could not decode file.")
