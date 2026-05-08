import { apiJson } from "../lib/api";

export interface MeetingAttendee {
  user_id: number;
  email: string;
  first_name: string;
  last_name: string;
  status: "invited" | "accepted" | "declined" | "maybe";
}

export interface Meeting {
  id: number;
  calendar_id: number;
  title: string;
  description: string | null;
  location: string | null;
  meeting_type: "in_person" | "virtual";
  color: string;
  start_time: string;
  end_time: string;
  capacity: number | null;
  setup_minutes: number;
  cleanup_minutes: number;
  status: "proposed" | "confirmed" | "cancelled";
  created_by: number | null;
  created_at: string;
  is_organizer: boolean;
  current_user_status: "invited" | "accepted" | "declined" | "maybe" | null;
  attendee_count: number;
  accepted_count: number;
  declined_count: number;
  maybe_count: number;
  invited_count: number;
  attendees: MeetingAttendee[];
}

export interface MeetingRecommendation {
  rank: number;
  start_time: string;
  end_time: string;
  available_attendee_count: number;
  conflicted_attendee_count: number;
  score: number;
  reason: string;
}

export interface MeetingRecommendationsResponse {
  attendees: Array<{
    user_id: number;
    email: string;
    first_name: string;
    last_name: string;
  }>;
  duration_minutes: number;
  recommendations: MeetingRecommendation[];
}

export interface CreateMeetingPayload {
  title: string;
  description?: string;
  location?: string;
  meeting_type?: "in_person" | "virtual";
  color?: string;
  start_time: string;
  end_time: string;
  capacity?: number;
  setup_minutes?: number;
  cleanup_minutes?: number;
  attendee_emails?: string[];
}

export interface MeetingRecommendationsPayload {
  attendee_emails?: string[];
  start_date: string;
  end_date: string;
  duration_minutes: number;
  max_results?: number;
  include_organizer?: boolean;
}

export async function listMeetings(includeCancelled = false) {
  return apiJson<Meeting[]>(`/api/meetings/?include_cancelled=${includeCancelled}`);
}

export async function createMeeting(payload: CreateMeetingPayload) {
  return apiJson<Meeting>("/api/meetings/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function fetchMeetingRecommendations(payload: MeetingRecommendationsPayload) {
  return apiJson<MeetingRecommendationsResponse>("/api/meetings/recommendations", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function cancelMeeting(meetingId: number) {
  return apiJson<Meeting>(`/api/meetings/${meetingId}/cancel`, {
    method: "POST",
  });
}

export async function updateMeetingRsvp(
  meetingId: number,
  status: "accepted" | "declined" | "maybe"
) {
  return apiJson<Meeting>(`/api/meetings/${meetingId}/rsvp`, {
    method: "POST",
    body: JSON.stringify({ status }),
  });
}

export async function getMeetingAvailability(meetingId: number) {
  return apiJson(`/api/meetings/${meetingId}/availability`);
}

export async function fetchRescheduleSuggestions(
  meetingId: number,
  payload: MeetingRecommendationsPayload
) {
  return apiJson<MeetingRecommendationsResponse>(
    `/api/meetings/${meetingId}/reschedule-suggestions`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
}

export async function updateMeeting(
  meetingId: number,
  payload: Partial<CreateMeetingPayload>
) {
  return apiJson<Meeting>(`/api/meetings/${meetingId}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}
