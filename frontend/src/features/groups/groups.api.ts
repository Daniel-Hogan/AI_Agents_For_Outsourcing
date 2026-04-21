const API_URL = "http://127.0.0.1:8000";

function getToken() {
  return localStorage.getItem("access_token") || "";
}

function authHeaders() {
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${getToken()}`,
  };
}

async function parseError(response: Response, fallback: string) {
  try {
    const data = await response.json();
    if (typeof data?.detail === "string") return data.detail;
  } catch {
    // Fall back to a generic message when backend doesn't return JSON.
  }
  return fallback;
}

export interface CreateGroupPayload {
  name: string;
  description?: string;
}

export interface JoinGroupPayload {
  inviteCode?: string;
  groupId?: number;
}

export async function getGroups() {
  const res = await fetch(`${API_URL}/groups/`, {
    headers: authHeaders(),
  });

  if (!res.ok) {
    throw new Error(await parseError(res, "Failed to fetch groups"));
  }

  return res.json();
}

export async function createGroup(payload: CreateGroupPayload) {
  const res = await fetch(`${API_URL}/groups/`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    throw new Error(await parseError(res, "Failed to create group"));
  }

  return res.json();
}

export async function joinGroup(payload: JoinGroupPayload) {
  const res = await fetch(`${API_URL}/groups/join`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    throw new Error(await parseError(res, "Failed to join group"));
  }

  return res.json();
}
