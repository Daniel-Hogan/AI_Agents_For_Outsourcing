import { apiJson } from "../lib/api";

export interface CalendarApiEvent {
  id: number;
  title: string;
  location?: string | null;
  color?: string | null;
  start_time: string;
  end_time: string;
  current_user_status?: "invited" | "accepted" | "declined" | "maybe" | null;
}

export interface CalendarAvailabilitySlot {
  id: number;
  day_of_week: number;
  start_time: string;
  end_time: string;
}

// ── Events ────────────────────────────────────────────────────────────────────

export async function fetchEvents() {
  return apiJson<CalendarApiEvent[]>("/calendar/events");
}

export async function createEvent(event: {
  title: string;
  start_time: string;
  end_time: string;
  location?: string;
  color?: string;
}) {
  return apiJson<CalendarApiEvent>("/calendar/events", {
    method: "POST",
    body: JSON.stringify(event),
  });
}

export async function updateEvent(
  eventId: number,
  event: {
    title?: string;
    start_time?: string;
    end_time?: string;
    location?: string;
    color?: string;
  }
) {
  return apiJson<CalendarApiEvent>(`/calendar/events/${eventId}`, {
    method: "PUT",
    body: JSON.stringify(event),
  });
}

export async function deleteEvent(eventId: number) {
  return apiJson<{ message: string }>(`/calendar/events/${eventId}`, {
    method: "DELETE",
  });
}

// ── Availability ──────────────────────────────────────────────────────────────

export async function fetchAvailability() {
  return apiJson<CalendarAvailabilitySlot[]>("/calendar/availability");
}

export async function createAvailability(slot: {
  day_of_week: number;
  start_time: string;
  end_time: string;
}) {
  return apiJson<CalendarAvailabilitySlot>("/calendar/availability", {
    method: "POST",
    body: JSON.stringify(slot),
  });
}

export async function deleteAvailability(slotId: number) {
  return apiJson<{ message: string }>(`/calendar/availability/${slotId}`, {
    method: "DELETE",
  });
}
