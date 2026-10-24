import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AIChatbot from "../src/components/AIChatbot";
import { apiFetch } from "../src/api";
vi.mock("../src/api", () => ({ apiFetch: vi.fn() }));
afterEach(cleanup);
const response = (data: unknown) => ({ ok: true, json: async () => data }) as Response;
beforeEach(() => {
  vi.mocked(apiFetch).mockImplementation(async (url, options) => {
    if (url.endsWith("/api/conversations") && options?.method === "POST") return response({ id: 3, title: "New chat" });
    if (url.endsWith("/api/conversations")) return response({ conversations: [{ id: 1, title: "First chat" }, { id: 2, title: "Second chat" }] });
    if (options?.method === "POST") return response({ conversation: { id: 3, title: "A new question" }, messages: [
      { id: 5, role: "user", content: "A new question" },
      { id: 6, role: "assistant", content: "A supported observation. [Diary 12]", sources: [{ entry_id: 12, title: "Synthetic source", entry_date: "2026-10-01", excerpt: "Supporting synthetic passage" }] },
    ] });
    const id = url.includes("/1/") ? 1 : 2;
    return response({ messages: [{ id, role: "user", content: id === 1 ? "First saved message" : "Second saved message" }] });
  });
});
describe("Saved conversations", () => {
  it("restores chats and keeps selected conversation messages separate", async () => {
    const user = userEvent.setup();
    render(<AIChatbot />);
    await screen.findByText("First saved message");
    await user.selectOptions(screen.getByLabelText("Saved conversations"), "2");
    await screen.findByText("Second saved message");
    expect(screen.queryByText("First saved message")).toBeNull();
  });
  it("starts a new conversation and renders saved answer citations", async () => {
    const user = userEvent.setup();
    render(<AIChatbot />);
    await screen.findByText("First saved message");
    await user.click(screen.getByRole("button", { name: "New Chat" }));
    expect(screen.queryByText("First saved message")).toBeNull();
    await user.type(screen.getByLabelText("Your diary question"), "A new question");
    await user.click(screen.getByRole("button", { name: /Send/ }));
    await screen.findByText("A supported observation. [Diary 12]");
    expect(screen.getByTitle("Supporting synthetic passage").textContent).toContain("Synthetic source");
    expect(vi.mocked(apiFetch).mock.calls.some(([url, options]) => url.endsWith("/3/messages") && options?.method === "POST")).toBe(true);
  });
});
