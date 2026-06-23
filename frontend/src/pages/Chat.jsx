import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { sendQuestion } from "../api/client";
import ReactMarkdown from "react-markdown";
import ChartPanel from "../components/ChartPanel";

function ChartIcon({ className = "w-4 h-4" }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
        d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
    </svg>
  );
}

function Message({ msg, onViewChart, onHideChart, isActiveChart }) {
  const isUser = msg.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}>
      <div
        className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
          isUser
            ? "bg-blue-600 text-white rounded-tr-sm"
            : "bg-white border border-gray-200 text-gray-800 rounded-tl-sm shadow-sm"
        }`}
      >
        {isUser ? (
          msg.content
        ) : (
          <ReactMarkdown
            components={{
              p:      ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
              ul:     ({ children }) => <ul className="list-disc pl-4 mb-2 space-y-1">{children}</ul>,
              ol:     ({ children }) => <ol className="list-decimal pl-4 mb-2 space-y-1">{children}</ol>,
              li:     ({ children }) => <li>{children}</li>,
              strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
              h1:     ({ children }) => <p className="font-semibold mt-2 mb-1">{children}</p>,
              h2:     ({ children }) => <p className="font-semibold mt-2 mb-1">{children}</p>,
              h3:     ({ children }) => <p className="font-medium mt-1 mb-0.5">{children}</p>,
            }}
          >
            {msg.content}
          </ReactMarkdown>
        )}

        {/* Row count badge */}
        {msg.rows_count != null && msg.rows_count > 0 && (
          <p className={`text-xs mt-2 ${isUser ? "text-blue-200" : "text-gray-400"}`}>
            {msg.rows_count} row{msg.rows_count !== 1 ? "s" : ""} retrieved
          </p>
        )}

        {/* View / Hide chart toggle */}
        {msg.chart_data && (
          <button
            onClick={() => isActiveChart ? onHideChart() : onViewChart(msg.chart_data)}
            className={`mt-2 flex items-center gap-1.5 text-xs font-medium rounded-lg px-2.5 py-1 transition-colors ${
              isActiveChart
                ? "bg-indigo-100 text-indigo-700 hover:bg-indigo-200"
                : "bg-gray-100 text-gray-500 hover:bg-indigo-50 hover:text-indigo-600"
            }`}
          >
            <ChartIcon className="w-3.5 h-3.5" />
            {isActiveChart ? "Hide chart" : "View chart"}
          </button>
        )}
      </div>
    </div>
  );
}

const SUGGESTIONS = [
  "How many employees are there?",
  "Show me the top 5 sales this month",
  "What is the total revenue this quarter?",
  "List all departments",
];

export default function Chat() {
  const [messages, setMessages]       = useState([]);
  const [input, setInput]             = useState("");
  const [loading, setLoading]         = useState(false);
  const [activeChart, setActiveChart] = useState(null);
  const [chartOpen, setChartOpen]     = useState(false);
  const bottomRef                       = useRef(null);
  const { user, logout }                = useAuth();
  const navigate                        = useNavigate();

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const openChart = (chartData) => {
    setActiveChart(chartData);
    setChartOpen(true);
  };

  const closeChart = () => {
    setChartOpen(false);
  };

  const send = async (question) => {
    if (!question.trim() || loading) return;
    const q = question.trim();
    setInput("");
    // Send last 8 messages as history (backend picks out the relevant chain)
    const history = messages
      .slice(-8)
      .map(({ role, content }) => ({ role, content }));
    setMessages((prev) => [...prev, { role: "user", content: q }]);
    setLoading(true);
    try {
      const data = await sendQuestion(q, history);
      const newMsg = {
        role:       "assistant",
        content:    data.answer,
        rows_count: data.rows_count,
        chart_data: data.chart_data || null,
      };
      setMessages((prev) => [...prev, newMsg]);
      if (data.chart_data) {
        setActiveChart(data.chart_data);
        setChartOpen(true);
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: err.response?.data?.detail || "Something went wrong." },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="h-screen flex flex-col bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-4 py-3 flex items-center justify-between flex-shrink-0 z-10">
        <div>
          <h1 className="font-semibold text-gray-800 text-sm">KT Demo</h1>
          <p className="text-xs text-gray-500">{user?.firm_id}</p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-gray-600">{user?.display_name}</span>
          <button
            onClick={() => { logout(); navigate("/"); }}
            className="text-xs text-gray-400 hover:text-gray-600 transition-colors"
          >
            Sign out
          </button>
        </div>
      </header>

      {/* Body: chat + optional chart panel */}
      <div className="flex-1 flex overflow-hidden">

        {/* Chat column */}
        <div className="flex-1 flex flex-col min-w-0">

          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-4 py-6">
            <div className="max-w-3xl w-full mx-auto">
              {messages.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-center pt-20">
                  <div className="w-12 h-12 rounded-xl bg-blue-600 flex items-center justify-center mb-4">
                    <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                        d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                    </svg>
                  </div>
                  <h2 className="text-lg font-medium text-gray-700 mb-1">Ask about your data</h2>
                  <p className="text-sm text-gray-400 mb-6">Questions are answered based on your access level</p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full max-w-md">
                    {SUGGESTIONS.map((s) => (
                      <button
                        key={s}
                        onClick={() => send(s)}
                        className="text-left text-sm bg-white border border-gray-200 rounded-xl px-4 py-3 text-gray-600 hover:border-blue-300 hover:text-blue-700 transition-colors"
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                <>
                  {messages.map((msg, i) => (
                    <Message
                      key={i}
                      msg={msg}
                      onViewChart={openChart}
                      onHideChart={closeChart}
                      isActiveChart={chartOpen && activeChart === msg.chart_data}
                    />
                  ))}
                  {loading && (
                    <div className="flex justify-start mb-4">
                      <div className="bg-white border border-gray-200 rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm">
                        <div className="flex gap-1">
                          {[0, 1, 2].map((i) => (
                            <span
                              key={i}
                              className="w-2 h-2 bg-gray-300 rounded-full animate-bounce"
                              style={{ animationDelay: `${i * 0.15}s` }}
                            />
                          ))}
                        </div>
                      </div>
                    </div>
                  )}
                  <div ref={bottomRef} />
                </>
              )}
            </div>
          </div>

          {/* Input bar */}
          <div className="bg-white border-t border-gray-200 px-4 py-4 flex-shrink-0">
            <div className="max-w-3xl mx-auto flex gap-2 items-center">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && send(input)}
                placeholder="Ask a question about your data…"
                disabled={loading}
                className="flex-1 border border-gray-300 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
              />

              <button
                onClick={() => send(input)}
                disabled={loading || !input.trim()}
                className="bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white rounded-xl px-4 py-2.5 text-sm font-medium transition-colors flex-shrink-0"
              >
                Send
              </button>
            </div>
          </div>
        </div>

        {/* Chart panel — slides in on the right */}
        {chartOpen && activeChart && (
          <div className="w-[380px] flex-shrink-0">
            <ChartPanel chart={activeChart} onClose={closeChart} />
          </div>
        )}
      </div>
    </div>
  );
}
