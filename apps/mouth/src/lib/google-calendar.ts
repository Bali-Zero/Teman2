import { google, calendar_v3 } from "googleapis";

// Service account credentials from environment variables
const GOOGLE_SERVICE_ACCOUNT_EMAIL = process.env.GOOGLE_SERVICE_ACCOUNT_EMAIL;
const GOOGLE_PRIVATE_KEY = process.env.GOOGLE_PRIVATE_KEY?.replace(
  /\\n/g,
  "\n",
);

// Default team calendar
export const TEAM_CALENDAR_ID =
  process.env.GOOGLE_CALENDAR_ID ||
  "ec0863e7c14ac6bf414ec23e2aab81960ecb26823c6a8f397c664fc64901d617@group.calendar.google.com";

function getAuthClient() {
  if (!GOOGLE_SERVICE_ACCOUNT_EMAIL || !GOOGLE_PRIVATE_KEY) {
    throw new Error("Google service account credentials not configured");
  }

  return new google.auth.JWT({
    email: GOOGLE_SERVICE_ACCOUNT_EMAIL,
    key: GOOGLE_PRIVATE_KEY,
    scopes: ["https://www.googleapis.com/auth/calendar"],
  });
}

function getCalendarClient(): calendar_v3.Calendar {
  const auth = getAuthClient();
  return google.calendar({ version: "v3", auth });
}

export interface CalendarEvent {
  id: string;
  summary: string;
  start: string | null | undefined;
  end: string | null | undefined;
  description?: string | null;
  location?: string | null;
  hangoutLink?: string | null;
  attendees?: string[];
}

export interface CalendarInfo {
  id: string;
  name: string;
  role: string;
}

export async function listCalendars(): Promise<CalendarInfo[]> {
  const calendar = getCalendarClient();
  const response = await calendar.calendarList.list();

  return (response.data.items || []).map((cal) => ({
    id: cal.id || "",
    name: cal.summary || "",
    role: cal.accessRole || "",
  }));
}

export async function listEvents(
  calendarId: string = TEAM_CALENDAR_ID,
  days: number = 30,
  maxResults: number = 50,
): Promise<CalendarEvent[]> {
  const calendar = getCalendarClient();

  const timeMin = new Date().toISOString();
  const timeMax = new Date(
    Date.now() + days * 24 * 60 * 60 * 1000,
  ).toISOString();

  const response = await calendar.events.list({
    calendarId,
    timeMin,
    timeMax,
    maxResults,
    singleEvents: true,
    orderBy: "startTime",
  });

  return (response.data.items || []).map((evt) => ({
    id: evt.id || "",
    summary: evt.summary || "",
    start: evt.start?.dateTime || evt.start?.date,
    end: evt.end?.dateTime || evt.end?.date,
    description: evt.description,
    location: evt.location,
    hangoutLink: evt.hangoutLink,
    attendees: evt.attendees?.map((a) => a.email || ""),
  }));
}

export interface CreateEventParams {
  summary: string;
  from: string;
  to: string;
  description?: string;
  location?: string;
  attendees?: string;
  withMeet?: boolean;
  calendarId?: string;
}

export async function createEvent(
  params: CreateEventParams,
): Promise<CalendarEvent> {
  const calendar = getCalendarClient();
  const calendarId = params.calendarId || TEAM_CALENDAR_ID;

  const eventBody: calendar_v3.Schema$Event = {
    summary: params.summary,
    start: {
      dateTime: params.from,
      timeZone: "Asia/Makassar",
    },
    end: {
      dateTime: params.to,
      timeZone: "Asia/Makassar",
    },
  };

  if (params.description) {
    eventBody.description = params.description;
  }

  if (params.location) {
    eventBody.location = params.location;
  }

  if (params.attendees) {
    eventBody.attendees = params.attendees.split(",").map((email) => ({
      email: email.trim(),
    }));
  }

  if (params.withMeet) {
    eventBody.conferenceData = {
      createRequest: {
        requestId: `meet-${Date.now()}`,
        conferenceSolutionKey: { type: "hangoutsMeet" },
      },
    };
  }

  const response = await calendar.events.insert({
    calendarId,
    requestBody: eventBody,
    conferenceDataVersion: params.withMeet ? 1 : 0,
  });

  const evt = response.data;
  return {
    id: evt.id || "",
    summary: evt.summary || "",
    start: evt.start?.dateTime || evt.start?.date,
    end: evt.end?.dateTime || evt.end?.date,
    description: evt.description,
    location: evt.location,
    hangoutLink: evt.hangoutLink,
    attendees: evt.attendees?.map((a) => a.email || ""),
  };
}

export async function deleteEvent(
  eventId: string,
  calendarId: string = TEAM_CALENDAR_ID,
): Promise<void> {
  const calendar = getCalendarClient();
  await calendar.events.delete({
    calendarId,
    eventId,
  });
}
