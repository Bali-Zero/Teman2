import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import CalendarPage from "../page";

// Mock lucide-react icons
vi.mock("lucide-react", () => {
  const createIcon = (name: string) => {
    const Icon = (props: Record<string, unknown>) => (
      <svg data-testid={`icon-${name}`} {...props} />
    );
    Icon.displayName = name;
    return Icon;
  };
  return {
    Calendar: createIcon("Calendar"),
    Plus: createIcon("Plus"),
    RefreshCw: createIcon("RefreshCw"),
    Clock: createIcon("Clock"),
    MapPin: createIcon("MapPin"),
    Users: createIcon("Users"),
    Video: createIcon("Video"),
    Trash2: createIcon("Trash2"),
    ChevronLeft: createIcon("ChevronLeft"),
    ChevronRight: createIcon("ChevronRight"),
    List: createIcon("List"),
    Grid3X3: createIcon("Grid3X3"),
    ExternalLink: createIcon("ExternalLink"),
    X: createIcon("X"),
  };
});

// Mock cn utility
vi.mock("@/lib/utils", () => ({
  cn: (...classes: (string | boolean | undefined)[]) =>
    classes.filter(Boolean).join(" "),
}));

const mockCalendars = {
  success: true,
  calendars: [
    { id: "cal-1", name: "Team Calendar", role: "owner" },
    { id: "cal-2", name: "Personal", role: "owner" },
  ],
};

const mockEvents = {
  success: true,
  events: [
    {
      id: "event-1",
      summary: "Team Standup",
      start: new Date(Date.now() + 3600000).toISOString(),
      end: new Date(Date.now() + 7200000).toISOString(),
      description: "Daily standup",
      location: "Office",
    },
    {
      id: "event-2",
      summary: "Client Meeting",
      start: new Date(Date.now() + 86400000).toISOString(),
      end: new Date(Date.now() + 90000000).toISOString(),
      hangoutLink: "https://meet.google.com/abc",
    },
  ],
};

describe("CalendarPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (global.fetch as ReturnType<typeof vi.fn>).mockReset();

    // Default: return calendars and events
    (global.fetch as ReturnType<typeof vi.fn>).mockImplementation(
      (url: string) => {
        if (typeof url === "string" && url.includes("/calendars")) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve(mockCalendars),
          });
        }
        if (typeof url === "string" && url.includes("/events")) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve(mockEvents),
          });
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({}),
        });
      },
    );
  });

  it("renders the calendar header", async () => {
    await act(async () => {
      render(<CalendarPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("Bali Zero Calendar")).toBeInTheDocument();
    });
  });

  it("renders weekday headers in Italian", async () => {
    await act(async () => {
      render(<CalendarPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("Lun")).toBeInTheDocument();
      expect(screen.getByText("Mar")).toBeInTheDocument();
      expect(screen.getByText("Mer")).toBeInTheDocument();
      expect(screen.getByText("Gio")).toBeInTheDocument();
      expect(screen.getByText("Ven")).toBeInTheDocument();
      expect(screen.getByText("Sab")).toBeInTheDocument();
      expect(screen.getByText("Dom")).toBeInTheDocument();
    });
  });

  it("renders view toggle buttons", async () => {
    await act(async () => {
      render(<CalendarPage />);
    });

    await waitFor(() => {
      expect(screen.getByLabelText("Vista mese")).toBeInTheDocument();
      expect(screen.getByLabelText("Vista lista")).toBeInTheDocument();
    });
  });

  it("renders Nuovo button for creating events", async () => {
    await act(async () => {
      render(<CalendarPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("Nuovo")).toBeInTheDocument();
    });
  });

  it("renders refresh button", async () => {
    await act(async () => {
      render(<CalendarPage />);
    });

    await waitFor(() => {
      expect(screen.getByLabelText("Aggiorna eventi")).toBeInTheDocument();
    });
  });

  it("renders month navigation buttons", async () => {
    await act(async () => {
      render(<CalendarPage />);
    });

    await waitFor(() => {
      expect(screen.getByLabelText("Mese precedente")).toBeInTheDocument();
      expect(screen.getByLabelText("Mese successivo")).toBeInTheDocument();
    });
  });

  it("renders 'Oggi' button", async () => {
    await act(async () => {
      render(<CalendarPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("Oggi")).toBeInTheDocument();
    });
  });

  it("shows event count", async () => {
    await act(async () => {
      render(<CalendarPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("2 eventi")).toBeInTheDocument();
    });
  });

  it("renders calendar selector", async () => {
    await act(async () => {
      render(<CalendarPage />);
    });

    await waitFor(() => {
      expect(screen.getByLabelText("Seleziona calendario")).toBeInTheDocument();
    });
  });

  it("opens create form when Nuovo is clicked", async () => {
    await act(async () => {
      render(<CalendarPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("Nuovo")).toBeInTheDocument();
    });

    await act(async () => {
      fireEvent.click(screen.getByText("Nuovo"));
    });

    expect(screen.getByText("Nuovo Evento")).toBeInTheDocument();
    expect(screen.getByText("Titolo")).toBeInTheDocument();
    expect(screen.getByText("Inizio")).toBeInTheDocument();
    expect(screen.getByText("Fine")).toBeInTheDocument();
  });

  it("switches to list view", async () => {
    await act(async () => {
      render(<CalendarPage />);
    });

    await waitFor(() => {
      expect(screen.getByLabelText("Vista lista")).toBeInTheDocument();
    });

    await act(async () => {
      fireEvent.click(screen.getByLabelText("Vista lista"));
    });

    // In list view, events appear in the list AND in the sidebar
    // so we use getAllByText to handle duplicates
    await waitFor(() => {
      expect(screen.getAllByText("Team Standup").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("Client Meeting").length).toBeGreaterThanOrEqual(1);
    });
  });

  it("shows error banner on fetch failure", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockImplementation(
      (url: string) => {
        if (typeof url === "string" && url.includes("/calendars")) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve(mockCalendars),
          });
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ success: false, error: "API Error" }),
        });
      },
    );

    await act(async () => {
      render(<CalendarPage />);
    });

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("API Error");
    });
  });

  it("shows upcoming events in sidebar", async () => {
    await act(async () => {
      render(<CalendarPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("Prossimi Eventi")).toBeInTheDocument();
    });
  });
});
