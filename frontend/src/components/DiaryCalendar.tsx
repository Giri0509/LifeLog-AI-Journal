import { apiFetch } from "../api";

import { useEffect, useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

interface DiaryEntry {
  id: number;
  title: string;
  content: string;
  entry_date: string;
  mood?: string | null;
  mood_score?: number | null;
}

function DiaryCalendar() {
  const [entries, setEntries] = useState<DiaryEntry[]>([]);
  const [currentMonth, setCurrentMonth] = useState(new Date());
  const [selectedDate, setSelectedDate] = useState(() => {
    const today = new Date();
    return [
      today.getFullYear(),
      String(today.getMonth() + 1).padStart(2, "0"),
      String(today.getDate()).padStart(2, "0"),
    ].join("-");
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Mood-based colors
  const getMoodColor = (mood?: string | null) => {
    switch (mood?.toLowerCase()) {
      case "happy":
      case "joyful":
      case "excited":
        return "bg-green-100 border-green-300 text-green-800";

      case "sad":
      case "depressed":
        return "bg-blue-100 border-blue-300 text-blue-800";

      case "anxious":
      case "stressed":
      case "worried":
        return "bg-amber-100 border-amber-300 text-amber-800";

      case "angry":
      case "frustrated":
        return "bg-red-100 border-red-300 text-red-800";

      case "neutral":
      case "calm":
        return "bg-slate-100 border-slate-300 text-slate-700";

      case "mixed":
        return "bg-purple-100 border-purple-300 text-purple-800";

      default:
        return "bg-indigo-50 border-indigo-200 text-indigo-700";
    }
  };

  // Fetch diary entries from backend
  useEffect(() => {
    const fetchEntries = async () => {
      try {
        setLoading(true);
        setError("");

        const response = await apiFetch(
          "http://localhost:8000/api/diary"
        );

        if (!response.ok) {
          throw new Error("Failed to fetch diary entries");
        }

        const data = await response.json();
        setEntries(data.entries);
      } catch (err) {
        console.error(err);
        setError("Unable to load diary entries.");
      } finally {
        setLoading(false);
      }
    };

    fetchEntries();
  }, []);

  // Current calendar month
  const year = currentMonth.getFullYear();
  const month = currentMonth.getMonth();

  const firstDay = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();

  // Navigate months
  const changeMonth = (offset: number) => {
    setCurrentMonth(new Date(year, month + offset, 1));
  };

  // Format date as YYYY-MM-DD
  const formatDate = (day: number) => {
    const mm = String(month + 1).padStart(2, "0");
    const dd = String(day).padStart(2, "0");

    return `${year}-${mm}-${dd}`;
  };

  // Selected date entries
  const selectedEntries = entries.filter(
    (entry) => entry.entry_date === selectedDate
  );

  const monthLabel = currentMonth.toLocaleDateString(
    "en-US",
    {
      month: "long",
      year: "numeric",
    }
  );

  // -------------------------------------------
  // Monthly Mood Summary
  // -------------------------------------------

  const monthPrefix = `${year}-${String(month + 1).padStart(2, "0")}`;

  // Entries in the displayed month
  const monthlyEntries = entries.filter((entry) =>
    entry.entry_date.startsWith(`${monthPrefix}-`)
  );

  // Number of unique days with entries
  const journaledDays = new Set(
    monthlyEntries.map((entry) => entry.entry_date)
  ).size;

  // Entries with valid mood scores
  const analyzedEntries = monthlyEntries.filter(
    (entry) =>
      entry.mood_score != null &&
      Number.isFinite(entry.mood_score)
  );

  // Monthly average mood
  const averageMood =
    analyzedEntries.length > 0
      ? (
          analyzedEntries.reduce(
            (sum, entry) => sum + (entry.mood_score ?? 0),
            0
          ) / analyzedEntries.length
        ).toFixed(1)
      : null;

  // Group mood scores by date
  const dailyMoodScores = new Map<
    string,
    { total: number; count: number }
  >();

  analyzedEntries.forEach((entry) => {
    const existing = dailyMoodScores.get(entry.entry_date) ?? {
      total: 0,
      count: 0,
    };

    dailyMoodScores.set(entry.entry_date, {
      total: existing.total + (entry.mood_score ?? 0),
      count: existing.count + 1,
    });
  });

  // Find day with highest average mood score
  const happiestDay = [...dailyMoodScores.entries()]
    .map(([date, stats]) => ({
      date,
      average: stats.total / stats.count,
    }))
    .sort(
      (a, b) =>
        b.average - a.average ||
        a.date.localeCompare(b.date)
    )[0];

  const happiestDayLabel = happiestDay
    ? new Date(
        `${happiestDay.date}T12:00:00`
      ).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
      })
    : "—";

  // -------------------------------------------
  // Monthly Mood Trend Data
  // -------------------------------------------

  // One average mood score per day
  const moodTrendData = [...dailyMoodScores.entries()]
    .map(([date, stats]) => ({
      date,
      day: Number(date.slice(8, 10)),
      score: Number(
        (stats.total / stats.count).toFixed(1)
      ),
    }))
    .sort((a, b) => a.date.localeCompare(b.date));

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      {/* Header */}
      <div>
        <p className="mb-2 text-sm font-medium text-indigo-600">
          YOUR JOURNAL TIMELINE
        </p>

        <h2 className="text-3xl font-bold text-slate-800">
          Diary Calendar 📅
        </h2>

        <p className="mt-2 text-slate-500">
          Explore your memories one day at a time.
        </p>
      </div>

      {/* Mood Legend */}
      <div className="flex flex-wrap gap-3 rounded-xl border border-slate-200 bg-white p-4">
        {[
          { label: "Happy", color: "bg-green-400" },
          { label: "Sad", color: "bg-blue-400" },
          { label: "Anxious", color: "bg-amber-400" },
          { label: "Angry", color: "bg-red-400" },
          { label: "Neutral", color: "bg-slate-400" },
          { label: "Mixed", color: "bg-purple-400" },
        ].map((item) => (
          <div
            key={item.label}
            className="flex items-center gap-2"
          >
            <span
              className={`h-3 w-3 rounded-full ${item.color}`}
            />

            <span className="text-xs font-medium text-slate-600">
              {item.label}
            </span>
          </div>
        ))}
      </div>

      {/* ------------------------------------ */}
      {/* Monthly Mood Summary Cards */}
      {/* ------------------------------------ */}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {/* Average Mood */}
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-3 text-2xl">💜</div>

          <p className="text-sm font-medium text-slate-500">
            Average Mood
          </p>

          <h3 className="mt-2 text-3xl font-bold text-indigo-700">
            {loading
              ? "..."
              : error
              ? "—"
              : averageMood !== null
              ? `${averageMood}/10`
              : "—"}
          </h3>

          <p className="mt-2 text-xs text-slate-400">
            {monthLabel}
          </p>
        </div>

        {/* Journaled Days */}
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-3 text-2xl">📅</div>

          <p className="text-sm font-medium text-slate-500">
            Journaled Days
          </p>

          <h3 className="mt-2 text-3xl font-bold text-indigo-700">
            {loading ? "..." : error ? "—" : journaledDays}
          </h3>

          <p className="mt-2 text-xs text-slate-400">
            Days with at least one entry
          </p>
        </div>

        {/* Happiest Day */}
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-3 text-2xl">☀️</div>

          <p className="text-sm font-medium text-slate-500">
            Happiest Day
          </p>

          <h3 className="mt-2 text-3xl font-bold text-indigo-700">
            {loading
              ? "..."
              : error
              ? "—"
              : happiestDayLabel}
          </h3>

          <p className="mt-2 text-xs text-slate-400">
            Highest daily average mood score
          </p>
        </div>
      </div>

      {/* ------------------------------------ */}
      {/* Monthly Mood Trend Chart */}
      {/* ------------------------------------ */}

      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-6">
          <h3 className="text-lg font-bold text-slate-800">
            📈 Monthly Mood Trend
          </h3>

          <p className="mt-1 text-sm text-slate-500">
            Daily average mood scores for {monthLabel}
          </p>
        </div>

        {loading ? (
          <p className="py-12 text-center text-slate-500">
            Loading mood trend...
          </p>
        ) : error ? (
          <p className="py-12 text-center text-red-600">
            Unable to load mood trend.
          </p>
        ) : moodTrendData.length === 0 ? (
          <p className="py-12 text-center text-slate-500">
            No analyzed diary entries for this month.
          </p>
        ) : (
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={moodTrendData}
                margin={{
                  top: 10,
                  right: 20,
                  left: -20,
                  bottom: 20,
                }}
              >
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="#e2e8f0"
                />

                <XAxis
                  dataKey="day"
                  type="number"
                  domain={[1, daysInMonth]}
                  ticks={[1, 5, 10, 15, 20, 25, daysInMonth]}
                  tickLine={false}
                  tick={{ fontSize: 12 }}
                  label={{
                    value: "Day of month",
                    position: "insideBottom",
                    offset: -10,
                  }}
                />

                <YAxis
                  domain={[0, 10]}
                  ticks={[0, 2, 4, 6, 8, 10]}
                  tick={{ fontSize: 12 }}
                />

                <Tooltip
                  labelFormatter={(day) =>
                    `Day ${day} of ${monthLabel}`
                  }
                  formatter={(value) => [
                    `${value}/10`,
                    "Average Mood",
                  ]}
                />

                <Line
                  type="monotone"
                  dataKey="score"
                  stroke="#6366f1"
                  strokeWidth={3}
                  dot={{
                    r: 5,
                    fill: "#6366f1",
                  }}
                  activeDot={{ r: 7 }}
                  connectNulls={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* ------------------------------------ */}
      {/* Calendar */}
      {/* ------------------------------------ */}

      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm md:p-8">
        {/* Month Navigation */}
        <div className="mb-6 flex items-center justify-between">
          <h3 className="text-xl font-bold text-slate-800">
            {monthLabel}
          </h3>

          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => changeMonth(-1)}
              aria-label="Previous month"
              className="rounded-lg border border-slate-200 px-4 py-2 hover:bg-slate-50"
            >
              ←
            </button>

            <button
              type="button"
              onClick={() => changeMonth(1)}
              aria-label="Next month"
              className="rounded-lg border border-slate-200 px-4 py-2 hover:bg-slate-50"
            >
              →
            </button>
          </div>
        </div>

        {/* Calendar Grid */}
        <div className="grid grid-cols-7 gap-2">
          {/* Weekday Headers */}
          {[
            "Sun",
            "Mon",
            "Tue",
            "Wed",
            "Thu",
            "Fri",
            "Sat",
          ].map((day) => (
            <div
              key={day}
              className="py-2 text-center text-xs font-semibold text-slate-500"
            >
              {day}
            </div>
          ))}

          {/* Empty Cells */}
          {Array.from(
            { length: firstDay },
            (_, index) => (
              <div key={`empty-${index}`} />
            )
          )}

          {/* Calendar Days */}
          {Array.from(
            { length: daysInMonth },
            (_, index) => {
              const day = index + 1;
              const dateString = formatDate(day);

              const dayEntries = entries.filter(
                (entry) =>
                  entry.entry_date === dateString
              );

              const dayAnalyzedEntries = dayEntries.filter(
                (entry) =>
                  entry.mood &&
                  entry.mood_score != null
              );

              // Use highest-scoring entry for calendar color
              const dominantEntry =
                dayAnalyzedEntries.length > 0
                  ? dayAnalyzedEntries.reduce(
                      (highest, current) =>
                        (current.mood_score ?? 0) >
                        (highest.mood_score ?? 0)
                          ? current
                          : highest
                    )
                  : null;

              const moodColor = dominantEntry
                ? getMoodColor(dominantEntry.mood)
                : "bg-white border-slate-100 text-slate-800";

              const isSelected =
                selectedDate === dateString;

              return (
                <button
                  key={dateString}
                  type="button"
                  onClick={() =>
                    setSelectedDate(dateString)
                  }
                  aria-label={`${dateString}, ${dayEntries.length} diary entries${
                    dominantEntry?.mood
                      ? `, mood ${dominantEntry.mood}`
                      : ""
                  }`}
                  aria-pressed={isSelected}
                  className={`flex min-h-16 flex-col items-center justify-center rounded-xl border p-2 transition hover:brightness-95 ${
                    dayEntries.length > 0
                      ? moodColor
                      : "border-slate-100 bg-white text-slate-800"
                  } ${
                    isSelected
                      ? "ring-2 ring-indigo-500 ring-offset-2"
                      : ""
                  }`}
                >
                  <span className="text-sm font-semibold">
                    {day}
                  </span>

                  {dayEntries.length > 0 && (
                    <>
                      <span className="mt-1 text-[10px] font-medium">
                        {dayEntries.length}{" "}
                        {dayEntries.length === 1
                          ? "entry"
                          : "entries"}
                      </span>

                      {dominantEntry?.mood && (
                        <span className="mt-1 max-w-full truncate text-[10px] font-semibold">
                          {dominantEntry.mood}
                        </span>
                      )}
                    </>
                  )}
                </button>
              );
            }
          )}
        </div>
      </div>

      {/* ------------------------------------ */}
      {/* Selected Day Entries */}
      {/* ------------------------------------ */}

      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h3 className="mb-5 text-lg font-bold text-slate-800">
          Entries for {selectedDate}
        </h3>

        {loading ? (
          <p className="text-slate-500">
            Loading diary entries...
          </p>
        ) : error ? (
          <p className="text-red-600">
            {error}
          </p>
        ) : selectedEntries.length === 0 ? (
          <p className="text-sm text-slate-500">
            No diary entries for this date.
          </p>
        ) : (
          <div className="space-y-4">
            {selectedEntries.map((entry) => (
              <div
                key={entry.id}
                className="rounded-xl border border-slate-200 bg-slate-50 p-5"
              >
                <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                  <h4 className="font-semibold text-slate-800">
                    {entry.title}
                  </h4>

                  {entry.mood && (
                    <span
                      className={`rounded-full border px-3 py-1 text-xs font-medium ${getMoodColor(
                        entry.mood
                      )}`}
                    >
                      {entry.mood}

                      {entry.mood_score != null &&
                        ` · ${entry.mood_score}/10`}
                    </span>
                  )}
                </div>

                <p className="whitespace-pre-wrap text-sm leading-7 text-slate-600">
                  {entry.content}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default DiaryCalendar;
