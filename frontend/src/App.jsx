import React, { useState, useEffect } from "react";
import { SchoolSelector } from "./components/SchoolSelector";
import { MatrixTable } from "./components/MatrixTable";
import { PlanSummary } from "./components/PlanSummary";
import { ExplainerChat } from "./components/ExplainerChat";
import { generatePlan } from "./api";

const STORAGE_KEY = "transfer_planner_state";

export default function App() {
  const [sources, setSources] = useState([]);
  const [targets, setTargets] = useState([]);
  const [planData, setPlanData] = useState(null);
  const [loading, setLoading] = useState(false);

  // Restore saved selections on page load
  useEffect(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
      const parsed = JSON.parse(saved);
      setSources(parsed.sources || []);
      setTargets(parsed.targets || []);
    }
  }, []);

  // Save selections to localStorage on every change
  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ sources, targets }));
  }, [sources, targets]);

  const handleGenerate = async () => {
    setLoading(true);
    try {
      const data = await generatePlan(75, sources.map(s => s.id), targets);
      setPlanData(data);
    } catch (err) {
      alert(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 p-6 flex flex-col gap-6">
      <header className="border-b pb-4">
        <h1 className="text-2xl font-bold text-gray-900">California Transfer Planner</h1>
        <p className="text-sm text-gray-500">Compare articulation agreements & optimize your transfer plan</p>
      </header>

      <SchoolSelector 
        sources={sources} 
        setSources={setSources} 
        targets={targets} 
        setTargets={setTargets} 
        onGenerate={handleGenerate}
        loading={loading}
      />

      {planData && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 flex flex-col gap-6">
            <MatrixTable matrix={planData.matrix} targets={targets} />
            <PlanSummary summary={planData.summary} />
          </div>
          <div className="lg:col-span-1">
            <ExplainerChat planContext={planData.summary} />
          </div>
        </div>
      )}
    </div>
  );
}