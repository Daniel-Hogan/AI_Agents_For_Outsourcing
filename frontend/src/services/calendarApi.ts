const API_URL = "http://127.0.0.1:8000";

function getToken() {
  return localStorage.getItem("access_token");
}

function authHeaders() {
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${getToken()}`,
  };
}

// ── Events ────────────────────────────────────────────────────────────────────

export async function fetchEvents() {
  const res = await fetch(`${API_URL}/calendar/events`, {
    headers: authHeaders(),
    credentials: "include",
  });
  if (!res.ok) throw new Error("Failed to fetch events");
  return res.json();
}

export async function createEvent(event: {
  title: string;
  start_time: string;
  end_time: string;
  location?: string;
}) {
  const res = await fetch(`${API_URL}/calendar/events`, {
    method: "POST",
    headers: authHeaders(),
    credentials: "include",
    body: JSON.stringify(event),
  });
  if (!res.ok) throw new Error("Failed to create event");
  return res.json();
}

export async function updateEvent(
  eventId: number,
  event: {
    title?: string;
    start_time?: string;
    end_time?: string;
    location?: string;
  }
) {
  const res = await fetch(`${API_URL}/calendar/events/${eventId}`, {
    method: "PUT",
    headers: authHeaders(),
    credentials: "include",
    body: JSON.stringify(event),
  });
  if (!res.ok) throw new Error("Failed to update event");
  return res.json();
}

export async function deleteEvent(eventId: number) {
  const res = await fetch(`${API_URL}/calendar/events/${eventId}`, {
    method: "DELETE",
    headers: authHeaders(),
    credentials: "include",
  });
  if (!res.ok) throw new Error("Failed to delete event");
  return res.json();
}

// ── Availability ──────────────────────────────────────────────────────────────

export async function fetchAvailability() {
  const res = await fetch(`${API_URL}/calendar/availability`, {
    headers: authHeaders(),
    credentials: "include",
  });
  if (!res.ok) throw new Error("Failed to fetch availability");
  return res.json();
}

export async function createAvailability(slot: {
  day_of_week: number;
  start_time: string;
  end_time: string;
}) {
  const res = await fetch(`${API_URL}/calendar/availability`, {
    method: "POST",
    headers: authHeaders(),
    credentials: "include",
    body: JSON.stringify(slot),
  });
  if (!res.ok) throw new Error("Failed to create availability");
  return res.json();
}

export async function deleteAvailability(slotId: number) {
  const res = await fetch(`${API_URL}/calendar/availability/${slotId}`, {
    method: "DELETE",
    headers: authHeaders(),
    credentials: "include",
  });
  if (!res.ok) throw new Error("Failed to delete availability");
  return res.json();
}