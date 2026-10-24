import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AuthGate from "../src/components/AuthGate";
import { apiFetch } from "../src/api";
vi.mock("../src/api", () => ({ apiFetch: vi.fn() }));
vi.mock("../src/App", () => ({ default: () => <p>Private diary view</p> }));
afterEach(cleanup);
const response = (status: number, data: unknown) => ({ ok: status >= 200 && status < 300, status, json: async () => data }) as Response;

describe("Account screen", () => {
  it("keeps private content hidden until sign-in succeeds, then signs out", async () => {
    vi.mocked(apiFetch).mockResolvedValueOnce(response(401, {})).mockResolvedValueOnce(response(200, { user: { id: 1, username: "owner" } })).mockResolvedValueOnce(response(200, {}));
    const user = userEvent.setup();
    render(<AuthGate />);
    await screen.findByRole("heading", { name: "Welcome back" });
    expect(screen.queryByText("Private diary view")).toBeNull();
    await user.type(screen.getByLabelText("Username"), "owner");
    await user.type(screen.getByLabelText("Password"), "synthetic-password");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    await screen.findByText("Private diary view");
    expect(vi.mocked(apiFetch).mock.calls[1][1]?.body).toBe(JSON.stringify({ username: "owner", password: "synthetic-password" }));
    await user.click(screen.getByRole("button", { name: "Sign out" }));
    await screen.findByRole("heading", { name: "Welcome back" });
    expect(screen.queryByText("Private diary view")).toBeNull();
  });
  it("checks password confirmation before registering", async () => {
    vi.mocked(apiFetch).mockResolvedValue(response(401, {}));
    const user = userEvent.setup();
    render(<AuthGate />);
    await screen.findByRole("heading", { name: "Welcome back" });
    await user.click(screen.getByRole("button", { name: "New here? Create an account" }));
    await user.type(screen.getByLabelText("Username"), "owner");
    await user.type(screen.getByLabelText("Password", { exact: true }), "synthetic-password");
    await user.type(screen.getByLabelText("Confirm password"), "different-password");
    await user.click(screen.getByRole("button", { name: "Create account", exact: true }));
    expect(screen.getByRole("alert").textContent).toContain("Passwords do not match");
    expect(vi.mocked(apiFetch)).toHaveBeenCalledTimes(1);
  });
  it("removes the private view on session expiry", async () => {
    vi.mocked(apiFetch).mockResolvedValue(response(200, { user: { id: 1, username: "owner" } }));
    render(<AuthGate />);
    await screen.findByText("Private diary view");
    window.dispatchEvent(new Event("lifelog-session-expired"));
    await waitFor(() => expect(screen.queryByText("Private diary view")).toBeNull());
    expect(screen.getByRole("alert").textContent).toContain("sign in again");
  });
});
