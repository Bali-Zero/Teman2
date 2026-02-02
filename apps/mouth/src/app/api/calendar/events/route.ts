import { NextRequest, NextResponse } from 'next/server';
import { listEvents, createEvent, deleteEvent, TEAM_CALENDAR_ID } from '@/lib/google-calendar';

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const calendarId = searchParams.get('calendarId') || TEAM_CALENDAR_ID;
    const days = parseInt(searchParams.get('days') || '30', 10);
    const max = parseInt(searchParams.get('max') || '50', 10);

    const events = await listEvents(calendarId, days, max);

    return NextResponse.json({
      success: true,
      events,
      calendarId,
    });
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : 'Failed to fetch events';

    if (message.includes('No events')) {
      return NextResponse.json({ success: true, events: [], calendarId: TEAM_CALENDAR_ID });
    }

    return NextResponse.json({ success: false, error: message }, { status: 500 });
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { summary, from, to, description, location, attendees, withMeet, calendarId } = body;

    if (!summary || !from || !to) {
      return NextResponse.json(
        { success: false, error: 'summary, from, and to are required' },
        { status: 400 }
      );
    }

    const event = await createEvent({
      summary,
      from,
      to,
      description,
      location,
      attendees,
      withMeet,
      calendarId,
    });

    return NextResponse.json({ success: true, event });
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : 'Failed to create event';
    return NextResponse.json({ success: false, error: message }, { status: 500 });
  }
}

export async function DELETE(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const eventId = searchParams.get('eventId');
    const calendarId = searchParams.get('calendarId') || TEAM_CALENDAR_ID;

    if (!eventId) {
      return NextResponse.json({ success: false, error: 'eventId is required' }, { status: 400 });
    }

    await deleteEvent(eventId, calendarId);

    return NextResponse.json({ success: true });
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : 'Failed to delete event';
    return NextResponse.json({ success: false, error: message }, { status: 500 });
  }
}
