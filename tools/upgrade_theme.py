import re
from pathlib import Path

path = Path("app/api/dashboard.html")
content = path.read_text(encoding="utf-8")

replacements = [
    # Steps 2-5
    ('id="qStep2" class="q-step hidden bg-white p-6 sm:p-8 rounded-2xl border border-slate-200 shadow-xs space-y-6"',
     'id="qStep2" class="q-step hidden bg-[#111827] p-6 sm:p-8 rounded-2xl border border-[#334155]/60 shadow-xl space-y-6"'),
    ('id="qStep3" class="q-step hidden bg-white p-6 sm:p-8 rounded-2xl border border-slate-200 shadow-xs space-y-6"',
     'id="qStep3" class="q-step hidden bg-[#111827] p-6 sm:p-8 rounded-2xl border border-[#334155]/60 shadow-xl space-y-6"'),
    ('id="qStep4" class="q-step hidden bg-white p-6 sm:p-8 rounded-2xl border border-slate-200 shadow-xs space-y-6"',
     'id="qStep4" class="q-step hidden bg-[#111827] p-6 sm:p-8 rounded-2xl border border-[#334155]/60 shadow-xl space-y-6"'),
    ('id="qStep5" class="q-step hidden bg-white p-6 sm:p-8 rounded-2xl border border-slate-200 shadow-xs space-y-6"',
     'id="qStep5" class="q-step hidden bg-[#111827] p-6 sm:p-8 rounded-2xl border border-[#334155]/60 shadow-xl space-y-6"'),

    # Loading and Results Panels
    ('id="aiCvLoadingPanel" class="hidden bg-white p-8 sm:p-12 rounded-2xl border border-slate-200 text-center shadow-sm space-y-4"',
     'id="aiCvLoadingPanel" class="hidden bg-[#111827] p-8 sm:p-12 rounded-2xl border border-indigo-500/30 text-center shadow-2xl space-y-4"'),
    ('id="aiCvResultsPanel" class="hidden bg-white p-6 sm:p-8 rounded-2xl border border-slate-200 shadow-sm space-y-6"',
     'id="aiCvResultsPanel" class="hidden bg-[#111827] p-6 sm:p-8 rounded-2xl border border-emerald-500/30 shadow-2xl space-y-6"'),

    # Upload Results Card
    ('id="cvUploadResults" class="hidden bg-white p-6 sm:p-8 rounded-2xl border border-slate-200 shadow-sm space-y-6"',
     'id="cvUploadResults" class="hidden bg-[#111827] p-6 sm:p-8 rounded-2xl border border-emerald-500/30 shadow-xl space-y-6"'),

    # Drag and Drop card
    ('class="bg-white p-8 sm:p-10 rounded-2xl border-2 border-dashed border-slate-300 text-center space-y-4 hover:border-emerald-500 transition"',
     'class="bg-[#111827] p-8 sm:p-10 rounded-2xl border-2 border-dashed border-[#334155] text-center space-y-4 hover:border-emerald-500/60 transition shadow-lg"'),

    # Inner boxes in Step 1, 2, 3, 4, 5
    ('class="bg-slate-50 p-4 rounded-xl border border-slate-200 space-y-2"',
     'class="bg-[#1E293B]/70 p-4 rounded-xl border border-[#334155]/60 space-y-2 text-slate-200"'),
    ('class="bg-slate-50 p-4 rounded-xl border border-slate-200 space-y-3"',
     'class="bg-[#1E293B]/70 p-4 rounded-xl border border-[#334155]/60 space-y-3 text-slate-200"'),
    ('class="bg-slate-50 p-4 rounded-xl border border-slate-200 space-y-4"',
     'class="bg-[#1E293B]/70 p-4 rounded-xl border border-[#334155]/60 space-y-4 text-slate-200"'),

    # Geolocation dropdowns
    ('class="w-full border border-slate-200 rounded-lg p-2 text-xs bg-white text-slate-800 font-medium focus:outline-none focus:border-emerald-500"',
     'class="w-full border border-[#334155] rounded-lg p-2 text-xs bg-[#0B0F17] text-slate-100 font-medium focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"'),

    # Stepper quick buttons
    ('class="py-1 rounded-lg text-emerald-700 font-bold bg-emerald-50 border border-emerald-200"',
     'class="py-1.5 rounded-lg text-emerald-400 font-bold bg-emerald-500/10 border border-emerald-500/30 transition shadow-xs"'),
    ('class="py-1 rounded-lg hover:bg-slate-100"',
     'class="py-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-[#1E293B] border border-transparent transition"'),

    # Dynamic row builder inputs
    ('bg-white border border-slate-200 rounded p-2 text-slate-800',
     'bg-[#0B0F17] border border-[#334155] rounded p-2 text-slate-100 focus:border-emerald-500 focus:outline-none'),
    ('bg-white border border-slate-200 rounded p-1.5',
     'bg-[#0B0F17] border border-[#334155] rounded p-1.5 text-slate-100 focus:border-emerald-500 focus:outline-none'),

    # Modals styling
    ('class="bg-white rounded-2xl max-w-2xl w-full shadow-2xl border border-slate-200 overflow-hidden"',
     'class="bg-[#111827] rounded-2xl max-w-2xl w-full shadow-2xl border border-[#334155] text-slate-100 overflow-hidden"'),
    ('class="bg-white rounded-2xl max-w-xl w-full shadow-2xl border border-slate-200 overflow-hidden"',
     'class="bg-[#111827] rounded-2xl max-w-xl w-full shadow-2xl border border-[#334155] text-slate-100 overflow-hidden"'),
    ('class="bg-white rounded-2xl max-w-md w-full shadow-2xl border border-slate-200 overflow-hidden"',
     'class="bg-[#111827] rounded-2xl max-w-md w-full shadow-2xl border border-[#334155] text-slate-100 overflow-hidden"'),

    # Tabs 3 and 4 containers
    ('class="bg-white p-6 rounded-xl border border-slate-200 shadow-sm space-y-4"',
     'class="bg-[#111827] p-6 rounded-xl border border-[#334155]/60 shadow-xl space-y-4"'),
    ('class="bg-white p-6 rounded-xl border border-slate-200 shadow-sm space-y-6"',
     'class="bg-[#111827] p-6 rounded-xl border border-[#334155]/60 shadow-xl space-y-6"'),
    ('class="bg-white p-4 rounded-xl border border-slate-200 shadow-xs flex flex-wrap items-center justify-between gap-3"',
     'class="bg-[#111827] p-4 rounded-xl border border-[#334155]/60 shadow-lg flex flex-wrap items-center justify-between gap-3"'),

    # Form textareas
    ('class="w-full bg-white border border-slate-200 rounded-lg p-3 text-xs text-slate-800 focus:outline-none focus:border-emerald-500 font-mono"',
     'class="w-full bg-[#0B0F17] border border-[#334155] rounded-lg p-3 text-xs text-slate-100 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 font-mono"'),
    ('class="w-full bg-slate-50 border border-slate-200 rounded-lg p-3 text-xs text-slate-800 focus:bg-white focus:outline-none focus:border-emerald-500"',
     'class="w-full bg-[#0B0F17] border border-[#334155] rounded-lg p-3 text-xs text-slate-100 focus:bg-[#0B0F17] focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 placeholder:text-slate-500"'),

    # Text headers
    ('text-slate-800', 'text-slate-100'),
    ('text-slate-700', 'text-slate-200'),
    ('text-slate-900', 'text-white'),
    ('border-slate-100', 'border-[#334155]/40'),
    ('border-slate-200', 'border-[#334155]/60'),
    ('border-slate-300', 'border-[#334155]'),
    ('bg-slate-50', 'bg-[#1E293B]/70'),
    ('bg-slate-100', 'bg-[#1E293B]'),
    ('hover:bg-slate-50', 'hover:bg-[#1E293B]/50'),
    ('hover:bg-slate-100', 'hover:bg-[#1E293B]'),
    ('hover:bg-slate-200', 'hover:bg-[#334155]'),
]

for old, new in replacements:
    count = content.count(old)
    if count > 0:
        content = content.replace(old, new)
        print(f"Replaced {count} instances of: {old[:50]}...")

path.write_text(content, encoding="utf-8")
print("Finished fine-tuning dashboard.html!")
