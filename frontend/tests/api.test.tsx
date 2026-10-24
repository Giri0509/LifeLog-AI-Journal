import { afterEach, describe, expect, it, vi } from "vitest";
import { apiFetch, responseError } from "../src/api";
afterEach(() => vi.unstubAllGlobals());
describe("API requests", () => {
  it("sends cookies and signals session expiry without retrying", async () => {
    const fetcher = vi.fn().mockResolvedValue({ status: 401 });
    vi.stubGlobal("fetch", fetcher);
    const expired = vi.fn();
    window.addEventListener("lifelog-session-expired", expired);
    try {
      await apiFetch("http://localhost:8000/api/diary", { method: "POST" });
      expect(fetcher).toHaveBeenCalledTimes(1);
      expect(fetcher.mock.calls[0][1].credentials).toBe("include");
      expect(expired).toHaveBeenCalledTimes(1);
    } finally { window.removeEventListener("lifelog-session-expired", expired); }
  });
  it("turns connection failures into a useful message and does not retry a mutation", async () => {
    const fetcher = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    vi.stubGlobal("fetch", fetcher);
    await expect(apiFetch("http://localhost:8000/api/diary", { method: "POST" })).rejects.toThrow("Unable to reach the server");
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
  it("warns that a timed-out write may already have been saved", async () => {
    const error = new Error("timeout");
    error.name = "TimeoutError";
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(error));
    await expect(apiFetch("http://localhost:8000/api/diary", { method: "POST" })).rejects.toThrow("Check whether your changes were saved");
  });
  it("presents server validation messages without relying on raw input values", async () => {
    const error = await responseError({ json: async () => ({ detail: [{ msg: "This field cannot be blank." }] }) } as Response, "Fallback");
    expect(error.message).toBe("This field cannot be blank.");
  });
});
