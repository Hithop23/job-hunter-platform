import re
from pathlib import Path

path = Path("app/api/dashboard.html")
content = path.read_text(encoding="utf-8")

# 1. Update <head> typography and CSS
old_head = """  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    body { font-family: 'Inter', sans-serif; }
    .badge-alta { background-color: #dcfce7; color: #15803d; border: 1px solid #86efac; }
    .badge-revision { background-color: #e0f2fe; color: #0369a1; border: 1px solid #7dd3fc; }
    .badge-excluido { background-color: #fee2e2; color: #b91c1c; border: 1px solid #fca5a5; }
    .badge-enviada { background-color: #f3e8ff; color: #7e22ce; border: 1px solid #d8b4fe; }
    .badge-entrevista { background-color: #fef9c3; color: #a16207; border: 1px solid #fde047; }"""

new_head = """  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@600;700;800&display=swap');
    
    :root {
      --apple-bg: #F5F5F7;
      --apple-card: #FFFFFF;
      --apple-text-primary: #1D1D1F;
      --apple-text-secondary: #6E6E73;
      --apple-text-tertiary: #86868B;
      --apple-border: rgba(0, 0, 0, 0.07);
      --apple-blue: #0071E3;
      --apple-blue-hover: #0077ED;
      --apple-green: #34C759;
    }

    body {
      font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Inter", sans-serif;
      background-color: var(--apple-bg);
      color: var(--apple-text-primary);
      -webkit-font-smoothing: antialiased;
      -moz-osx-font-smoothing: grayscale;
      letter-spacing: -0.01em;
    }

    h1, h2, h3, h4, h5, h6, .font-display {
      font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Plus Jakarta Sans", sans-serif;
      letter-spacing: -0.025em;
    }

    /* Apple Minimal Badges */
    .badge-alta {
      background-color: rgba(52, 199, 89, 0.12) !important;
      color: #248A3D !important;
      border: 1px solid rgba(52, 199, 89, 0.25) !important;
      font-weight: 600;
      border-radius: 9999px;
    }
    .badge-revision {
      background-color: rgba(0, 113, 227, 0.1) !important;
      color: #0071E3 !important;
      border: 1px solid rgba(0, 113, 227, 0.2) !important;
      font-weight: 600;
      border-radius: 9999px;
    }
    .badge-excluido {
      background-color: rgba(255, 59, 48, 0.1) !important;
      color: #D70015 !important;
      border: 1px solid rgba(255, 59, 48, 0.2) !important;
      font-weight: 600;
      border-radius: 9999px;
    }
    .badge-enviada {
      background-color: rgba(175, 82, 222, 0.1) !important;
      color: #8944AB !important;
      border: 1px solid rgba(175, 82, 222, 0.2) !important;
      font-weight: 600;
      border-radius: 9999px;
    }
    .badge-entrevista {
      background-color: rgba(255, 149, 0, 0.12) !important;
      color: #B25000 !important;
      border: 1px solid rgba(255, 149, 0, 0.25) !important;
      font-weight: 600;
      border-radius: 9999px;
    }

    /* Apple-style smooth scrollbars */
    ::-webkit-scrollbar {
      width: 7px;
      height: 7px;
    }
    ::-webkit-scrollbar-track {
      background: #F5F5F7;
    }
    ::-webkit-scrollbar-thumb {
      background: #D2D2D7;
      border-radius: 9999px;
    }
    ::-webkit-scrollbar-thumb:hover {
      background: #AEAEB2;
    }"""

if old_head in content:
    content = content.replace(old_head, new_head, 1)
    print("Replaced head style successfully!")
else:
    print("Warning: old_head not found!")

# 2. Body tag
content = content.replace(
    '<body class="bg-slate-50 text-slate-900 min-h-screen">',
    '<body class="bg-[#F5F5F7] text-[#1D1D1F] min-h-screen antialiased">',
    1
)

# 3. Header: Translucent Frosted Glass with Apple Minimalism
old_header = """  <!-- Header -->
  <header class="bg-slate-900 text-white shadow-md border-b border-slate-800 sticky top-0 z-40">
    <div class="max-w-7xl mx-auto px-4 py-3 sm:px-6 lg:px-8 flex flex-wrap items-center justify-between gap-4">
      <div class="flex items-center space-x-3">
        <div class="bg-emerald-500 text-slate-900 p-2 rounded-lg font-black text-xl tracking-wider">
          JH
        </div>
        <div>
          <h1 class="text-lg font-bold flex items-center gap-2">
            JOB-HUNTER-CO <span class="text-xs bg-emerald-500/20 text-emerald-400 px-2 py-0.5 rounded-full border border-emerald-500/30">SaaS Multi-Usuario</span>
          </h1>
          <p class="text-xs text-slate-400">Candidato: <span id="candidateNameDisplay" class="text-white font-medium">Invitado</span> <span id="candidateRoleDisplay" class="text-slate-400">(Sin iniciar sesión)</span></p>
        </div>
      </div>

      <!-- Action bar controls -->
      <div class="flex flex-wrap items-center gap-2 text-sm">
        <select id="scanMode" class="bg-slate-800 border border-slate-700 text-slate-200 rounded-lg px-3 py-1.5 focus:outline-none focus:border-emerald-500 text-xs">
          <option value="SCAN">Modo: SCAN (Solo Búsqueda)</option>
          <option value="PREPARE" selected>Modo: PREPARE (Búsqueda + CV ATS)</option>
          <option value="AUTOPILOT">🚀 Modo: AUTOPILOT (Envío Real)</option>
        </select>
        <!-- Shown only in AUTOPILOT mode -->
        <span class="autopilot-mode-indicator items-center gap-1.5 bg-emerald-500 text-slate-900 text-xs font-bold px-2.5 py-1 rounded-lg animate-pulse">
          🚀 AUTOPILOT ACTIVO — Botones ENVÍAN al portal
        </span>

        <button onclick="openGeneralSession('https://www.linkedin.com/login')" class="bg-indigo-600 hover:bg-indigo-500 text-white px-3 py-1.5 rounded-lg font-medium text-xs flex items-center gap-1.5 transition shadow-sm" title="Abre una ventana de navegador para iniciar sesión en tu cuenta. Tus credenciales quedarán recordadas para postularte sin bloqueos.">
          <i data-lucide="key-round" class="w-3.5 h-3.5"></i>
          <span>Iniciar Sesión LinkedIn</span>
        </button>

        <button onclick="triggerScan()" id="btnScan" class="bg-emerald-600 hover:bg-emerald-500 text-white px-3.5 py-1.5 rounded-lg font-medium text-xs flex items-center gap-1.5 transition">
          <i data-lucide="search" class="w-3.5 h-3.5"></i>
          <span>Escanear Fuentes</span>
        </button>

        <a href="/api/applications/export/csv" class="bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 px-3 py-1.5 rounded-lg text-xs flex items-center gap-1.5 transition">
          <i data-lucide="download" class="w-3.5 h-3.5"></i>
          <span>Exportar CSV</span>
        </a>

        <!-- Supabase Auth / Multi-tenant Profile Controls -->
        <div id="authContainer" class="flex items-center gap-1.5 border-l border-slate-700 pl-2">
          <!-- Button when Logged Out -->
          <button id="btnOpenAuth" onclick="openAuthModal()" class="bg-blue-600 hover:bg-blue-500 text-white px-3 py-1.5 rounded-lg font-medium text-xs flex items-center gap-1.5 transition shadow-sm">
            <i data-lucide="user-plus" class="w-3.5 h-3.5"></i>
            <span>Iniciar Sesión / Registro</span>
          </button>
          
          <!-- Buttons when Logged In -->
          <div id="userLoggedInGroup" class="hidden flex items-center gap-1.5">
            <button onclick="openProfileModal()" class="bg-slate-800 hover:bg-slate-700 text-emerald-400 border border-emerald-500/40 px-3 py-1.5 rounded-lg font-medium text-xs flex items-center gap-1.5 transition" title="Configurar tu perfil y datos para la hoja de vida ATS">
              <i data-lucide="user-check" class="w-3.5 h-3.5 text-emerald-400"></i>
              <span id="userProfileBtnLabel">Mi Perfil ATS</span>
            </button>
            <button onclick="handleSignOut()" class="bg-rose-950/60 hover:bg-rose-900 text-rose-300 border border-rose-800/50 px-2.5 py-1.5 rounded-lg text-xs flex items-center gap-1 transition" title="Cerrar Sesión">
              <i data-lucide="log-out" class="w-3.5 h-3.5"></i>
            </button>
          </div>
        </div>
    </div>
  </header>"""

new_header = """  <!-- Header: Apple Minimal Frosted Glass -->
  <header class="bg-white/80 backdrop-blur-xl border-b border-black/[0.06] sticky top-0 z-40 transition-all duration-200">
    <div class="max-w-7xl mx-auto px-4 py-3 sm:px-6 lg:px-8 flex flex-wrap items-center justify-between gap-4">
      <div class="flex items-center space-x-3">
        <div class="w-10 h-10 rounded-2xl bg-[#1D1D1F] text-white flex items-center justify-center font-bold text-sm tracking-tight shadow-sm">
          JH
        </div>
        <div>
          <div class="flex items-center gap-2">
            <h1 class="text-base font-bold text-[#1D1D1F] tracking-tight">JobHunter AI</h1>
            <span class="text-[10px] font-semibold bg-[#0071E3]/10 text-[#0071E3] px-2 py-0.5 rounded-full border border-[#0071E3]/20">SaaS ATS</span>
          </div>
          <p class="text-[11px] text-[#6E6E73]">Candidato: <span id="candidateNameDisplay" class="text-[#1D1D1F] font-semibold">Invitado</span> <span id="candidateRoleDisplay" class="text-[#86868B]">(Sin iniciar sesión)</span></p>
        </div>
      </div>

      <!-- Action bar controls -->
      <div class="flex flex-wrap items-center gap-2 text-xs">
        <select id="scanMode" class="bg-[#F5F5F7] border border-black/[0.08] text-[#1D1D1F] rounded-full px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-[#0071E3] font-medium text-xs">
          <option value="SCAN">Modo: SCAN (Búsqueda)</option>
          <option value="PREPARE" selected>Modo: PREPARE (Búsqueda + CV)</option>
          <option value="AUTOPILOT">🚀 Modo: AUTOPILOT (Envío Real)</option>
        </select>
        
        <span class="autopilot-mode-indicator items-center gap-1.5 bg-[#34C759] text-white text-xs font-semibold px-3 py-1 rounded-full animate-pulse">
          🚀 AUTOPILOT ACTIVO
        </span>

        <button onclick="openGeneralSession('https://www.linkedin.com/login')" class="bg-[#F5F5F7] hover:bg-[#E8E8ED] text-[#1D1D1F] border border-black/[0.08] px-3.5 py-1.5 rounded-full font-medium text-xs flex items-center gap-1.5 transition" title="Sesión LinkedIn">
          <i data-lucide="key-round" class="w-3.5 h-3.5 text-[#0071E3]"></i>
          <span>LinkedIn</span>
        </button>

        <button onclick="triggerScan()" id="btnScan" class="bg-[#0071E3] hover:bg-[#0077ED] text-white px-4 py-1.5 rounded-full font-semibold text-xs flex items-center gap-1.5 transition shadow-xs">
          <i data-lucide="search" class="w-3.5 h-3.5"></i>
          <span>Escanear Fuentes</span>
        </button>

        <a href="/api/applications/export/csv" class="bg-[#F5F5F7] hover:bg-[#E8E8ED] text-[#1D1D1F] border border-black/[0.08] px-3.5 py-1.5 rounded-full text-xs font-medium flex items-center gap-1.5 transition">
          <i data-lucide="download" class="w-3.5 h-3.5 text-[#6E6E73]"></i>
          <span>CSV</span>
        </a>

        <!-- Supabase Auth Controls -->
        <div id="authContainer" class="flex items-center gap-1.5 border-l border-black/[0.08] pl-2">
          <button id="btnOpenAuth" onclick="openAuthModal()" class="bg-[#1D1D1F] hover:bg-[#333336] text-white px-4 py-1.5 rounded-full font-semibold text-xs flex items-center gap-1.5 transition shadow-xs">
            <i data-lucide="user-plus" class="w-3.5 h-3.5"></i>
            <span>Iniciar Sesión</span>
          </button>
          
          <div id="userLoggedInGroup" class="hidden flex items-center gap-1.5">
            <button onclick="openProfileModal()" class="bg-[#F5F5F7] hover:bg-[#E8E8ED] text-[#0071E3] border border-black/[0.08] px-3.5 py-1.5 rounded-full font-semibold text-xs flex items-center gap-1.5 transition">
              <i data-lucide="user-check" class="w-3.5 h-3.5"></i>
              <span id="userProfileBtnLabel">Mi Perfil ATS</span>
            </button>
            <button onclick="handleSignOut()" class="bg-rose-50 hover:bg-rose-100 text-rose-600 border border-rose-200 px-2.5 py-1.5 rounded-full text-xs transition" title="Cerrar Sesión">
              <i data-lucide="log-out" class="w-3.5 h-3.5"></i>
            </button>
          </div>
        </div>
      </div>
    </div>
  </header>"""

if old_header in content:
    content = content.replace(old_header, new_header, 1)
    print("Replaced header successfully!")
else:
    print("Warning: old_header not found!")

# 4. Navigation Tabs: Segmented Control
old_tabs = """    <!-- Navigation Tabs -->
    <div class="border-b border-slate-200 flex flex-wrap gap-y-2 space-x-2 sm:space-x-6 text-sm font-medium">
      <button onclick="openTab('tab-applications')" id="btn-tab-applications" class="tab-btn pb-3 border-b-2 border-emerald-600 text-emerald-600 font-semibold flex items-center gap-2">
        <i data-lucide="briefcase" class="w-4 h-4"></i>
        <span>Vacantes & Candidaturas</span>
      </button>
      <button onclick="openTab('tab-cv-builder')" id="btn-tab-cv-builder" class="tab-btn pb-3 border-b-2 border-transparent text-slate-500 hover:text-slate-700 flex items-center gap-2">
        <i data-lucide="file-text" class="w-4 h-4 text-emerald-600"></i>
        <span>Creador & Optimizador ATS</span>
        <span class="px-1.5 py-0.5 text-[10px] font-bold rounded-full bg-emerald-500 text-white animate-pulse">NUEVO</span>
      </button>
      <button onclick="openTab('tab-hil')" id="btn-tab-hil" class="tab-btn pb-3 border-b-2 border-transparent text-slate-500 hover:text-slate-700 flex items-center gap-2">
        <i data-lucide="user-check" class="w-4 h-4"></i>
        <span>Revisión Humana</span>
        <span id="tabHilBadge" class="hidden ml-1 px-1.5 py-0.5 text-[10px] font-bold rounded-full bg-amber-500 text-white">0</span>
      </button>
      <button onclick="openTab('tab-sources')" id="btn-tab-sources" class="tab-btn pb-3 border-b-2 border-transparent text-slate-500 hover:text-slate-700 flex items-center gap-2">
        <i data-lucide="building-2" class="w-4 h-4"></i>
        <span>Fuentes & Empresas CO</span>
      </button>
      <button onclick="openTab('tab-profile')" id="btn-tab-profile" class="tab-btn pb-3 border-b-2 border-transparent text-slate-500 hover:text-slate-700 flex items-center gap-2">
        <i data-lucide="id-card" class="w-4 h-4"></i>
        <span>Perfil Verificado</span>
      </button>
    </div>"""

new_tabs = """    <!-- Navigation Tabs: Apple Segmented Pill Control -->
    <div class="flex items-center justify-start overflow-x-auto pb-1 no-scrollbar">
      <div class="inline-flex p-1 bg-[#E8E8ED]/80 backdrop-blur-md rounded-2xl border border-black/[0.04] text-xs font-medium gap-1 shadow-inner">
        <button onclick="openTab('tab-applications')" id="btn-tab-applications" class="tab-btn px-4 py-2 rounded-xl transition duration-200 font-semibold bg-white text-[#1D1D1F] shadow-xs flex items-center gap-2">
          <i data-lucide="briefcase" class="w-4 h-4"></i>
          <span>Vacantes & Radar</span>
        </button>
        <button onclick="openTab('tab-cv-builder')" id="btn-tab-cv-builder" class="tab-btn px-4 py-2 rounded-xl transition duration-200 text-[#6E6E73] hover:text-[#1D1D1F] flex items-center gap-2">
          <i data-lucide="sparkles" class="w-4 h-4 text-[#0071E3]"></i>
          <span>Creador de CV ATS (IA)</span>
          <span class="px-1.5 py-0.2 text-[9px] font-bold rounded-full bg-[#0071E3] text-white">PRO</span>
        </button>
        <button onclick="openTab('tab-hil')" id="btn-tab-hil" class="tab-btn px-4 py-2 rounded-xl transition duration-200 text-[#6E6E73] hover:text-[#1D1D1F] flex items-center gap-2">
          <i data-lucide="user-check" class="w-4 h-4"></i>
          <span>Revisión Humana</span>
          <span id="tabHilBadge" class="hidden ml-1 px-1.5 py-0.2 text-[9px] font-bold rounded-full bg-[#FF9500] text-white">0</span>
        </button>
        <button onclick="openTab('tab-sources')" id="btn-tab-sources" class="tab-btn px-4 py-2 rounded-xl transition duration-200 text-[#6E6E73] hover:text-[#1D1D1F] flex items-center gap-2">
          <i data-lucide="building-2" class="w-4 h-4"></i>
          <span>Fuentes & Empresas</span>
        </button>
        <button onclick="openTab('tab-profile')" id="btn-tab-profile" class="tab-btn px-4 py-2 rounded-xl transition duration-200 text-[#6E6E73] hover:text-[#1D1D1F] flex items-center gap-2">
          <i data-lucide="id-card" class="w-4 h-4"></i>
          <span>Perfil</span>
        </button>
      </div>
    </div>"""

if old_tabs in content:
    content = content.replace(old_tabs, new_tabs, 1)
    print("Replaced tabs successfully!")
else:
    print("Warning: old_tabs not found!")

# 5. Update openTab() in JS to toggle Apple Segmented Control classes
old_openTab = """    function openTab(tabId) {
      document.querySelectorAll('.tab-content').forEach(el => el.classList.add('hidden'));
      document.querySelectorAll('.tab-btn').forEach(el => {
        el.classList.remove('border-emerald-600', 'text-emerald-600', 'font-semibold');
        el.classList.add('border-transparent', 'text-slate-500');
      });
      document.getElementById(tabId).classList.remove('hidden');
      const activeBtn = document.getElementById('btn-' + tabId);
      if (activeBtn) {
        activeBtn.classList.remove('border-transparent', 'text-slate-500');
        activeBtn.classList.add('border-emerald-600', 'text-emerald-600', 'font-semibold');
      }
      lucide.createIcons();
    }"""

new_openTab = """    function openTab(tabId) {
      document.querySelectorAll('.tab-content').forEach(el => el.classList.add('hidden'));
      document.querySelectorAll('.tab-btn').forEach(el => {
        el.classList.remove('bg-white', 'text-[#1D1D1F]', 'shadow-xs', 'font-semibold');
        el.classList.add('text-[#6E6E73]');
      });
      document.getElementById(tabId).classList.remove('hidden');
      const activeBtn = document.getElementById('btn-' + tabId);
      if (activeBtn) {
        activeBtn.classList.remove('text-[#6E6E73]');
        activeBtn.classList.add('bg-white', 'text-[#1D1D1F]', 'shadow-xs', 'font-semibold');
      }
      lucide.createIcons();
    }"""

if old_openTab in content:
    content = content.replace(old_openTab, new_openTab, 1)
    print("Replaced openTab successfully!")
else:
    print("Warning: old_openTab not found!")

# 6. Update goToStep() in JS for Apple Stepper Pills
old_goToStep_inner = """          if (i === currentStep) {
            tabEl.className = 'py-1 rounded-lg text-emerald-700 font-bold bg-emerald-50 border border-emerald-200';
          } else if (i < currentStep) {
            tabEl.className = 'py-1 rounded-lg text-slate-700 font-semibold bg-slate-50 hover:bg-slate-100';
          } else {
            tabEl.className = 'py-1 rounded-lg text-slate-400 hover:bg-slate-50';
          }"""

new_goToStep_inner = """          if (i === currentStep) {
            tabEl.className = 'py-2 rounded-full text-white font-bold bg-[#0071E3] shadow-xs text-xs transition duration-200';
          } else if (i < currentStep) {
            tabEl.className = 'py-2 rounded-full text-[#248A3D] font-semibold bg-[#34C759]/10 hover:bg-[#34C759]/20 text-xs transition duration-200';
          } else {
            tabEl.className = 'py-2 rounded-full text-[#86868B] hover:text-[#1D1D1F] hover:bg-[#E8E8ED] text-xs transition duration-200';
          }"""

if old_goToStep_inner in content:
    content = content.replace(old_goToStep_inner, new_goToStep_inner, 1)
    print("Replaced goToStep successfully!")
else:
    print("Warning: old_goToStep_inner not found!")

# 7. Modernize cards, corners and shadows
# Soft Apple corners: rounded-2xl / rounded-3xl
content = content.replace('shadow-sm border border-slate-200', 'shadow-[0_2px_12px_rgba(0,0,0,0.03)] border border-black/[0.06] rounded-2xl')
content = content.replace('shadow-xs space-y-4', 'shadow-[0_2px_12px_rgba(0,0,0,0.03)] border border-black/[0.06] rounded-3xl space-y-5')
content = content.replace('shadow-xs space-y-6', 'shadow-[0_4px_20px_rgba(0,0,0,0.04)] border border-black/[0.06] rounded-3xl space-y-6')

# Primary action buttons in forms to Apple pill buttons
content = content.replace(
    'class="bg-emerald-600 hover:bg-emerald-500 text-white px-7 py-3 rounded-xl font-bold text-xs flex items-center gap-2 transition shadow-md"',
    'class="bg-[#0071E3] hover:bg-[#0077ED] text-white px-7 py-3 rounded-full font-bold text-xs flex items-center gap-2 transition shadow-sm"'
)
content = content.replace(
    'class="bg-slate-900 hover:bg-slate-800 text-white px-6 py-2.5 rounded-xl font-bold text-xs flex items-center gap-2 transition"',
    'class="bg-[#1D1D1F] hover:bg-[#333336] text-white px-6 py-2.5 rounded-full font-bold text-xs flex items-center gap-2 transition shadow-xs"'
)
content = content.replace(
    'class="bg-slate-100 hover:bg-slate-200 text-slate-700 px-5 py-2.5 rounded-xl font-semibold text-xs flex items-center gap-1.5 transition"',
    'class="bg-[#F5F5F7] hover:bg-[#E8E8ED] text-[#1D1D1F] px-5 py-2.5 rounded-full font-semibold text-xs flex items-center gap-1.5 transition border border-black/[0.06]"'
)

# Text inputs: Apple style (#F5F5F7 -> white on focus)
content = content.replace(
    'class="w-full bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-slate-800 focus:bg-white focus:outline-none focus:border-emerald-500 font-medium"',
    'class="w-full bg-[#F5F5F7] border border-black/[0.08] rounded-xl p-3 text-xs text-[#1D1D1F] font-medium placeholder:text-[#86868B] focus:bg-white focus:border-[#0071E3] focus:ring-4 focus:ring-[#0071E3]/10 focus:outline-none transition"'
)

path.write_text(content, encoding="utf-8")
print("Apple Minimal upgrade completed successfully!")
