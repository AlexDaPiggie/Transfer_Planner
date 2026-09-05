import React, { useState } from "react";
import { sendChatMessage } from "../api";

export function ExplainerChat({ planContext }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const quickPrompts = [
    "What if I drop Physics?",
    "Which university requires the most courses?",
    "Explain the Calculus series rule"
  ];

  const handleSend = async (textToSend) => {
    const query = textToSend || input;
    if (!query.trim()) return;

    const newHistory = [...messages, { role: "user", content: query }];
    setMessages(newHistory);
    setInput("");
    setLoading(true);

    try {
      const res = await sendChatMessage(planContext, messages, query);
      setMessages([...newHistory, { role: "assistant", content: res.reply }]);
    } catch (err) {
      setMessages([...newHistory, { role: "assistant", content: "Error getting response." }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-white p-4 rounded-lg shadow-sm border flex flex-col h-[600px]">
      <h2 className="text-lg font-bold text-gray-900 border-b pb-2 mb-3">Transfer Advisor Bot</h2>

      <div className="flex flex-wrap gap-1.5 mb-3">
        {quickPrompts.map((qp, i) => (
          <button
            key={i}
            onClick={() => handleSend(qp)}
            className="text-xs bg-gray-100 hover:bg-gray-200 text-gray-700 px-2 py-1 rounded transition"
          >
            {qp}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto space-y-3 p-2 bg-gray-50 rounded mb-3">
        {messages.map((m, i) => (
          <div key={i} className={`p-3 rounded-lg text-sm ${m.role === 'user' ? 'bg-blue-600 text-white ml-8' : 'bg-white border text-gray-800 mr-8'}`}>
            {m.content}
          </div>
        ))}
        {loading && <div className="text-xs text-gray-400 italic">Advisor is typing...</div>}
      </div>

      <div className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSend()}
          placeholder="Ask a question about your plan..."
          className="flex-1 border rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
        <button
          onClick={() => handleSend()}
          disabled={loading}
          className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded text-sm font-medium"
        >
          Send
        </button>
      </div>
    </div>
  );
}