import React, { useEffect, useState } from 'react';
import { Briefcase, CheckCircle2, AlertTriangle, Send, Search, ExternalLink, UserCheck, ShieldCheck } from 'lucide-react';

interface Stats {
  total_jobs_found: number;
  compatible_jobs: number;
  high_priority_jobs: number;
  cvs_prepared: number;
  submitted_applications: number;
  pending_human_interventions: number;
  interviews_scheduled: number;
  response_rate_percent: number;
  sources_breakdown?: Record<string, number>;
  status_breakdown?: Record<string, number>;
}

export default function App() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [mode, setMode] = useState('PREPARE');
  const [loading, setLoading] = useState(false);
  const [statusMsg, setStatusMsg] = useState('');

  const fetchStats = () => {
    fetch('/api/stats/dashboard')
      .then(res => res.json())
      .then(data => setStats(data))
      .catch(err => console.error(err));
  };

  useEffect(() => {
    fetchStats();
    const interval = setInterval(fetchStats, 15000);
    return () => clearInterval(interval);
  }, []);

  const handleScan = async () => {
    setLoading(true);
    setStatusMsg('Escaneando ofertas activas...');
    try {
      await fetch(`/api/jobs/scan?mode=${mode}`, { method: 'POST' });
      setStatusMsg('Búsqueda completada. Actualizando métricas...');
      setTimeout(() => {
        fetchStats();
        setLoading(false);
        setStatusMsg('');
      }, 3000);
    } catch (e: any) {
      setStatusMsg('Error: ' + e.message);
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 flex flex-col font-sans">
      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-950/80 backdrop-blur sticky top-0 z-30 px-6 py-4 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="bg-emerald-500 text-slate-950 font-black px-2.5 py-1.5 rounded-lg text-lg tracking-wider">
            JH
          </div>
          <div>
            <h1 className="text-lg font-bold flex items-center gap-2">
              JOB-HUNTER SaaS <span className="text-xs bg-emerald-500/20 text-emerald-400 px-2 py-0.5 rounded-full border border-emerald-500/30">Vercel Edge</span>
            </h1>
            <p className="text-xs text-slate-400">Plataforma de Postulación Laboral & Generador ATS</p>
          </div>
        </div>

        <div className="flex items-center gap-2 text-xs">
          <select
            value={mode}
            onChange={e => setMode(e.target.value)}
            className="bg-slate-800 border border-slate-700 text-slate-200 px-3 py-1.5 rounded-lg focus:outline-none focus:border-emerald-500"
          >
            <option value="SCAN">Modo: SCAN (Solo Búsqueda)</option>
            <option value="PREPARE">Modo: PREPARE (Búsqueda + CV ATS)</option>
            <option value="AUTOPILOT">🚀 Modo: AUTOPILOT (Envío Real)</option>
          </select>

          <button
            onClick={handleScan}
            disabled={loading}
            className="bg-emerald-600 hover:bg-emerald-500 text-white font-semibold px-4 py-1.5 rounded-lg transition flex items-center gap-1.5 disabled:opacity-50"
          >
            <Search className="w-3.5 h-3.5" />
            <span>{loading ? 'Escaneando...' : 'Escanear Fuentes'}</span>
          </button>

          <a
            href="https://job-hunter-platform-4ik7.onrender.com"
            target="_blank"
            rel="noreferrer"
            className="bg-indigo-600 hover:bg-indigo-500 text-white font-semibold px-3 py-1.5 rounded-lg transition flex items-center gap-1.5"
            title="Abrir el panel completo con navegador Playwright y visor de hojas de vida"
          >
            <span>Panel Completo</span>
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        </div>
      </header>

      {/* Hero / Status Banner */}
      {statusMsg && (
        <div className="bg-emerald-500/10 border-b border-emerald-500/20 px-6 py-2 text-xs text-emerald-400 text-center animate-pulse">
          {statusMsg}
        </div>
      )}

      {/* Main Content */}
      <main className="max-w-6xl w-full mx-auto p-6 space-y-6 flex-1">
        {/* Metric Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-slate-800/80 border border-slate-700/80 p-4 rounded-xl shadow-xs">
            <div className="flex items-center justify-between text-slate-400 text-xs mb-1">
              <span>Ofertas Encontradas</span>
              <Briefcase className="w-4 h-4 text-slate-400" />
            </div>
            <p className="text-3xl font-extrabold text-white">{stats?.total_jobs_found || 0}</p>
            <p className="text-[11px] text-slate-400 mt-1">Computrabajo, LinkedIn, Remotive, etc.</p>
          </div>

          <div className="bg-slate-800/80 border border-slate-700/80 p-4 rounded-xl shadow-xs">
            <div className="flex items-center justify-between text-sky-400 text-xs mb-1">
              <span>Compatibles (≥60%)</span>
              <CheckCircle2 className="w-4 h-4 text-sky-400" />
            </div>
            <p className="text-3xl font-extrabold text-sky-400">{stats?.compatible_jobs || 0}</p>
            <p className="text-[11px] text-slate-400 mt-1">Requisitos de TI & perfil</p>
          </div>

          <div className="bg-slate-800/80 border border-slate-700/80 p-4 rounded-xl shadow-xs">
            <div className="flex items-center justify-between text-emerald-400 text-xs mb-1">
              <span>Alta Prioridad (≥75%)</span>
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
            </div>
            <p className="text-3xl font-extrabold text-emerald-400">{stats?.high_priority_jobs || 0}</p>
            <p className="text-[11px] text-slate-400 mt-1">Salario ≥$2.5M & remoto</p>
          </div>

          <div className="bg-slate-800/80 border border-slate-700/80 p-4 rounded-xl shadow-xs">
            <div className="flex items-center justify-between text-purple-400 text-xs mb-1">
              <span>Postulaciones Enviadas</span>
              <Send className="w-4 h-4 text-purple-400" />
            </div>
            <p className="text-3xl font-extrabold text-purple-400">{stats?.submitted_applications || 0}</p>
            <p className="text-[11px] text-slate-400 mt-1">Confirmadas en portales</p>
          </div>
        </div>

        {/* Feature Highlights */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
          <div className="bg-slate-800/50 border border-slate-700 p-4 rounded-xl">
            <h3 className="font-bold text-sm text-emerald-400 mb-1">🛡️ Multi-Tenant Aislado</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Cada usuario cuenta con credenciales y postulaciones protegidas con Supabase Row Level Security (RLS). Cero cruces de datos entre candidatos.
            </p>
          </div>

          <div className="bg-slate-800/50 border border-slate-700 p-4 rounded-xl">
            <h3 className="font-bold text-sm text-sky-400 mb-1">📄 CV ATS Dinámico</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Genera automáticamente hojas de vida PDF adaptadas a las palabras clave de cada vacante técnica usando los datos específicos de tu perfil.
            </p>
          </div>

          <div className="bg-slate-800/50 border border-slate-700 p-4 rounded-xl">
            <h3 className="font-bold text-sm text-indigo-400 mb-1">🤖 Playwright Headless</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Navegadores autónomos ejecutados en el backend de Render para aplicar sin interacción manual y con captura de pantalla como evidencia.
            </p>
          </div>
        </div>

        {/* Call to Action Box */}
        <div className="bg-gradient-to-r from-emerald-950/60 via-slate-900 to-indigo-950/60 border border-emerald-500/30 rounded-2xl p-6 flex flex-col md:flex-row items-center justify-between gap-4">
          <div>
            <h3 className="text-base font-bold text-white">¿Deseas acceder al panel interactivo completo?</h3>
            <p className="text-xs text-slate-400 mt-1">
              Accede al visor de vacantes detalladas, descarga de CVs generados, resolución de verificaciones 2FA e inicio de sesión de portales.
            </p>
          </div>
          <a
            href="https://job-hunter-platform-4ik7.onrender.com"
            target="_blank"
            rel="noreferrer"
            className="bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs px-5 py-2.5 rounded-xl transition shadow-lg shrink-0 flex items-center gap-2"
          >
            <span>Ir al Panel de Control</span>
            <ExternalLink className="w-4 h-4" />
          </a>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800 py-4 px-6 text-center text-xs text-slate-500">
        JOB-HUNTER SaaS &bull; Conectado a Render &bull; Supabase PostgreSQL
      </footer>
    </div>
  );
}
