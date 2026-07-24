import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Recommendation } from "@/lib/chat";
import { RecommendationList } from "./RecommendationList";

function makeRecommendation(overrides: Partial<Recommendation> = {}): Recommendation {
  return {
    rank: 1,
    placeId: "p1",
    name: "Test Gym",
    score: 80,
    scoreBreakdown: {},
    explanation: null,
    lat: 40.7,
    lng: -73.9,
    ...overrides,
  };
}

describe("RecommendationList", () => {
  it("renders nothing for an empty list", () => {
    const { container } = render(<RecommendationList recommendations={[]} />);

    expect(container.firstChild).toBeNull();
  });

  it("renders one card per recommendation, in order", () => {
    const recommendations = [
      makeRecommendation({ placeId: "p1", name: "First Place", rank: 1 }),
      makeRecommendation({ placeId: "p2", name: "Second Place", rank: 2 }),
    ];

    const { getAllByRole } = render(<RecommendationList recommendations={recommendations} />);

    const items = getAllByRole("listitem");
    expect(items).toHaveLength(2);
    expect(items[0].textContent).toContain("First Place");
    expect(items[1].textContent).toContain("Second Place");
  });
});
