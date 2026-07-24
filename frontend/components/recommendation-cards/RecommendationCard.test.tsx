import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Recommendation } from "@/lib/chat";
import { RecommendationCard } from "./RecommendationCard";

function makeRecommendation(overrides: Partial<Recommendation> = {}): Recommendation {
  return {
    rank: 1,
    placeId: "p1",
    name: "Test Gym",
    score: 80,
    scoreBreakdown: { rating: 0.9, review_count: 0.5 },
    explanation: "Great rating and plenty of reviews.",
    lat: 40.7,
    lng: -73.9,
    polyline: null,
    startTime: null,
    ...overrides,
  };
}

describe("RecommendationCard", () => {
  it("renders the name and explanation", () => {
    render(<RecommendationCard recommendation={makeRecommendation()} />);

    expect(screen.getByText("Test Gym")).toBeInTheDocument();
    expect(screen.getByText("Great rating and plenty of reviews.")).toBeInTheDocument();
  });

  it("shows the rank and score somewhere in the card", () => {
    const { container } = render(
      <RecommendationCard recommendation={makeRecommendation({ rank: 3, score: 80 })} />
    );

    expect(container.textContent).toContain("3");
    expect(container.textContent).toContain("80/100");
  });

  it("omits the explanation paragraph when null", () => {
    const { container } = render(
      <RecommendationCard recommendation={makeRecommendation({ explanation: null })} />
    );

    expect(container.querySelectorAll("p")).toHaveLength(0);
  });

  it("humanizes factor names into one bar per factor", () => {
    render(
      <RecommendationCard
        recommendation={makeRecommendation({ scoreBreakdown: { rating: 1, review_count: 0.5 } })}
      />
    );

    expect(screen.getByText("Rating")).toBeInTheDocument();
    expect(screen.getByText("Review Count")).toBeInTheDocument();
  });

  it("sizes each factor bar to its score as a percentage width", () => {
    const { container } = render(
      <RecommendationCard recommendation={makeRecommendation({ scoreBreakdown: { rating: 0.75 } })} />
    );

    const bar = container.querySelector("div[style]") as HTMLElement;
    expect(bar.style.width).toBe("75%");
  });

  it("renders no factor bars when scoreBreakdown is empty", () => {
    const { container } = render(
      <RecommendationCard recommendation={makeRecommendation({ scoreBreakdown: {} })} />
    );

    expect(container.querySelectorAll("div[style]")).toHaveLength(0);
  });

  it.each([
    [90, "bg-emerald-100"],
    [60, "bg-amber-100"],
    [30, "bg-red-100"],
  ])("uses the right score-pill tone for a score of %i", (score: number, expectedClass: string) => {
    const { container } = render(<RecommendationCard recommendation={makeRecommendation({ score })} />);

    const pill = container.querySelector(`.${expectedClass}`);
    expect(pill).not.toBeNull();
    expect(pill?.textContent).toBe(`${score}/100`);
  });

  // ---- Milestone 7: accept/reject feedback ----

  it("renders no feedback UI when onFeedback is not provided", () => {
    render(<RecommendationCard recommendation={makeRecommendation()} />);

    expect(screen.queryByText("👍 Helpful")).not.toBeInTheDocument();
    expect(screen.queryByText("👎 Not helpful")).not.toBeInTheDocument();
  });

  it("clicking Helpful submits an accepted action with no reason", async () => {
    const onFeedback = vi.fn().mockResolvedValue(undefined);
    render(<RecommendationCard recommendation={makeRecommendation()} onFeedback={onFeedback} />);

    fireEvent.click(screen.getByText("👍 Helpful"));

    await waitFor(() => expect(screen.getByText("Thanks — saved.")).toBeInTheDocument());
    expect(onFeedback).toHaveBeenCalledWith("accepted", undefined);
  });

  it("clicking Not helpful reveals a reason field, and Submit sends the typed reason", async () => {
    const onFeedback = vi.fn().mockResolvedValue(undefined);
    render(<RecommendationCard recommendation={makeRecommendation()} onFeedback={onFeedback} />);

    fireEvent.click(screen.getByText("👎 Not helpful"));
    const input = screen.getByPlaceholderText("What wasn't a fit? (optional)");
    fireEvent.change(input, { target: { value: "too far from home" } });
    fireEvent.click(screen.getByText("Submit"));

    await waitFor(() => expect(screen.getByText("Thanks — saved.")).toBeInTheDocument());
    expect(onFeedback).toHaveBeenCalledWith("rejected", "too far from home");
  });

  it("submitting a rejection with a blank reason omits it rather than sending an empty string", async () => {
    const onFeedback = vi.fn().mockResolvedValue(undefined);
    render(<RecommendationCard recommendation={makeRecommendation()} onFeedback={onFeedback} />);

    fireEvent.click(screen.getByText("👎 Not helpful"));
    fireEvent.click(screen.getByText("Submit"));

    await waitFor(() => expect(onFeedback).toHaveBeenCalled());
    expect(onFeedback).toHaveBeenCalledWith("rejected", undefined);
  });

  it("Cancel returns to the idle buttons without calling onFeedback", () => {
    const onFeedback = vi.fn();
    render(<RecommendationCard recommendation={makeRecommendation()} onFeedback={onFeedback} />);

    fireEvent.click(screen.getByText("👎 Not helpful"));
    fireEvent.click(screen.getByText("Cancel"));

    expect(screen.getByText("👍 Helpful")).toBeInTheDocument();
    expect(onFeedback).not.toHaveBeenCalled();
  });

  it("shows a retry option when the feedback call fails", async () => {
    const onFeedback = vi.fn().mockRejectedValue(new Error("network error"));
    render(<RecommendationCard recommendation={makeRecommendation()} onFeedback={onFeedback} />);

    fireEvent.click(screen.getByText("👍 Helpful"));

    await waitFor(() => expect(screen.getByText("Couldn't save that.")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Try again"));
    expect(screen.getByText("👍 Helpful")).toBeInTheDocument();
  });
});
