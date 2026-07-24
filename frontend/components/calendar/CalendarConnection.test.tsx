import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CalendarConnection } from "./CalendarConnection";
import { connectCalendar, disconnectCalendar, getCalendarStatus } from "@/lib/calendar";

vi.mock("@/lib/calendar", () => ({
  getCalendarStatus: vi.fn(),
  connectCalendar: vi.fn(),
  disconnectCalendar: vi.fn(),
}));

const mockedGetStatus = vi.mocked(getCalendarStatus);
const mockedConnect = vi.mocked(connectCalendar);
const mockedDisconnect = vi.mocked(disconnectCalendar);

function setUrl(search: string) {
  window.history.replaceState({}, "", `/settings${search}`);
}

describe("CalendarConnection", () => {
  afterEach(() => {
    setUrl("");
  });

  it("shows a Connect button when not connected", async () => {
    mockedGetStatus.mockResolvedValue({ connected: false });

    render(<CalendarConnection getIdToken={async () => "token"} />);

    await waitFor(() => expect(screen.getByText("Connect Google Calendar")).toBeInTheDocument());
  });

  it("shows Connected + a Disconnect button when connected", async () => {
    mockedGetStatus.mockResolvedValue({ connected: true });

    render(<CalendarConnection getIdToken={async () => "token"} />);

    await waitFor(() => expect(screen.getByText("Connected")).toBeInTheDocument());
    expect(screen.getByText("Disconnect")).toBeInTheDocument();
  });

  it("shows an error state when the status check fails", async () => {
    mockedGetStatus.mockRejectedValue(new Error("network error"));

    render(<CalendarConnection getIdToken={async () => "token"} />);

    await waitFor(() => expect(screen.getByText("Couldn't check calendar status.")).toBeInTheDocument());
  });

  it("clicking Connect fetches an authorization URL and navigates the browser there", async () => {
    mockedGetStatus.mockResolvedValue({ connected: false });
    mockedConnect.mockResolvedValue({ authorizationUrl: "https://accounts.google.com/o/oauth2/v2/auth?x=1" });
    // jsdom doesn't implement real page navigation -- assert the component
    // set window.location.href to the right value rather than that a real
    // navigation occurred (out of scope for a unit test either way).
    const hrefSpy = vi
      .spyOn(window, "location", "set")
      .mockImplementation(() => undefined);

    render(<CalendarConnection getIdToken={async () => "token"} />);
    await waitFor(() => expect(screen.getByText("Connect Google Calendar")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Connect Google Calendar"));

    await waitFor(() => expect(mockedConnect).toHaveBeenCalledTimes(1));

    hrefSpy.mockRestore();
  });

  it("clicking Disconnect calls disconnectCalendar and flips the UI back to Connect", async () => {
    mockedGetStatus.mockResolvedValue({ connected: true });
    mockedDisconnect.mockResolvedValue(undefined);

    render(<CalendarConnection getIdToken={async () => "token"} />);
    await waitFor(() => expect(screen.getByText("Disconnect")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Disconnect"));

    await waitFor(() => expect(screen.getByText("Connect Google Calendar")).toBeInTheDocument());
    expect(mockedDisconnect).toHaveBeenCalledTimes(1);
  });

  it('shows a connected notice when the URL has ?calendar=connected', async () => {
    setUrl("?calendar=connected");
    mockedGetStatus.mockResolvedValue({ connected: true });

    render(<CalendarConnection getIdToken={async () => "token"} />);

    await waitFor(() => expect(screen.getByText("Google Calendar connected.")).toBeInTheDocument());
  });

  it('shows a cancelled notice when the URL has ?calendar=cancelled', async () => {
    setUrl("?calendar=cancelled");
    mockedGetStatus.mockResolvedValue({ connected: false });

    render(<CalendarConnection getIdToken={async () => "token"} />);

    await waitFor(() => expect(screen.getByText("Calendar connection was cancelled.")).toBeInTheDocument());
  });
});
