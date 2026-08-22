import { afterEach, describe, expect, it, vi } from "vitest";

describe("Synth Now mobile API client", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.resetModules();
    delete process.env.EXPO_PUBLIC_API_BASE_URL;
  });

  it("requests only the configured Worker API and forwards an access token", async () => {
    process.env.EXPO_PUBLIC_API_BASE_URL = "https://api.example.test/";
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ items: [] }), { status: 200, headers: { "content-type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);
    const { synthNowApi } = await import("../lib/synth-now-api");

    await synthNowApi.listPresets("Juno", "access-token");

    expect(fetchMock).toHaveBeenCalledWith(
      "https://api.example.test/v1/presets?query=Juno",
      expect.objectContaining({ headers: expect.objectContaining({ Authorization: "Bearer access-token" }) }),
    );
  });

  it("fails closed when a mobile build has no configured Worker API", async () => {
    const { synthNowApi, SynthNowApiError } = await import("../lib/synth-now-api");

    await expect(synthNowApi.getAnalysis("job_123")).rejects.toBeInstanceOf(SynthNowApiError);
  });
});
