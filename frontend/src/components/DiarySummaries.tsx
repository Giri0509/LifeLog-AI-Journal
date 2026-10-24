import { apiFetch } from "../api";
import { useState } from "react";

interface SummaryResult {
  status: "complete" | "insufficient_data" | "partial";
  start_date: string;
  end_date: string;
  entry_count: number;
  journaled_days: number;
  summary?: string;
  message?: string;
  emotion_entry_count?: number;
  emotions?: { emotion: string; count: number }[];
  highest_days?: { date: string; average: number; entry_count: number }[];
  lowest_days?: { date: string; average: number; entry_count: number }[];
  themes?: { title: string; observation: string; sources: { entry_id: number; entry_date: string }[] }[];
  sources: { entry_id: number; entry_date: string }[];
}

export default function DiarySummaries({ insights = false }: { insights?: boolean }) {
  const [period, setPeriod] = useState("weekly");
  const [anchorDate, setAnchorDate] = useState(() => {
    const today = new Date();
    return `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
  });
  const [result, setResult] = useState<SummaryResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const generate = async () => {
    if (!anchorDate || loading) return;
    setLoading(true);
    setResult(null);
    setError("");
    try {
      const response = await apiFetch(`http://localhost:8000/api/diary-${insights ? "insights" : "summary"}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ period, anchor_date: anchorDate }),
        signal: AbortSignal.timeout(90000),
      });
      if (!response.ok) {
        const data = await response.json().catch(() => null);
        throw new Error(typeof data?.detail === "string" ? data.detail : "Unable to generate a summary. Please try again.");
      }
      const data = await response.json();
      setResult({ ...data, sources: data.sources ?? [] });
    } catch (err) {
      setError(err instanceof Error && err.name !== "TimeoutError" ? err.message : "The request timed out. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <p className="mb-2 text-sm font-medium text-indigo-600">REFLECT ON YOUR JOURNEY</p>
        <h2 className="text-3xl font-bold text-slate-800">{insights ? "AI Insights" : "Diary Summaries"}</h2>
        <p className="mt-2 text-slate-500">Explore significant events, recurring themes, and mood changes from your entries.</p>
      </div>
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-wrap items-end gap-4">
          <label className="text-sm font-medium text-slate-600">
            Period
            <select value={period} disabled={loading} onChange={(e) => { setPeriod(e.target.value); setResult(null); setError(""); }} className="mt-2 block rounded-xl border border-slate-200 p-3">
              <option value="weekly">Weekly</option>
              <option value="monthly">Monthly</option>
            </select>
          </label>
          <label className="text-sm font-medium text-slate-600">
            A date within the period
            <input type="date" required value={anchorDate} disabled={loading} onChange={(e) => { setAnchorDate(e.target.value); setResult(null); setError(""); }} className="mt-2 block rounded-xl border border-slate-200 p-3" />
          </label>
          <button type="button" onClick={generate} disabled={loading || !anchorDate} className="rounded-xl bg-indigo-600 px-6 py-3 font-semibold text-white hover:bg-indigo-700 disabled:opacity-50">
            {loading ? "Generating..." : (insights ? "Explore Insights" : "Generate Summary")}
          </button>
        </div>
        <p className="mt-4 text-sm text-slate-500">Weeks run Monday–Sunday. Months cover the full calendar month. At least two journaled days are needed.</p>
        <p className="mt-2 text-xs text-slate-400">Generating sends entries from this period to your configured AI provider. Results are generated on demand and are not saved.</p>
      </div>
      {error && <p role="alert" className="rounded-xl bg-red-50 p-4 text-red-700">{error}</p>}
      <div aria-live="polite" aria-busy={loading}>
        {loading ? <p className="text-slate-500">Reading your entries and preparing a reflection...</p> : result ? (
          <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <h3 className="text-lg font-bold">{insights ? "Your Emotion Patterns" : result.status === "complete" ? "Your Reflection" : "More entries needed"}</h3>
            <p className="mt-2 text-sm text-slate-500">{result.start_date} to {result.end_date} · {result.entry_count} entries across {result.journaled_days} days</p>
                        {insights ? <>
              <p role="status" className="mt-4 text-sm text-slate-600">{result.message}</p>
              <h4 className="mt-6 font-semibold">Most frequent emotions</h4>
              <p className="mt-1 text-xs text-slate-500">Counts are entries containing each saved AI emotion label. {result.emotion_entry_count} entries have emotion labels. Similar labels are counted separately.</p>
              <div className="mt-3 flex flex-wrap gap-2">{result.emotions?.length ? result.emotions.map((item) => <span key={item.emotion} className="rounded-full bg-indigo-50 px-3 py-1 text-sm text-indigo-700">{item.emotion}: {item.count}</span>) : <p className="text-sm text-slate-500">No analyzed emotions in this period.</p>}</div>
              <div className="mt-6 grid gap-4 sm:grid-cols-2">
                {[{ label: "Highest mood days", days: result.highest_days }, { label: "Lowest mood days", days: result.lowest_days }].map((group) => <div key={group.label} className="rounded-xl bg-slate-50 p-4">
                  <h4 className="font-semibold">{group.label}</h4>
                  {group.days?.length ? group.days.map((day) => <p key={day.date} className="mt-2 text-sm">{day.date}: {day.average}/10 ({day.entry_count} analyzed entries)</p>) : <p className="mt-2 text-sm text-slate-500">No valid mood scores.</p>}
                </div>)}
              </div>
              <p className="mt-2 text-xs text-slate-500">Based on daily averages of saved scores. Tied days appear in both groups; these are relative highs and lows, not diagnoses.</p>
              <h4 className="mt-6 font-semibold">Recurring themes</h4>
              {result.themes?.map((theme, index) => <article key={index} className="mt-3 rounded-xl border border-slate-200 p-4">
                <h5 className="font-medium text-indigo-700">{theme.title}</h5>
                <p className="mt-2 whitespace-pre-wrap text-sm leading-6">{theme.observation}</p>
                <p className="mt-3 text-xs text-slate-500">Supporting diary dates: {[...new Set(theme.sources.map((source) => source.entry_date))].join(", ")}</p>
              </article>)}
              {!result.themes?.length && <p className="mt-2 text-sm text-slate-500">No themes available. {result.status === "partial" ? "Use Explore Insights to retry." : "More entries may help reveal recurring themes."}</p>}
            </> : <p className="mt-5 whitespace-pre-wrap leading-7 text-slate-700">{result.summary}</p>}
            {result.sources.length > 0 && <div className="mt-6 border-t border-slate-100 pt-4">
              <p className="text-sm font-semibold text-slate-600">Diary dates included</p>
              <div className="mt-2 flex flex-wrap gap-2">{[...new Set(result.sources.map((source) => source.entry_date))].map((date) => <span key={date} className="rounded-full bg-indigo-50 px-3 py-1 text-xs text-indigo-700">{date}</span>)}</div>
            </div>}
          </section>
        ) : <p className="text-slate-500">Choose a period to explore your diary.</p>}
      </div>
    </div>
  );
}

