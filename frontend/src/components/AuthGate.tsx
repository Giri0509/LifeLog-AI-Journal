import { useEffect, useState, type FormEvent } from "react";
import App from "../App";
import { apiFetch } from "../api";

interface User { id: number; username: string }
const authUrl = "http://localhost:8000/api/auth";

export default function AuthGate() {
  const [user, setUser] = useState<User | null>(null);
  const [initializing, setInitializing] = useState(true);
  const [busy, setBusy] = useState(false);
  const [register, setRegister] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    const expired = () => { setUser(null); setPassword(""); setConfirmPassword(""); setError("Please sign in again. Your session may have expired."); };
    window.addEventListener("lifelog-session-expired", expired);
    void (async () => {
      try {
        const response = await apiFetch(`${authUrl}/me`, { signal: controller.signal });
        if (response.ok) {
          const data = await response.json();
          if (!controller.signal.aborted) setUser(data.user);
        } else if (response.status !== 401) {
          throw new Error("Unable to check your session. Check that the backend is running.");
        }
      } catch (err) {
        if (!controller.signal.aborted) setError(err instanceof Error ? err.message : "Unable to connect.");
      } finally {
        if (!controller.signal.aborted) setInitializing(false);
      }
    })();
    return () => { controller.abort(); window.removeEventListener("lifelog-session-expired", expired); };
  }, []);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (busy) return;
    if (register && password !== confirmPassword) { setError("Passwords do not match."); return; }
    setBusy(true);
    setError("");
    try {
      const response = await apiFetch(`${authUrl}/${register ? "register" : "login"}`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: username.trim(), password }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Check your username and password format.");
      setUser(data.user);
      setPassword("");
      setConfirmPassword("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to sign in.");
    } finally { setBusy(false); }
  };

  const logout = async () => {
    setBusy(true);
    setError("");
    try {
      const response = await apiFetch(`${authUrl}/logout`, { method: "POST" });
      if (!response.ok) throw new Error("Unable to sign out. Please try again.");
      setUser(null);
      setRegister(false);
      setPassword("");
      setConfirmPassword("");
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to sign out."); }
    finally { setBusy(false); }
  };

  if (initializing) return <p role="status" className="p-10 text-center text-slate-500">Checking your session...</p>;
  if (user) return <>
    <div className="flex flex-wrap items-center justify-end gap-4 bg-white px-6 py-3 text-sm md:ml-64">
      <span className="text-slate-600">Signed in as {user.username}</span>
      <button type="button" onClick={logout} disabled={busy} className="font-semibold text-indigo-700 disabled:opacity-50">{busy ? "Signing out..." : "Sign out"}</button>
      {error && <p role="alert" className="text-red-600">{error}</p>}
    </div>
    <App key={user.id} />
  </>;
  return <main className="flex min-h-screen items-center justify-center bg-slate-50 p-5">
    <section className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
      <p className="text-sm font-semibold text-indigo-600">LIFELOG AI</p>
      <h1 className="mt-3 text-3xl font-bold text-slate-800">{register ? "Create your account" : "Welcome back"}</h1>
      <p className="mt-2 text-sm text-slate-500">Sign in to access your private diary and conversations.</p>
      <form onSubmit={submit} className="mt-6 space-y-4">
        <label className="block text-sm font-medium text-slate-600">Username
          <input required minLength={3} maxLength={80} pattern="[A-Za-z0-9_.\-]+" autoComplete="username" value={username} disabled={busy} onChange={(event) => setUsername(event.target.value)} className="mt-2 w-full rounded-xl border border-slate-200 p-3" />
        </label>
        <p className="text-xs text-slate-500">3–80 letters, numbers, dots, underscores, or hyphens. Usernames are case-insensitive.</p>
        <label className="block text-sm font-medium text-slate-600">Password
          <input required type="password" minLength={10} maxLength={128} autoComplete={register ? "new-password" : "current-password"} value={password} disabled={busy} onChange={(event) => setPassword(event.target.value)} className="mt-2 w-full rounded-xl border border-slate-200 p-3" />
        </label>
        {register && <>
          <p className="text-xs text-slate-500">Use 10–128 characters.</p>
          <label className="block text-sm font-medium text-slate-600">Confirm password
            <input required type="password" minLength={10} maxLength={128} autoComplete="new-password" value={confirmPassword} disabled={busy} onChange={(event) => setConfirmPassword(event.target.value)} className="mt-2 w-full rounded-xl border border-slate-200 p-3" />
          </label>
          <p className="rounded-xl bg-indigo-50 p-3 text-sm text-indigo-700">The first account on this installation receives the existing diary entries and chats. Later accounts start empty.</p>
        </>}
        {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
        <button disabled={busy} type="submit" className="w-full rounded-xl bg-indigo-600 px-5 py-3 font-semibold text-white disabled:opacity-50">{busy ? "Please wait..." : register ? "Create account" : "Sign in"}</button>
      </form>
      <button type="button" disabled={busy} onClick={() => { setRegister(!register); setError(""); setPassword(""); setConfirmPassword(""); }} className="mt-5 text-sm font-medium text-indigo-700">{register ? "Already have an account? Sign in" : "New here? Create an account"}</button>
    </section>
  </main>;
}
