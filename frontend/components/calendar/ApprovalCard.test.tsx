import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ProposedEvent } from "@/lib/chat";
import { ApprovalCard } from "./ApprovalCard";

function makeProposedEvent(overrides: Partial<ProposedEvent> = {}): ProposedEvent {
  return {
    title: "Time outside",
    start: "2026-07-25T17:00:00+00:00",
    end: "2026-07-25T18:00:00+00:00",
    location: "Prospect Park, Brooklyn, NY",
    ...overrides,
  };
}

describe("ApprovalCard", () => {
  it("renders the event title and location", () => {
    render(<ApprovalCard proposedEvent={makeProposedEvent()} onDecide={vi.fn()} />);

    expect(screen.getByText("Time outside")).toBeInTheDocument();
    expect(screen.getByText("Prospect Park, Brooklyn, NY")).toBeInTheDocument();
  });

  it("omits the location line when null", () => {
    render(<ApprovalCard proposedEvent={makeProposedEvent({ location: null })} onDecide={vi.fn()} />);

    expect(screen.queryByText("Prospect Park, Brooklyn, NY")).not.toBeInTheDocument();
  });

  it("clicking Confirm calls onDecide(true)", async () => {
    const onDecide = vi.fn().mockResolvedValue(undefined);
    render(<ApprovalCard proposedEvent={makeProposedEvent()} onDecide={onDecide} />);

    fireEvent.click(screen.getByText("Confirm"));

    await waitFor(() => expect(screen.getByText("Done — see the reply below.")).toBeInTheDocument());
    expect(onDecide).toHaveBeenCalledWith(true);
  });

  it("clicking No thanks calls onDecide(false)", async () => {
    const onDecide = vi.fn().mockResolvedValue(undefined);
    render(<ApprovalCard proposedEvent={makeProposedEvent()} onDecide={onDecide} />);

    fireEvent.click(screen.getByText("No thanks"));

    await waitFor(() => expect(screen.getByText("Done — see the reply below.")).toBeInTheDocument());
    expect(onDecide).toHaveBeenCalledWith(false);
  });

  it("shows a retry option when the decision call fails", async () => {
    const onDecide = vi.fn().mockRejectedValue(new Error("network error"));
    render(<ApprovalCard proposedEvent={makeProposedEvent()} onDecide={onDecide} />);

    fireEvent.click(screen.getByText("Confirm"));

    await waitFor(() => expect(screen.getByText("Something went wrong.")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Try again"));
    expect(screen.getByText("Confirm")).toBeInTheDocument();
  });
});
