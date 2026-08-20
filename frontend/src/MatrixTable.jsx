import React, { useState } from "react";

export function MatrixTable({ matrix, targets }) {
  const [selectedCell, setSelectedCell] = useState(null);

  return (
    <div className="bg-white rounded-lg shadow-sm border overflow-hidden">
      <div className="p-4 border-b">
        <h2 className="text-lg font-bold text-gray-900">Cross-University Course Matrix</h2>
        <p className="text-xs text-gray-500">Sticky left column with horizontal comparison across all selected schools</p>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-gray-100 border-b text-xs font-semibold text-gray-600 uppercase">
              <th className="sticky left-0 bg-gray-100 z-10 p-3 min-w-[200px] border-r">
                CC Course
              </th>
              <th className="p-3 min-w-[80px] text-center border-r">Units</th>
              <th className="p-3 min-w-[120px] text-center border-r">Overlap</th>
              {targets.map(t => (
                <th key={t.target_id} className="p-3 min-w-[160px] text-center border-r">
                  {t.target_name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y text-sm">
            {matrix.map(row => (
              <tr key={row.code} className="hover:bg-gray-50">
                <td className="sticky left-0 bg-white z-10 p-3 font-semibold text-gray-900 border-r shadow-sm">
                  {row.code}
                  <span className="block text-xs font-normal text-gray-500">{row.title}</span>
                </td>
                <td className="p-3 text-center text-gray-600 border-r">{row.units}</td>
                <td className="p-3 text-center border-r">
                  <span className={`inline-block text-xs px-2 py-0.5 rounded font-medium ${
                    row.overlap_type === 'Universal' ? 'bg-green-100 text-green-800' :
                    row.overlap_type === 'Partial' ? 'bg-yellow-100 text-yellow-800' : 'bg-gray-100 text-gray-700'
                  }`}>
                    {row.overlap_type} ({row.overlap_count}/{targets.length})
                  </span>
                </td>
                {targets.map(t => {
                  const match = row.schools[t.target_name];
                  return (
                    <td 
                      key={t.target_id} 
                      onClick={() => setSelectedCell({ course: row, target: t.target_name, match })}
                      className="p-3 text-center border-r cursor-pointer hover:bg-blue-50 transition"
                    >
                      {match ? (
                        <span className="text-xs font-medium text-blue-700 bg-blue-50 border border-blue-200 px-2 py-1 rounded">
                          ✅ {match}
                        </span>
                      ) : (
                        <span className="text-xs text-gray-400">❌ None</span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {selectedCell && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50">
          <div className="bg-white p-6 rounded-lg max-w-md w-full shadow-lg">
            <h3 className="text-lg font-bold text-gray-900 mb-2">{selectedCell.course.code} Articulation</h3>
            <p className="text-sm text-gray-600 mb-4">
              <strong>Target School:</strong> {selectedCell.target}<br/>
              <strong>Equivalent Course:</strong> {selectedCell.match || "No Articulation"}
            </p>
            <button 
              onClick={() => setSelectedCell(null)}
              className="w-full bg-gray-200 hover:bg-gray-300 text-gray-800 py-2 rounded text-sm font-medium"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}