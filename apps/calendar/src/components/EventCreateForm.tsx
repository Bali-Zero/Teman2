'use client';

import React from 'react';
import { X, RefreshCw, Video } from 'lucide-react';

export interface NewEventData {
  summary: string;
  from: string;
  to: string;
  description: string;
  location: string;
  attendees: string;
  withMeet: boolean;
}

interface EventCreateFormProps {
  value: NewEventData;
  onChange: (data: NewEventData) => void;
  onSubmit: (e: React.FormEvent) => void;
  onCancel: () => void;
  creating: boolean;
}

const inputCls =
  'w-full bg-[#242424] border border-white/10 rounded-lg px-3 py-2 text-sm text-[#E6E7EB] focus:ring-2 focus:ring-[#d4845a] focus:outline-none';

const labelCls = 'block text-sm font-medium text-[#9AA0AE] mb-1.5';

export function EventCreateForm({
  value,
  onChange,
  onSubmit,
  onCancel,
  creating,
}: EventCreateFormProps) {
  const set = (field: keyof NewEventData) => (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) =>
    onChange({
      ...value,
      [field]: e.target.type === 'checkbox' ? (e.target as HTMLInputElement).checked : e.target.value,
    });

  return (
    <div className="flex-1 overflow-auto p-6">
      <div className="flex items-center justify-between mb-6">
        <h3 className="font-semibold text-[#E6E7EB]">Nuovo Evento</h3>
        <button
          type="button"
          onClick={onCancel}
          className="text-[#9AA0AE] hover:text-[#E6E7EB] transition-colors p-1"
          aria-label="Chiudi modulo creazione evento"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      <form onSubmit={onSubmit} className="space-y-4">
        {/* Title */}
        <div>
          <label htmlFor="event-title" className={labelCls}>
            Titolo <span className="text-[#d4845a]">*</span>
          </label>
          <input
            id="event-title"
            type="text"
            required
            value={value.summary}
            onChange={set('summary')}
            className={inputCls}
            placeholder="Aggiungi titolo"
          />
        </div>

        {/* Start / End */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label htmlFor="event-start" className={labelCls}>
              Inizio <span className="text-[#d4845a]">*</span>
            </label>
            <input
              id="event-start"
              type="datetime-local"
              required
              value={value.from}
              onChange={set('from')}
              className={inputCls}
            />
          </div>
          <div>
            <label htmlFor="event-end" className={labelCls}>
              Fine <span className="text-[#d4845a]">*</span>
            </label>
            <input
              id="event-end"
              type="datetime-local"
              required
              value={value.to}
              onChange={set('to')}
              className={inputCls}
            />
          </div>
        </div>

        {/* Location */}
        <div>
          <label htmlFor="event-location" className={labelCls}>
            Luogo
          </label>
          <input
            id="event-location"
            type="text"
            value={value.location}
            onChange={set('location')}
            className={inputCls}
            placeholder="Aggiungi luogo"
          />
        </div>

        {/* Description */}
        <div>
          <label htmlFor="event-description" className={labelCls}>
            Descrizione
          </label>
          <textarea
            id="event-description"
            value={value.description}
            onChange={set('description')}
            className={inputCls + ' resize-none'}
            rows={3}
            placeholder="Aggiungi descrizione"
          />
        </div>

        {/* Attendees */}
        <div>
          <label htmlFor="event-attendees" className={labelCls}>
            Partecipanti
          </label>
          <input
            id="event-attendees"
            type="text"
            value={value.attendees}
            onChange={set('attendees')}
            className={inputCls}
            placeholder="email1@example.com, email2@example.com"
            aria-describedby="event-attendees-hint"
          />
          <p id="event-attendees-hint" className="mt-1 text-xs text-[#9AA0AE]">
            Separare gli indirizzi con virgola
          </p>
        </div>

        {/* Google Meet */}
        <label className="flex items-center gap-2 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={value.withMeet}
            onChange={(e) => onChange({ ...value, withMeet: e.target.checked })}
            className="w-4 h-4 rounded bg-[#242424] border-white/10 accent-[#d4845a]"
            aria-label="Aggiungi Google Meet"
          />
          <Video className="h-4 w-4 text-[#34D399]" aria-hidden="true" />
          <span className="text-sm text-[#9AA0AE]">Aggiungi Google Meet</span>
        </label>

        {/* Actions */}
        <div className="flex gap-2 pt-4">
          <button
            type="button"
            onClick={onCancel}
            className="flex-1 px-4 py-2 rounded-lg border border-white/10 text-[#9AA0AE] hover:bg-white/5 transition-colors text-sm"
          >
            Annulla
          </button>
          <button
            type="submit"
            disabled={creating}
            className="flex-1 px-4 py-2 rounded-lg bg-[#d4845a] text-white hover:bg-[#bf7350] disabled:opacity-50 disabled:cursor-not-allowed inline-flex items-center justify-center gap-2 text-sm font-medium transition-colors"
          >
            {creating && <RefreshCw className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />}
            {creating ? 'Salvataggio...' : 'Salva evento'}
          </button>
        </div>
      </form>
    </div>
  );
}
