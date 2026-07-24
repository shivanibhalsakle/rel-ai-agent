import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Recommendation } from "@/lib/chat";
import { WeatherTimeline } from "./WeatherTimeline";

function makeHour(overrides: Partial<Recommendation> = {}): Recommendation {
  return {
    rank: 1,
    placeId: "2026-07-24T14:00:00Z",
    name: "02:00 PM UTC",
    score: 80,
    scoreBreakdown: { temperature: 1, daylight: 1 },
    explanation: "Pleasant and dry.",
    lat: null,
    lng: null,
    polyline: null,
    startTime: "2026-07-24T14:00:00Z",
    ...overrides,
  };
}

describe("WeatherTimeline", () => {
  it("renders nothing for an empty list", () => {
    const { container } = render(<WeatherTimeline recommendations={[]} />);

    expect(container.firstChild).toBeNull();
  });

  it("renders nothing when no recommendation has a startTime", () => {
    // Defends the same gap RecommendationMap's plottable/routable filters
    // defend against: stale localStorage history from before M6.7 added
    // startTime, or a fitness/workspace result that has none at all.
    const { container } = render(
      <WeatherTimeline recommendations={[makeHour({ startTime: null })]} />
    );

    expect(container.firstChild).toBeNull();
  });

  it("sorts chronologically by startTime, not by rank", () => {
    // rank 1 (best score) is the LATER hour here -- the timeline must
    // still show it second, since it's a time-ordered view, not a
    // ranked list re-skinned.
    const recommendations = [
      makeHour({ rank: 1, startTime: "2026-07-24T14:00:00Z", name: "02:00 PM UTC" }),
      makeHour({ rank: 2, startTime: "2026-07-24T06:00:00Z", name: "06:00 AM UTC" }),
    ];

    render(<WeatherTimeline recommendations={recommendations} />);

    const labels = screen.getAllByText(/UTC/).map((el) => el.textContent);
    expect(labels).toEqual(["06:00 AM UTC", "02:00 PM UTC"]);
  });

  it("shows the score and explanation for each hour", () => {
    render(<WeatherTimeline recommendations={[makeHour({ score: 92, explanation: "Clear and mild." })]} />);

    expect(screen.getByText("92/100")).toBeInTheDocument();
    expect(screen.getByText("Clear and mild.")).toBeInTheDocument();
  });

  it("omits the explanation paragraph when null", () => {
    const { container } = render(<WeatherTimeline recommendations={[makeHour({ explanation: null })]} />);

    expect(container.querySelectorAll("p")).toHaveLength(0);
  });
});
