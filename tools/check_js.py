import re
from pathlib import Path

path = Path("app/api/dashboard.html")
original = path.read_text(encoding="utf-8")

# Extract the script tag and all JavaScript logic from dashboard.html
script_match = re.search(r'(<script>\s*// Global state.*?</script>)', original, re.DOTALL)
if not script_match:
    # Try finding <script> where currentUserId or supabase is initialized
    script_match = re.search(r'(<script>\s*const SUPABASE_URL.*?</script>)', original, re.DOTALL)

print("Found JS logic:", script_match is not None)
if script_match:
    js_code = script_match.group(1)
    print("JS logic length:", len(js_code))
