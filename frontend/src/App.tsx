import React, { useEffect, useState } from 'react';

interface Stats {
  total_jobs_found: number;
  compatible_jobs: number;
  high_priority_jobs: number;
  cvs_prepared: number;
  submitted_applications: number;
  pending_human_interventions: number;
  interviews_scheduled: number;
  response_rate_percent: number;
}

export default function App() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [mode, setMode] = useState('PREPARE');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetch('/api/stats/dashboard')
      .then(res => res.json())
      .then(data => setStats(data))
      .catch(err => console.error(err));
  }, []);

  const handleScan = async () => {
    setLoading(true);
    await fetch(`/api/jobs/scan?mode=${mode}`, { method: 'POST' });
    setTimeout(() => {
      fetch('/api/stats/dashboard')
        .then(res => res.json())
        .then(data => {
          setStats(data);
          setLoading(false);
        });
    }, 2000);
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="bg-slate-900 text-white px-6 py-4 shadow flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-emerald-400">JOB-HUNTER-CO</h1>
          <p className="text-xs text-slate-400">Julian David Diaz Medina — Soporte TI & Sistemas</p>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={mode}
            onChange={e => setMode(e.target.value)}
            className="bg-slate-800 text-xs px-3 py-1.5 rounded border border-slate-700"
          >
            <option value="SCAN">Modo SCAN</option>
            <option value="PREPARE">Modo PREPARE</option>
            <option value="AUTOPILOT">Modo AUTOPILOT</option>
          </select>
          <button
            onClick={handleScan}
            disabled={loading}
            className="bg-emerald-600 hover:bg-emerald-500 text-xs font-semibold px-4 py-1.5 rounded text-white transition"
          >
            {loading ? 'Escaneando...' : 'Escanear Fuentes'}
          </button>
        </div>
      </header>

      <main className="max-w-6xl mx-auto p-6 space-y-6">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
            <span className="text-xs text-slate-500">Vacantes Encontradas</span>
            <p className="text-2xl font-bold">{stats?.total_jobs_found || 0}</p>
          </div>
          <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
            <span className="text-xs text-slate-500">Compatibles (≥60%)</span>
            <p className="text-2xl font-bold text-sky-600">{stats?.compatible_jobs || 0}</p>
          </div>
          <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
            <span className="text-xs text-slate-500">Alta Prioridad (≥75%)</span>
            <p className="text-2xl font-bold text-emerald-600">{stats?.high_priority_jobs || 0}</p>
          </div>
          <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
            <span className="text-xs text-slate-500">Postulaciones</span>
            <p className="text-2xl font-bold text-purple-600">{stats?.submitted_applications || 0}</p>
          </div>
        </div>
      </main>
    </div>
  );
}
