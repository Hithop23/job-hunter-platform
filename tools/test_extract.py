import re
from pathlib import Path

# Read current dashboard.html to extract the JS script block intact
dashboard_path = Path("app/api/dashboard.html")
original = dashboard_path.read_text(encoding="utf-8")

# Extract the script block starting at '// Supabase Auth & Multi-Tenant State'
js_start_idx = original.find("// Supabase Auth & Multi-Tenant State")
if js_start_idx == -1:
    raise ValueError("Could not find start of JS script block!")

# Find the opening <script> before that comment
script_open_idx = original.rfind("<script>", 0, js_start_idx)
js_script_block = original[script_open_idx:]

print(f"Extracted JS block from index {script_open_idx} (length: {len(js_script_block)})")
