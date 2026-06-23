import {
  BarChart, Bar,
  LineChart, Line,
  PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer,
} from "recharts";

const COLORS = [
  "#6366f1", "#22c55e", "#f59e0b", "#ef4444",
  "#8b5cf6", "#06b6d4", "#f97316", "#ec4899",
  "#14b8a6", "#a855f7",
];

function truncate(str, max = 14) {
  if (!str) return str;
  const s = String(str);
  return s.length > max ? s.slice(0, max) + "…" : s;
}

function BarView({ chart }) {
  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={chart.data} margin={{ top: 8, right: 16, left: 0, bottom: 40 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis
          dataKey={chart.x_key}
          tick={{ fontSize: 11 }}
          tickFormatter={(v) => truncate(v)}
          angle={-30}
          textAnchor="end"
          interval={0}
        />
        <YAxis tick={{ fontSize: 11 }} width={40} />
        <Tooltip />
        <Bar dataKey={chart.y_key} fill="#6366f1" radius={[4, 4, 0, 0]} maxBarSize={48} />
      </BarChart>
    </ResponsiveContainer>
  );
}

function LineView({ chart }) {
  const lineKeys = chart.lines || [{ key: chart.y_key, label: chart.y_key }];
  return (
    <ResponsiveContainer width="100%" height={280}>
      <LineChart data={chart.data} margin={{ top: 8, right: 16, left: 0, bottom: 40 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis
          dataKey={chart.x_key}
          tick={{ fontSize: 11 }}
          tickFormatter={(v) => truncate(v)}
          angle={-30}
          textAnchor="end"
          interval={0}
        />
        <YAxis tick={{ fontSize: 11 }} width={40} />
        <Tooltip />
        <Legend />
        {lineKeys.map((l, i) => (
          <Line
            key={l.key}
            type="monotone"
            dataKey={l.key}
            name={l.label || l.key}
            stroke={l.color || COLORS[i % COLORS.length]}
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4 }}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

const RADIAN = Math.PI / 180;
function PieLabel({ cx, cy, midAngle, innerRadius, outerRadius, percent, name }) {
  if (percent < 0.05) return null;
  const r = innerRadius + (outerRadius - innerRadius) * 0.5;
  const x = cx + r * Math.cos(-midAngle * RADIAN);
  const y = cy + r * Math.sin(-midAngle * RADIAN);
  return (
    <text x={x} y={y} fill="white" textAnchor="middle" dominantBaseline="central" fontSize={11}>
      {`${(percent * 100).toFixed(0)}%`}
    </text>
  );
}

function PieView({ chart }) {
  return (
    <ResponsiveContainer width="100%" height={280}>
      <PieChart>
        <Pie
          data={chart.data}
          dataKey={chart.value_key}
          nameKey={chart.name_key}
          cx="50%"
          cy="45%"
          outerRadius={100}
          labelLine={false}
          label={PieLabel}
        >
          {chart.data.map((_, i) => (
            <Cell key={i} fill={COLORS[i % COLORS.length]} />
          ))}
        </Pie>
        <Tooltip formatter={(value, name) => [value, name]} />
        <Legend
          formatter={(value) => truncate(value, 20)}
          wrapperStyle={{ fontSize: 11 }}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}

export default function ChartPanel({ chart, onClose }) {
  if (!chart) return null;

  return (
    <div className="flex flex-col h-full bg-white border-l border-gray-200">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100 flex-shrink-0">
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4 text-indigo-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
          <span className="text-sm font-semibold text-gray-700">Chart</span>
        </div>
        <button
          onClick={onClose}
          title="Close chart panel"
          className="text-gray-400 hover:text-gray-600 transition-colors p-1 rounded hover:bg-gray-100"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Chart body */}
      <div className="flex-1 overflow-y-auto p-4">
        {chart.title && (
          <p className="text-xs font-medium text-gray-500 mb-3 text-center tracking-wide uppercase">
            {chart.title}
          </p>
        )}
        {chart.type === "pie"  && <PieView  chart={chart} />}
        {chart.type === "line" && <LineView chart={chart} />}
        {(!chart.type || chart.type === "bar") && <BarView chart={chart} />}
      </div>
    </div>
  );
}
