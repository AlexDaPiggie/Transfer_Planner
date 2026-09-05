import React from "react";

export function PlanSummary({ summary }) {
  return (
    <div className="bg-white p-6 rounded-lg shadow-sm border">
      <h2 className="text-lg font-bold text-gray-900 mb-3">Student Transfer Roadmap & Advice</h2>
      <div className="prose prose-sm max-w-none text-gray-700 whitespace-pre-line">
        {summary}
      </div>
    </div>
  );
}