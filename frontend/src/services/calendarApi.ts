const API_URL = "http://127.0.0.1:8000";

function getToken() {
  return localStorage.getItem("access_token");
}

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function parseErrorMessage(res: Response, fallback: string) {
  try {
    const data = await res.json();
    if (typeof data?.detail === "string") return data.detail;
  } catch {
    // Ignore parse errors and use fallback message.
  }
  return fallback;
}

async function refreshAccessToken() {
  const res = await fetch(`${API_URL}/auth/refresh`, {
    method: "POST",
    credentials: "include",
  });

  if (!res.ok) return null;

  const data = await res.json();
  const token = typeof data?.access_token === "string" ? data.access_token : null;
  if (token) {
    localStorage.setItem("access_token", token);
  }
  return token;
}

async function requestWithAuth(path: string, init: RequestInit = {}, retryOn401 = true) {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init.headers as Record<string, string> | undefined),
  };

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers,
    credentials: "include",
  });

  if (res.status === 401 && retryOn401) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      return requestWithAuth(path, init, false);
    }
    localStorage.removeItem("access_token");
  }

  return res;
}

// ── Events ────────────────────────────────────────────────────────────────────

export async function fetchEvents() {
  const res = await requestWithAuth("/calendar/events");
  if (!res.ok) {
    throw new ApiError(await parseErrorMessage(res, "Failed to fetch events"), res.status);
  }
  return res.json();
}

export async function createEvent(event: {
  title: string;
  start_time: string;
  end_time: string;
  location?: string;
  color?: string;
}) {
  const res = await requestWithAuth("/calendar/events", {
    method: "POST",
    body: JSON.stringify(event),
  });
  if (!res.ok) {
    throw new ApiError(await parseErrorMessage(res, "Failed to create event"), res.status);
  }
  return res.json();
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
  const res = await requestWithAuth(`/calendar/events/${eventId}`, {
    method: "PUT",
    body: JSON.stringify(event),
  });
  if (!res.ok) {
    throw new ApiError(await parseErrorMessage(res, "Failed to update event"), res.status);
  }
  return res.json();
}

export async function deleteEvent(eventId: number) {
  const res = await requestWithAuth(`/calendar/events/${eventId}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    throw new ApiError(await parseErrorMessage(res, "Failed to delete event"), res.status);
  }
  return res.json();
}

// ── Availability ──────────────────────────────────────────────────────────────

export async function fetchAvailability() {
  const res = await requestWithAuth("/calendar/availability");
  if (!res.ok) {
    throw new ApiError(await parseErrorMessage(res, "Failed to fetch availability"), res.status);
  }
  return res.json();
}

export async function createAvailability(slot: {
  day_of_week: number;
  start_time: string;
  end_time: string;
}) {
  const res = await requestWithAuth("/calendar/availability", {
    method: "POST",
    body: JSON.stringify(slot),
  });
  if (!res.ok) {
    throw new ApiError(await parseErrorMessage(res, "Failed to create availability"), res.status);
  }
  return res.json();
}

export async function deleteAvailability(slotId: number) {
  const res = await requestWithAuth(`/calendar/availability/${slotId}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    throw new ApiError(await parseErrorMessage(res, "Failed to delete availability"), res.status);
  }
  return res.json();
}