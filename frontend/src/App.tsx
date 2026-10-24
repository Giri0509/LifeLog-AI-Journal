import { apiFetch, responseError } from "./api";

import { useState } from "react";
import DiaryEntries from "./components/DiaryEntries";
import MoodAnalytics from "./components/MoodAnalytics";
import AIChatbot from "./components/AIChatbot";
import DiaryCalendar from "./components/DiaryCalendar";
import DiarySummaries from "./components/DiarySummaries";

function App() {
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [entryDate, setEntryDate] = useState(
    new Date().toLocaleDateString("en-CA")
  );
  const [message, setMessage] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [activePage, setActivePage] = useState("write");

  const saveDiary = async () => {
    if (!title.trim() || !content.trim()) {
      setMessage("Please enter a title and diary content.");
      return;
    }

    try {
      setIsSaving(true);
      setMessage("");

      const response = await apiFetch(
        "http://localhost:8000/api/diary",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            title,
            content,
            entry_date: entryDate,
          }),
        }
      );

      if (!response.ok) {
        throw await responseError(response, "Unable to save your diary. Please try again.");
      }

      const data = await response.json();
      setMessage([data.message || "Diary saved successfully!", ...(data.warnings ?? [])].join(" "));
      setTitle("");
      setContent("");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to save your diary. Please try again.");
      console.error(error);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#F8F9FC] text-slate-800">
      {/* Sidebar */}
      <aside className="fixed left-0 top-0 hidden h-screen w-64 border-r border-slate-200 bg-white p-6 md:block">
        {/* Logo */}
        <div className="mb-12 flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-indigo-600 text-2xl text-white">
            ✦
          </div>

          <h1 className="text-xl font-bold">
            LifeLog AI
          </h1>
        </div>

        {/* Navigation */}
        <nav className="space-y-2">
          {/* Write Diary */}
          <button
            type="button"
            onClick={() => setActivePage("write")}
            className={`w-full rounded-xl px-4 py-3 text-left font-medium transition ${
              activePage === "write"
                ? "bg-indigo-50 text-indigo-700"
                : "text-slate-500 hover:bg-slate-50"
            }`}
          >
            ✍️ Write Diary
          </button>

          {/* My Entries */}
          <button
            type="button"
            onClick={() => setActivePage("entries")}
            className={`w-full rounded-xl px-4 py-3 text-left font-medium transition ${
              activePage === "entries"
                ? "bg-indigo-50 text-indigo-700"
                : "text-slate-500 hover:bg-slate-50"
            }`}
          >
            📖 My Entries
          </button>

          {/* Calendar */}
          
<button
  type="button"
  onClick={() => setActivePage("calendar")}
  className={`w-full rounded-xl px-4 py-3 text-left font-medium transition ${
    activePage === "calendar"
      ? "bg-indigo-50 text-indigo-700"
      : "text-slate-500 hover:bg-slate-50"
  }`}
>
  📅 Calendar
</button>


          {/* Mood Analytics */}
          <button
            type="button"
            onClick={() => setActivePage("analytics")}
            className={`w-full rounded-xl px-4 py-3 text-left font-medium transition ${
              activePage === "analytics"
                ? "bg-indigo-50 text-indigo-700"
                : "text-slate-500 hover:bg-slate-50"
            }`}
          >
            📊 Mood Analytics
          </button>

          <button
            type="button"
            onClick={() => setActivePage("summaries")}
            className={`w-full rounded-xl px-4 py-3 text-left font-medium transition ${activePage === "summaries" ? "bg-indigo-50 text-indigo-700" : "text-slate-500 hover:bg-slate-50"}`}
          >
            📝 Diary Summaries
          </button>

          <button
            type="button"
            onClick={() => setActivePage("insights")}
            className={`w-full rounded-xl px-4 py-3 text-left font-medium transition ${activePage === "insights" ? "bg-indigo-50 text-indigo-700" : "text-slate-500 hover:bg-slate-50"}`}
          >
            💡 AI Insights
          </button>

          {/* AI Chatbot */}
          <button
            type="button"
            onClick={() => setActivePage("chat")}
            className={`w-full rounded-xl px-4 py-3 text-left font-medium transition ${
              activePage === "chat"
                ? "bg-indigo-50 text-indigo-700"
                : "text-slate-500 hover:bg-slate-50"
            }`}
          >
            💬 AI Chatbot
          </button>
        </nav>

        {/* Sidebar Footer */}
        <div className="absolute bottom-8 left-6 right-6 rounded-xl bg-indigo-50 p-4">
          <p className="font-semibold text-indigo-800">
            Your personal space
          </p>

          <p className="mt-1 text-sm text-indigo-600">
            Every day has a story worth remembering.
          </p>
        </div>
      </aside>

      {/* Main Content */}
      <main className="min-h-screen p-5 md:ml-64 md:p-10">
        {activePage === "entries" ? (
          /* My Entries Page */
          <div className="mx-auto max-w-4xl">
            <DiaryEntries />
          </div>
        
) : activePage === "analytics" ? (
  <div className="mx-auto max-w-5xl">
    <MoodAnalytics />
  </div>
) : activePage === "calendar" ? (
  <div className="mx-auto max-w-5xl">
    <DiaryCalendar />
  </div>
) : activePage === "summaries" ? (
  <DiarySummaries key="summaries" />
) : activePage === "insights" ? (
  <DiarySummaries key="insights" insights />
) : activePage === "chat" ? (

          /* AI Chatbot Page */
          <div className="mx-auto max-w-5xl">
            <AIChatbot />
          </div>
        ) : (
          /* Write Diary Page */
          <div className="mx-auto max-w-4xl">
            {/* Header */}
            <div className="mb-8">
              <p className="mb-2 text-sm font-medium text-indigo-600">
                YOUR PERSONAL JOURNAL
              </p>

              <h2 className="text-3xl font-bold tracking-tight md:text-4xl">
                Write Your Story ✨
              </h2>

              <p className="mt-3 text-slate-500">
                Take a moment to reflect on your day.
                Your thoughts matter.
              </p>
            </div>

            {/* Diary Editor */}
            <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm md:p-10">
              <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
                <div>
                  <h3 className="text-xl font-semibold">
                    New Journal Entry
                  </h3>

                  <p className="mt-1 text-sm text-slate-400">
                    Capture your thoughts and memories.
                  </p>
                </div>

                <div className="rounded-xl bg-indigo-50 px-4 py-2 text-sm font-medium text-indigo-700">
                  ✍️ Daily Reflection
                </div>
              </div>

              {/* Title */}
              <div className="mb-6">
                <label
                  htmlFor="diary-title"
                  className="mb-2 block text-sm font-semibold"
                >
                  Entry Title
                </label>

                <input
                  id="diary-title"
                  type="text"
                  value={title}
                  maxLength={255}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="Give your day a title..."
                  className="w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none transition focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100"
                />
              </div>

              {/* Date */}
              <div className="mb-6">
                <label
                  htmlFor="diary-date"
                  className="mb-2 block text-sm font-semibold"
                >
                  Date
                </label>

                <input
                  id="diary-date"
                  type="date"
                  value={entryDate}
                  onChange={(e) => setEntryDate(e.target.value)}
                  className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none focus:border-indigo-500"
                />
              </div>

              {/* Content */}
              <div className="mb-6">
                <label
                  htmlFor="diary-content"
                  className="mb-2 block text-sm font-semibold"
                >
                  How was your day?
                </label>

                <textarea
                  id="diary-content"
                  value={content}
                  maxLength={20000}
                  onChange={(e) => setContent(e.target.value)}
                  rows={12}
                  placeholder="Dear diary, today was..."
                  className="w-full resize-y rounded-xl border border-slate-200 bg-slate-50 p-5 leading-7 outline-none transition focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100"
                />

                <p className="mt-2 text-right text-xs text-slate-400">
                  {content.length}/20,000 characters
                </p>
              </div>

              {/* Save Button */}
              <div className="flex flex-wrap items-center justify-between gap-4 border-t border-slate-100 pt-6">
                <p className="text-sm text-slate-400">
                  Your journey, one day at a time.
                </p>

                <button
                  type="button"
                  onClick={saveDiary}
                  disabled={isSaving}
                  className="rounded-xl bg-indigo-600 px-7 py-3 font-semibold text-white shadow-sm transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {isSaving ? "Saving..." : "Save Entry →"}
                </button>
              </div>

              {/* Save Feedback */}
              {message && (
                <div
                  role="status"
                  className="mt-5 rounded-xl bg-indigo-50 p-4 text-sm font-medium text-indigo-700"
                >
                  {message}
                </div>
              )}
            </div>

            {/* Footer */}
            <p className="mt-6 text-center text-sm text-slate-400">
              Made for reflection, growth, and self-discovery.
            </p>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;


