import { apiFetch } from "../api";

import { useEffect, useState } from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  PieChart,
  Pie,
  Cell,
  Legend,
} from "recharts";

interface DiaryEntry {
  id: number;
  title: string;
  entry_date: string;
  mood: string | null;
  mood_score: number | null;
}

interface MoodData {
  id: number;
  date: string;
  title: string;
  score: number;
  mood: string;
}

type TimeRange = "7" | "30" | "all";

const MOOD_COLORS: Record<string, string> = {
  happy: "#22C55E",
  sad: "#3B82F6",
  neutral: "#94A3B8",
  anxious: "#F59E0B",
  angry: "#EF4444",
  mixed: "#A855F7",
  unknown: "#64748B",
};

function MoodAnalytics() {
  const [moodData, setMoodData] = useState<MoodData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [timeRange, setTimeRange] = useState<TimeRange>("7");

  // Fetch diary entries
  useEffect(() => {
    const fetchMoodData = async () => {
      try {
        const response = await apiFetch(
          "http://localhost:8000/api/diary"
        );

        if (!response.ok) {
          throw new Error("Failed to fetch diary entries");
        }

        const data = await response.json();
        const entries: DiaryEntry[] = data.entries;

        const analyzedEntries = entries
          .filter(
            (entry) =>
              entry.mood_score !== null &&
              entry.mood_score !== undefined
          )
          .map((entry) => ({
            id: entry.id,
            date: entry.entry_date,
            title: entry.title,
            score: entry.mood_score as number,
            mood: entry.mood?.trim() || "Unknown",
          }))
          .sort(
            (a, b) =>
              a.date.localeCompare(b.date) || a.id - b.id
          );

        setMoodData(analyzedEntries);
      } catch (err) {
        console.error(err);
        setError("Unable to load mood analytics.");
      } finally {
        setLoading(false);
      }
    };

    fetchMoodData();
  }, []);

  // Filter entries by selected time range
  const filteredMoodData = moodData.filter((entry) => {
    if (timeRange === "all") {
      return true;
    }

    const days = Number(timeRange);

    const today = new Date();
    today.setHours(0, 0, 0, 0);

    const startDate = new Date(today);
    startDate.setDate(today.getDate() - (days - 1));

    const [year, month, day] = entry.date
      .split("-")
      .map(Number);

    const entryDate = new Date(year, month - 1, day);

    return entryDate >= startDate && entryDate <= today;
  });

  // Calculate average mood score
  const averageMood =
    filteredMoodData.length > 0
      ? (
          filteredMoodData.reduce(
            (total, entry) => total + entry.score,
            0
          ) / filteredMoodData.length
        ).toFixed(1)
      : "N/A";

  // Count entries for each mood
  const moodCounts = filteredMoodData.reduce<
    Record<string, number>
  >((counts, entry) => {
    const mood = entry.mood.trim().toLowerCase() || "unknown";

    counts[mood] = (counts[mood] || 0) + 1;

    return counts;
  }, {});

  // Convert counts into Recharts data
  const moodDistribution = Object.entries(moodCounts)
    .map(([name, value]) => ({
      name: name.charAt(0).toUpperCase() + name.slice(1),
      value,
    }))
    .sort((a, b) => b.value - a.value);

  if (loading) {
    return (
      <p className="text-slate-500">
        Loading analytics...
      </p>
    );
  }

  if (error) {
    return (
      <p className="text-red-600">
        {error}
      </p>
    );
  }

  return (
    <div className="space-y-8">
      {/* Dashboard Header */}
      <div>
        <p className="mb-2 text-sm font-semibold text-indigo-600">
          YOUR EMOTIONAL JOURNEY
        </p>

        <h2 className="text-3xl font-bold text-slate-800">
          Mood Analytics 📊
        </h2>

        <p className="mt-2 text-slate-500">
          Explore your mood patterns through your diary entries.
        </p>
      </div>

      {/* Time Range Filters */}
      <div className="flex flex-wrap gap-3">
        {[
          { label: "Last 7 Days", value: "7" },
          { label: "Last 30 Days", value: "30" },
          { label: "All Time", value: "all" },
        ].map((filter) => (
          <button
            key={filter.value}
            type="button"
            onClick={() =>
              setTimeRange(filter.value as TimeRange)
            }
            className={`rounded-xl px-5 py-2.5 text-sm font-semibold transition ${
              timeRange === filter.value
                ? "bg-indigo-600 text-white shadow-sm"
                : "border border-slate-200 bg-white text-slate-600 hover:bg-indigo-50"
            }`}
          >
            {filter.label}
          </button>
        ))}
      </div>

      {/* Statistics Cards */}
      <div className="grid gap-5 sm:grid-cols-2">
        {/* Average Mood Score */}
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-sm font-medium text-slate-500">
            Average Mood Score
          </p>

          <p className="mt-3 text-4xl font-bold text-indigo-600">
            {averageMood}

            {filteredMoodData.length > 0 && (
              <span className="text-lg text-slate-400">
                {" "}/ 10
              </span>
            )}
          </p>
        </div>

        {/* Analyzed Entries */}
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-sm font-medium text-slate-500">
            Analyzed Entries
          </p>

          <p className="mt-3 text-4xl font-bold text-slate-800">
            {filteredMoodData.length}
          </p>
        </div>
      </div>

      {/* Mood Trend Chart */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm md:p-8">
        <h3 className="mb-2 text-xl font-semibold">
          Mood Score Trend
        </h3>

        <p className="mb-8 text-sm text-slate-500">
          AI-estimated emotional tone across your diary entries.
        </p>

        {filteredMoodData.length === 0 ? (
          <p className="py-16 text-center text-slate-500">
            No mood data available for the selected period.
          </p>
        ) : (
          <div className="h-80 w-full">
            <ResponsiveContainer
              width="100%"
              height="100%"
            >
              <LineChart
                data={filteredMoodData}
                margin={{
                  top: 10,
                  right: 20,
                  left: -20,
                  bottom: 10,
                }}
              >
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="#E2E8F0"
                />

                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 12 }}
                />

                <YAxis
                  domain={[0, 10]}
                  tick={{ fontSize: 12 }}
                />

                <Tooltip
                  formatter={(value) => [
                    `${value}/10`,
                    "Mood Score",
                  ]}
                  labelFormatter={(_, payload) => {
                    const entry = payload?.[0]?.payload as
                      | MoodData
                      | undefined;

                    return entry
                      ? `${entry.date} — ${entry.title} (${entry.mood})`
                      : "";
                  }}
                />

                <Line
                  type="monotone"
                  dataKey="score"
                  stroke="#6366F1"
                  strokeWidth={3}
                  dot={{
                    r: 5,
                    fill: "#6366F1",
                  }}
                  activeDot={{ r: 7 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Mood Distribution Pie Chart */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm md:p-8">
        <h3 className="mb-2 text-xl font-semibold">
          Mood Distribution 🥧
        </h3>

        <p className="mb-6 text-sm text-slate-500">
          See how frequently each mood appears in your diary entries.
        </p>

        {moodDistribution.length === 0 ? (
          <p className="py-16 text-center text-slate-500">
            No mood data available for the selected period.
          </p>
        ) : (
          <div className="h-80 w-full">
            <ResponsiveContainer
              width="100%"
              height="100%"
            >
              <PieChart>
                <Pie
                  data={moodDistribution}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="45%"
                  outerRadius={100}
                  label={({ name, percent }) =>
                    `${name} ${(
                      (percent ?? 0) * 100
                    ).toFixed(0)}%`
                  }
                >
                  {moodDistribution.map((entry) => (
                    <Cell
                      key={entry.name}
                      fill={
                        MOOD_COLORS[
                          entry.name.toLowerCase()
                        ] ?? "#64748B"
                      }
                    />
                  ))}
                </Pie>

                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  );
}

export default MoodAnalytics;
