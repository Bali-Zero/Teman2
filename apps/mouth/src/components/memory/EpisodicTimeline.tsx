/**
 * Episodic Timeline Component
 * Visualizes user events over time with filters
 */

'use client';

import { useState, useEffect } from 'react';
import { Calendar, Filter, TrendingUp, AlertCircle, CheckCircle, Clock } from 'lucide-react';
import type { EpisodicEvent, EpisodicEventType, EpisodicEmotion } from '@/lib/api/zantara-sdk/types';
import { Select } from '@/components/ui/select';

export interface EpisodicTimelineProps {
  events: EpisodicEvent[];
  onEventClick?: (event: EpisodicEvent) => void;
  showFilters?: boolean;
}

const eventTypeIcons: Record<EpisodicEventType, typeof Calendar> = {
  milestone: CheckCircle,
  problem: AlertCircle,
  resolution: CheckCircle,
  decision: TrendingUp,
  meeting: Calendar,
  deadline: Clock,
  discovery: TrendingUp,
  general: Calendar,
};

const eventTypeColors: Record<EpisodicEventType, string> = {
  milestone: 'text-green-600',
  problem: 'text-red-600',
  resolution: 'text-blue-600',
  decision: 'text-purple-600',
  meeting: 'text-orange-600',
  deadline: 'text-yellow-600',
  discovery: 'text-indigo-600',
  general: 'text-gray-600',
};

export function EpisodicTimeline({
  events,
  onEventClick,
  showFilters = true,
}: EpisodicTimelineProps) {
  const [filteredEvents, setFilteredEvents] = useState<EpisodicEvent[]>(events);
  const [eventTypeFilter, setEventTypeFilter] = useState<EpisodicEventType | 'all'>('all');
  const [emotionFilter, setEmotionFilter] = useState<EpisodicEmotion | 'all'>('all');

  useEffect(() => {
    let filtered = events;

    if (eventTypeFilter !== 'all') {
      filtered = filtered.filter((e) => e.event_type === eventTypeFilter);
    }

    if (emotionFilter !== 'all') {
      filtered = filtered.filter((e) => e.emotion === emotionFilter);
    }

    setFilteredEvents(filtered);
  }, [events, eventTypeFilter, emotionFilter]);

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <Calendar className="h-5 w-5" />
          Event Timeline
        </h3>
        <span className="text-sm text-muted-foreground">
          {filteredEvents.length} event{filteredEvents.length !== 1 ? 's' : ''}
        </span>
      </div>

      {showFilters && (
        <div className="flex gap-2 flex-wrap">
          <select
            value={eventTypeFilter}
            onChange={(e) => setEventTypeFilter(e.target.value as EpisodicEventType | 'all')}
            className="px-3 py-1 text-sm border rounded-md bg-background"
          >
            <option value="all">All Types</option>
            <option value="milestone">Milestones</option>
            <option value="problem">Problems</option>
            <option value="resolution">Resolutions</option>
            <option value="decision">Decisions</option>
            <option value="meeting">Meetings</option>
            <option value="deadline">Deadlines</option>
            <option value="discovery">Discoveries</option>
          </select>

          <select
            value={emotionFilter}
            onChange={(e) => setEmotionFilter(e.target.value as EpisodicEmotion | 'all')}
            className="px-3 py-1 text-sm border rounded-md bg-background"
          >
            <option value="all">All Emotions</option>
            <option value="positive">Positive</option>
            <option value="negative">Negative</option>
            <option value="neutral">Neutral</option>
            <option value="urgent">Urgent</option>
            <option value="frustrated">Frustrated</option>
            <option value="excited">Excited</option>
            <option value="worried">Worried</option>
          </select>
        </div>
      )}

      <div className="space-y-3">
        {filteredEvents.length === 0 ? (
          <p className="text-sm text-muted-foreground italic text-center py-8">
            No events found
          </p>
        ) : (
          filteredEvents.map((event) => {
            const Icon = eventTypeIcons[event.event_type];
            const colorClass = eventTypeColors[event.event_type];

            return (
              <div
                key={event.id}
                onClick={() => onEventClick?.(event)}
                className={`p-4 border rounded-lg hover:bg-muted transition-colors cursor-pointer ${
                  onEventClick ? '' : 'cursor-default'
                }`}
              >
                <div className="flex items-start gap-3">
                  <Icon className={`h-5 w-5 mt-0.5 ${colorClass}`} />
                  <div className="flex-1 space-y-1">
                    <div className="flex items-center justify-between">
                      <h4 className="font-medium">{event.title}</h4>
                      <span className="text-xs text-muted-foreground">
                        {formatDate(event.occurred_at)}
                      </span>
                    </div>
                    {event.description && (
                      <p className="text-sm text-muted-foreground">{event.description}</p>
                    )}
                    <div className="flex items-center gap-2 text-xs">
                      <span className="px-2 py-0.5 bg-muted rounded">
                        {event.event_type}
                      </span>
                      {event.emotion !== 'neutral' && (
                        <span className="px-2 py-0.5 bg-muted rounded">
                          {event.emotion}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}







