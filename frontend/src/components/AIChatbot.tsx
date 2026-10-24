import { apiFetch } from "../api";
import { useEffect, useState, type FormEvent } from "react";

interface DiarySource {
  entry_id: number;
  title: string;
  entry_date: string;
  excerpt?: string;
}
interface ChatMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  sources?: DiarySource[];
}
interface Conversation {
  id: number;
  title: string;
}
const api = "http://localhost:8000/api/conversations";
async function request(url: string, options?: RequestInit) {
  const response = await apiFetch(url, options);
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(typeof data?.detail === "string" ? data.detail : "Unable to load or save chat. Please try again.");
  }
  return response.json();
}

function AIChatbot() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(true);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    const initialize = async () => {
      try {
        const data = await request(api, { signal: controller.signal });
        if (controller.signal.aborted) return;
        setConversations(data.conversations);
        if (data.conversations.length > 0) {
          const first = data.conversations[0];
          const chat = await request(`${api}/${first.id}/messages`, { signal: controller.signal });
          if (controller.signal.aborted) return;
          setActiveId(first.id);
          setMessages(chat.messages);
        }
        setReady(true);
      } catch (err) {
        if (!controller.signal.aborted) setError(err instanceof Error ? err.message : "Unable to restore chats.");
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    };
    void initialize();
    return () => controller.abort();
  }, []);

  const openConversation = async (id: number) => {
    if (loading) return;
    setLoading(true);
    setError("");
    try {
      const data = await request(`${api}/${id}/messages`);
      setActiveId(id);
      setMessages(data.messages);
      setQuestion("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to open chat.");
    } finally {
      setLoading(false);
    }
  };

  const newChat = () => {
    if (loading) return;
    setActiveId(null);
    setMessages([]);
    setQuestion("");
    setError("");
  };

  const sendMessage = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const text = question.trim();
    if (!text || loading || !ready) return;
    setError("");
    setLoading(true);
    try {
      let id = activeId;
      if (id === null) {
        const conversation: Conversation = await request(api, { method: "POST" });
        id = conversation.id;
        setActiveId(id);
        setConversations((previous) => [conversation, ...previous]);
      }
      const data = await request(`${api}/${id}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: text }),
      });
      setMessages((previous) => [...previous, ...data.messages]);
      setConversations((previous) => [data.conversation, ...previous.filter((item) => item.id !== id)]);
      setQuestion("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save a response. Please try again.");
    } finally {
      setLoading(false);
    }
  };
  return (
    <div className="flex h-[calc(100vh-140px)] min-h-[500px] flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      {/* Header */}
      <div className="border-b border-slate-200 px-6 py-5">
        <h2 className="text-2xl font-bold text-slate-800">
          ✨ AI Diary Chatbot
        </h2>

        <p className="mt-1 text-sm text-slate-500">
          Ask questions about your memories, experiences, and moods. Chats are saved automatically.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-3 border-b border-slate-200 px-6 py-3">
        <label htmlFor="conversation" className="text-sm font-medium text-slate-600">Saved chats</label>
        <select id="conversation" aria-label="Saved conversations" value={activeId ?? ""} disabled={loading || !ready} onChange={(event) => { if (event.target.value) void openConversation(Number(event.target.value)); }} className="min-w-0 flex-1 rounded-lg border border-slate-200 p-2 text-sm">
          <option value="" disabled>New conversation</option>
          {conversations.map((conversation) => <option key={conversation.id} value={conversation.id}>{conversation.title}</option>)}
        </select>
        <button type="button" onClick={newChat} disabled={loading || !ready} className="rounded-lg bg-indigo-50 px-4 py-2 text-sm font-semibold text-indigo-700 disabled:opacity-50">New Chat</button>
      </div>

      {/* Chat Messages */}
      <div
        className="flex-1 space-y-5 overflow-y-auto bg-slate-50 p-6"
        aria-live="polite"
      >
        {messages.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center text-center">
            <div className="mb-4 text-5xl">💬</div>

            <h3 className="text-xl font-semibold text-slate-800">
              Chat with your diary
            </h3>

            <p className="mt-2 max-w-md text-sm text-slate-500">
              Ask LifeLog AI about your experiences and discover
              patterns in your journal entries.
            </p>

            <div className="mt-6 space-y-2 text-sm text-indigo-600">
              <p>What made me happy recently?</p>
              <p>What challenges have I faced?</p>
              <p>What were my recent accomplishments?</p>
            </div>
          </div>
        )}

        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex ${
              message.role === "user"
                ? "justify-end"
                : "justify-start"
            }`}
          >
            <div
              className={`max-w-[85%] rounded-2xl px-5 py-4 shadow-sm ${
                message.role === "user"
                  ? "bg-indigo-600 text-white"
                  : "border border-slate-200 bg-white text-slate-800"
              }`}
            >
              <p className="whitespace-pre-wrap text-sm leading-7">
                {message.content}
              </p>

              {/* Diary Sources */}
              {message.role === "assistant" &&
                message.sources &&
                message.sources.length > 0 && (
                  <div className="mt-4 border-t border-slate-200 pt-3">
                    <p className="mb-2 text-xs font-semibold text-slate-500">
                      📚 DIARY SOURCES
                    </p>

                    <div className="flex flex-wrap gap-2">
                      {message.sources.map((source) => (
                        <span
                          key={source.entry_id}
                          title={source.excerpt}
                          className="rounded-lg bg-indigo-50 px-3 py-2 text-xs text-indigo-700"
                        >
                          [Diary {source.entry_id}] {source.title} · {source.entry_date}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="rounded-2xl border border-slate-200 bg-white px-5 py-4 text-sm text-slate-500 shadow-sm">
              ✨ Searching your diary and thinking...
            </div>
          </div>
        )}
      </div>

      {/* Error Message */}
      {error && (
        <p role="alert" className="px-6 pt-3 text-sm text-red-600">
          {error}
          {!ready && <button type="button" onClick={() => window.location.reload()} className="ml-3 underline">Reload chats</button>}
        </p>
      )}

      {/* Message Input */}
      <form
        onSubmit={sendMessage}
        className="flex gap-3 border-t border-slate-200 bg-white p-4"
      >
        <input
          type="text"
          value={question}
          maxLength={4000}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="Ask something about your diary..."
          disabled={loading || !ready}
          aria-label="Your diary question"
          className="min-w-0 flex-1 rounded-xl border border-slate-200 px-4 py-3 text-sm outline-none focus:border-indigo-500 disabled:opacity-60"
        />

        <button
          type="submit"
          disabled={loading || !ready || !question.trim()}
          className="rounded-xl bg-indigo-600 px-6 py-3 text-sm font-semibold text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? "Thinking..." : "Send ➤"}
        </button>
      </form>
    </div>
  );
}

export default AIChatbot;



