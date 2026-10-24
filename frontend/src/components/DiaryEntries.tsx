import { apiFetch, responseError } from "../api";

import { useEffect, useState } from "react";


interface DiaryEntry {
  id: number;
  title: string;
  content: string;
  entry_date: string;
  mood?: string | null;
  mood_score?: number | null;
  emotions?: string[] | null;
  ai_summary?: string | null;
}


function DiaryEntries() {
  const [entries, setEntries] = useState<DiaryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [editingEntry, setEditingEntry] = useState<DiaryEntry | null>(null);
  const [isUpdating, setIsUpdating] = useState(false);
  const [notice, setNotice] = useState("");
  const [search, setSearch] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [moodFilter, setMoodFilter] = useState("");
  const [sort, setSort] = useState("date_desc");

  const clearFilters = () => {
    setSearch("");
    setStartDate("");
    setEndDate("");
    setMoodFilter("");
    setSort("date_desc");
  };
  const invalidRange = Boolean(startDate && endDate && startDate > endDate);
  const normalizedSearch = search.trim().toLocaleLowerCase();
  const moodOptions = [...new Set([
    ...entries.map((entry) => entry.mood?.trim().toLocaleLowerCase() ?? ""),
    ...(moodFilter.startsWith("mood:") ? [moodFilter.slice(5)] : []),
  ])].filter(Boolean).sort((a, b) => a.localeCompare(b));
  const visibleEntries = entries.filter((entry) => {
    const mood = entry.mood?.trim().toLocaleLowerCase() ?? "";
    return !invalidRange
      && (!normalizedSearch || entry.title.toLocaleLowerCase().includes(normalizedSearch) || entry.content.toLocaleLowerCase().includes(normalizedSearch))
      && (!startDate || entry.entry_date >= startDate)
      && (!endDate || entry.entry_date <= endDate)
      && (!moodFilter || (moodFilter === "unanalyzed" ? !mood : mood === moodFilter.slice(5)));
  }).sort((a, b) => {
    const dateOrder = a.entry_date.localeCompare(b.entry_date);
    if (sort === "date_asc") return dateOrder || a.id - b.id;
    if (sort === "title_asc") return a.title.localeCompare(b.title, undefined, { sensitivity: "base" }) || -dateOrder || b.id - a.id;
    if (sort === "mood_desc" || sort === "mood_asc") {
      // Entries without a finite score always sort last in either direction.
      const aScore = a.mood_score;
      const bScore = b.mood_score;
      const aValid = aScore != null && Number.isFinite(aScore);
      const bValid = bScore != null && Number.isFinite(bScore);
      if (aValid !== bValid) return aValid ? -1 : 1;
      if (aValid && bValid && aScore !== bScore) return sort === "mood_desc" ? bScore - aScore : aScore - bScore;
    }
    return -dateOrder || b.id - a.id;
  });

  useEffect(() => {
    const fetchEntries = async () => {
      try {
        const response = await apiFetch(
          "http://localhost:8000/api/diary"
        );

        if (!response.ok) {
          throw new Error("Failed to fetch entries");
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

  
  const deleteEntry = async (id: number) => {
    const confirmed = window.confirm(
      "Are you sure you want to delete this diary entry?"
    );

    if (!confirmed) {
      return;
    }

    try {
      const response = await apiFetch(
        `http://localhost:8000/api/diary/${id}`,
        {
          method: "DELETE",
        }
      );

      if (!response.ok) {
        throw await responseError(response, "Unable to delete diary entry.");
      }

      // Update the UI without refreshing the page
      setEntries((previousEntries) =>
        previousEntries.filter((entry) => entry.id !== id)
      );
    } catch (error) {
      console.error(error);
      window.alert(error instanceof Error ? error.message : "Unable to delete diary entry.");
    }
  };

  
  const updateEntry = async () => {
    if (!editingEntry) return;

    if (!editingEntry.title.trim() || !editingEntry.content.trim()) {
      window.alert("Title and content cannot be empty.");
      return;
    }

    try {
      setIsUpdating(true);

      const response = await apiFetch(
        `http://localhost:8000/api/diary/${editingEntry.id}`,
        {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            title: editingEntry.title,
            content: editingEntry.content,
            entry_date: editingEntry.entry_date,
          }),
        }
      );

      if (!response.ok) {
        throw await responseError(response, "Unable to update diary entry.");
      }

      const data = await response.json();

      setEntries((previousEntries) =>
        previousEntries.map((entry) =>
          entry.id === editingEntry.id
            ? { ...entry, ...data.entry }
            : entry
        )
      );

      setEditingEntry(null);
      setNotice(["Entry updated.", ...(data.warnings ?? [])].join(" "));
    } catch (error) {
      console.error(error);
      window.alert(error instanceof Error ? error.message : "Unable to update diary entry.");
    } finally {
      setIsUpdating(false);
    }
  };


  if (loading) {
    return <p className="text-slate-500">Loading entries...</p>;
  }

  if (error) {
    return <p className="text-red-600">{error}</p>;
  }

  return (
    <div>
      <h2 className="mb-2 text-3xl font-bold">
        My Diary Entries 📖
      </h2>

      <p className="mb-8 text-slate-500">
        A collection of your thoughts and memories.
      </p>

      {notice && <p role="status" className="mb-4 rounded-xl bg-indigo-50 p-4 text-sm text-indigo-700">{notice}</p>}

      {entries.length > 0 && (
        <section aria-label="Search and filter diary entries" className="mb-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <label htmlFor="diary-search" className="block text-sm font-semibold text-slate-600">Search title or content</label>
          <input id="diary-search" type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search your memories..." className="mt-2 w-full rounded-xl border border-slate-200 p-3 outline-none focus:border-indigo-500" />
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <label className="text-sm font-medium text-slate-600">
              From date
              <input type="date" value={startDate} aria-invalid={invalidRange} aria-describedby={invalidRange ? "date-range-error" : undefined} onChange={(event) => setStartDate(event.target.value)} className="mt-2 block w-full rounded-xl border border-slate-200 p-3" />
            </label>
            <label className="text-sm font-medium text-slate-600">
              To date
              <input type="date" value={endDate} aria-invalid={invalidRange} aria-describedby={invalidRange ? "date-range-error" : undefined} onChange={(event) => setEndDate(event.target.value)} className="mt-2 block w-full rounded-xl border border-slate-200 p-3" />
            </label>
            <label className="text-sm font-medium text-slate-600">
              Mood
              <select value={moodFilter} onChange={(event) => setMoodFilter(event.target.value)} className="mt-2 block w-full rounded-xl border border-slate-200 p-3 capitalize">
                <option value="">All moods</option>
                <option value="unanalyzed">Unanalyzed</option>
                {moodOptions.map((mood) => <option key={mood} value={`mood:${mood}`}>{mood}</option>)}
              </select>
            </label>
            <label className="text-sm font-medium text-slate-600">
              Sort by
              <select value={sort} onChange={(event) => setSort(event.target.value)} className="mt-2 block w-full rounded-xl border border-slate-200 p-3">
                <option value="date_desc">Newest date first</option>
                <option value="date_asc">Oldest date first</option>
                <option value="title_asc">Title A–Z</option>
                <option value="mood_desc">Highest mood score first</option>
                <option value="mood_asc">Lowest mood score first</option>
              </select>
            </label>
          </div>
          {invalidRange && <p id="date-range-error" role="alert" className="mt-3 text-sm text-red-600">From date must be on or before To date.</p>}
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
            <p role="status" className="text-sm text-slate-500">{invalidRange ? "Choose a valid date range." : `${visibleEntries.length} of ${entries.length} entries`}</p>
            <button type="button" onClick={clearFilters} className="rounded-lg bg-indigo-50 px-4 py-2 text-sm font-semibold text-indigo-700 hover:bg-indigo-100">Clear filters</button>
          </div>
        </section>
      )}

      {entries.length === 0 ? (
        <div className="rounded-2xl bg-white p-10 text-center shadow-sm">
          <p className="text-lg text-slate-500">
            No diary entries yet.
          </p>
          <p className="mt-2 text-sm text-slate-400">
            Start writing to capture your memories.
          </p>
        </div>
      ) : invalidRange ? null : visibleEntries.length === 0 ? (
        <div className="rounded-2xl bg-white p-10 text-center shadow-sm">
          <p className="text-lg text-slate-500">No entries match your filters.</p>
          <p className="mt-2 text-sm text-slate-400">Try a different search, mood, or date range.</p>
          <button type="button" onClick={clearFilters} className="mt-4 rounded-lg bg-indigo-50 px-4 py-2 font-medium text-indigo-700">Clear filters</button>
        </div>
      ) : (
        <div className="grid gap-5 md:grid-cols-2">
          {visibleEntries.map((entry) => (
            <div
              key={entry.id}
              className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm transition hover:shadow-md"
            >
              <p className="mb-3 text-sm font-medium text-indigo-600">
                📅 {entry.entry_date}
              </p>

              <h3 className="mb-3 text-xl font-semibold text-slate-800">
                {entry.title}
              </h3>

              <p className="whitespace-pre-wrap break-words text-sm leading-7 text-slate-600">
                {entry.content}
              </p>

              
                {/* AI Mood Analysis */}
                {entry.mood && (
                  <div className="mt-5 rounded-xl border border-indigo-100 bg-indigo-50/60 p-4">
                    <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                      <span className="text-sm font-semibold text-indigo-700">
                        ✨ AI Mood Analysis
                      </span>

                      <span className="rounded-full bg-white px-3 py-1 text-sm font-medium text-indigo-700">
                        {entry.mood}
                      </span>
                    </div>

                    {entry.mood_score != null && (
                      <div className="mb-4">
                        <div className="mb-2 flex justify-between text-sm">
                          <span className="text-slate-600">Mood Score</span>
                          <span className="font-semibold text-indigo-700">
                            {entry.mood_score}/10
                          </span>
                        </div>

                        <div className="h-2 overflow-hidden rounded-full bg-indigo-100">
                          <div
                            className="h-full rounded-full bg-indigo-500"
                            style={{
                              width: `${Math.max(
                                0,
                                Math.min(100, entry.mood_score * 10)
                              )}%`,
                            }}
                          />
                        </div>
                      </div>
                    )}

                    {entry.emotions && entry.emotions.length > 0 && (
                      <div className="mb-3 flex flex-wrap gap-2">
                        {entry.emotions.map((emotion, index) => (
                          <span
                            key={index}
                            className="rounded-full bg-white px-3 py-1 text-xs font-medium capitalize text-slate-600"
                          >
                            {emotion}
                          </span>
                        ))}
                      </div>
                    )}

                    {entry.ai_summary && (
                      <p className="text-sm italic leading-6 text-slate-600">
                        "{entry.ai_summary}"
                      </p>
                    )}
                  </div>
                )}

         
            
              <div className="mt-6 flex justify-end gap-3 border-t border-slate-100 pt-4">
                <button
                  type="button"
                  onClick={() => setEditingEntry({ ...entry })}
                  className="rounded-lg border border-indigo-200 px-4 py-2 text-sm font-medium text-indigo-600 transition hover:bg-indigo-50"
                >
                  ✏️ Edit
                </button>

                <button
                  type="button"
                  onClick={() => deleteEntry(entry.id)}
                  className="rounded-lg border border-red-200 px-4 py-2 text-sm font-medium text-red-600 transition hover:bg-red-50"
                >
                  🗑️ Delete
                </button>
              </div>


            </div>
          ))}
        </div>
      )}
      
      {editingEntry && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="edit-diary-title"
            className="w-full max-w-xl rounded-2xl bg-white p-6 shadow-xl"
          >
            <h3
              id="edit-diary-title"
              className="mb-6 text-2xl font-bold"
            >
              ✏️ Edit Diary Entry
            </h3>

            <label className="mb-2 block text-sm font-semibold">
              Title
            </label>
            <input
              type="text"
              value={editingEntry.title}
              maxLength={255}
              onChange={(e) =>
                setEditingEntry({
                  ...editingEntry,
                  title: e.target.value,
                })
              }
              className="mb-5 w-full rounded-xl border border-slate-200 p-3 outline-none focus:border-indigo-500"
            />

            <label className="mb-2 block text-sm font-semibold">
              Date
            </label>
            <input
              type="date"
              value={editingEntry.entry_date}
              onChange={(e) =>
                setEditingEntry({
                  ...editingEntry,
                  entry_date: e.target.value,
                })
              }
              className="mb-5 rounded-xl border border-slate-200 p-3"
            />

            <label className="mb-2 block text-sm font-semibold">
              Content
            </label>
            <textarea
              rows={8}
              value={editingEntry.content}
              maxLength={20000}
              onChange={(e) =>
                setEditingEntry({
                  ...editingEntry,
                  content: e.target.value,
                })
              }
              className="mb-6 w-full rounded-xl border border-slate-200 p-3 outline-none focus:border-indigo-500"
            />

            <div className="flex justify-end gap-3">
              <button
                type="button"
                disabled={isUpdating}
                onClick={() => setEditingEntry(null)}
                className="rounded-xl border border-slate-200 px-5 py-3 font-medium disabled:opacity-50"
              >
                Cancel
              </button>

              <button
                type="button"
                disabled={isUpdating}
                onClick={updateEntry}
                className="rounded-xl bg-indigo-600 px-5 py-3 font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
              >
                {isUpdating ? "Saving..." : "Save Changes"}
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}

export default DiaryEntries;

