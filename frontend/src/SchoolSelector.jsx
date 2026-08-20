import React from "react";

export function SchoolSelector({ sources, setSources, targets, setTargets, onGenerate, loading }) {
  return (
    <div className="bg-white p-6 rounded-lg shadow-sm border flex flex-col gap-4">
      <div>
        <label className="block text-sm font-semibold text-gray-700 mb-1">
          Your Community Colleges (Multi-Select):
        </label>
        <div className="flex gap-2 mb-2">
          {sources.map(s => (
            <span key={s.id} className="bg-blue-100 text-blue-800 text-xs px-2.5 py-1 rounded-full font-medium">
              {s.name}
            </span>
          ))}
        </div>
      </div>

      <div>
        <label className="block text-sm font-semibold text-gray-700 mb-1">
          Target Universities & Majors:
        </label>
        <div className="flex flex-col gap-2">
          {targets.map((t, idx) => (
            <div key={idx} className="flex items-center gap-3 p-2 border rounded bg-gray-50">
              <span className="font-medium text-sm text-gray-800">{t.target_name}</span>
              <span className="text-sm text-gray-500">({t.major})</span>
            </div>
          ))}
        </div>
      </div>

      <button
        onClick={onGenerate}
        disabled={loading || sources.length === 0 || targets.length === 0}
        className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2.5 rounded transition disabled:opacity-50"
      >
        {loading ? "Generating Plan..." : "Generate Master Transfer Plan"}
      </button>
    </div>
  );
}