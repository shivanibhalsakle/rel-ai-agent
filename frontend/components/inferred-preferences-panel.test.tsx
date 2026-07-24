import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { InferredPreferencesPanel } from "./inferred-preferences-panel";
import { apiFetch } from "@/lib/api-client";

vi.mock("@/lib/api-client", () => ({
  apiFetch: vi.fn(),
}));

const mockedApiFetch = vi.mocked(apiFetch);

function jsonResponse(body: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

describe("InferredPreferencesPanel", () => {
  it("shows an empty-state message when nothing has been adjusted yet", async () => {
    mockedApiFetch.mockResolvedValue(jsonResponse({ importanceDelta: {}, reasons: [] }));

    render(<InferredPreferencesPanel getIdToken={async () => "token"} />);

    await waitFor(() => expect(screen.getByText(/Nothing adjusted yet/)).toBeInTheDocument());
  });

  it("shows each adjusted factor and its reason", async () => {
    mockedApiFetch.mockResolvedValue(
      jsonResponse({
        importanceDelta: { affordability: 1 },
        reasons: ["You've rejected 3 recent options that scored low on affordability — weighting it more heavily."],
      })
    );

    render(<InferredPreferencesPanel getIdToken={async () => "token"} />);

    await waitFor(() => expect(screen.getByText("Affordability +1")).toBeInTheDocument());
    expect(screen.getByText(/You've rejected 3 recent options/)).toBeInTheDocument();
  });

  it("shows an error message when the request fails", async () => {
    mockedApiFetch.mockResolvedValue(jsonResponse({}, 500));

    render(<InferredPreferencesPanel getIdToken={async () => "token"} />);

    await waitFor(() => expect(screen.getByText(/Couldn't load this/)).toBeInTheDocument());
  });
});
