import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import DiaryEntries from "../src/components/DiaryEntries";
import { apiFetch } from "../src/api";
vi.mock("../src/api", () => ({ apiFetch: vi.fn(), responseError: vi.fn() }));
const entries = [
  { id: 1, title: "Park walk", content: "Relaxed beside the lake", entry_date: "2026-10-01", mood: "Happy", mood_score: 8 },
  { id: 2, title: "Work deadline", content: "Finished the report", entry_date: "2026-10-02", mood: "Anxious", mood_score: 3 },
  { id: 3, title: "Quiet Sunday", content: "Reading at home", entry_date: "2026-10-03", mood: null, mood_score: null },
];
afterEach(cleanup);
beforeEach(() => vi.mocked(apiFetch).mockResolvedValue({ ok: true, json: async () => ({ entries }) } as Response));

describe("Diary search and filters", () => {
  it("combines content search, mood and inclusive dates, then clears filters", async () => {
    const user = userEvent.setup();
    render(<DiaryEntries />);
    await screen.findByText("Park walk");
    await user.type(screen.getByLabelText("Search title or content"), "LAKE");
    await user.selectOptions(screen.getByLabelText("Mood"), "mood:happy");
    fireEvent.change(screen.getByLabelText("From date"), { target: { value: "2026-10-01" } });
    fireEvent.change(screen.getByLabelText("To date"), { target: { value: "2026-10-01" } });
    expect(screen.getByText("1 of 3 entries")).toBeTruthy();
    expect(screen.queryByText("Work deadline")).toBeNull();
    await user.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(screen.getByText("3 of 3 entries")).toBeTruthy();
  });
  it("sorts finite scores before missing scores and filters unanalyzed entries", async () => {
    const user = userEvent.setup();
    render(<DiaryEntries />);
    await screen.findByText("Park walk");
    await user.selectOptions(screen.getByLabelText("Sort by"), "mood_asc");
    expect(screen.getAllByRole("heading", { level: 3 }).map((node) => node.textContent)).toEqual(["Work deadline", "Park walk", "Quiet Sunday"]);
    await user.selectOptions(screen.getByLabelText("Mood"), "unanalyzed");
    expect(screen.getByText("1 of 3 entries")).toBeTruthy();
    expect(screen.getByText("Quiet Sunday")).toBeTruthy();
  });
  it("distinguishes invalid date ranges from no matching entries", async () => {
    render(<DiaryEntries />);
    await screen.findByText("Park walk");
    fireEvent.change(screen.getByLabelText("From date"), { target: { value: "2026-10-03" } });
    fireEvent.change(screen.getByLabelText("To date"), { target: { value: "2026-10-01" } });
    expect(screen.getByRole("alert").textContent).toContain("From date must be on or before");
    expect(screen.queryByText("No entries match your filters.")).toBeNull();
    fireEvent.change(screen.getByLabelText("From date"), { target: { value: "2026-09-01" } });
    fireEvent.change(screen.getByLabelText("To date"), { target: { value: "2026-09-30" } });
    expect(screen.getByText("No entries match your filters.")).toBeTruthy();
  });
  it("shows a safe loading failure instead of rendering diary cards", async () => {
    vi.mocked(apiFetch).mockResolvedValue({ ok: false } as Response);
    render(<DiaryEntries />);
    await waitFor(() => expect(screen.getByText("Unable to load diary entries.")).toBeTruthy());
    expect(screen.queryByText("Park walk")).toBeNull();
  });
});
