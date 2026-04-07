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
  invited_count: number;
  attendees: MeetingAttendee[];
}

export interface CreateMeetingPayload {
  title: string;
  description?: string;
  location?: string;
  color?: string;
  start_time: string;
  end_time: string;
  capacity?: number;
  setup_minutes?: number;
  cleanup_minutes?: number;
  attendee_emails?: string[];
}

export async function listMeetings(includeCancelled = false) {
  return apiJson<Meeting[]>(`/meetings/?include_cancelled=${includeCancelled}`);
}

export async function createMeeting(payload: CreateMeetingPayload) {
  return apiJson<Meeting>("/meetings/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function cancelMeeting(meetingId: number) {
  return apiJson<Meeting>(`/meetings/${meetingId}/cancel`, {
    method: "POST",
  });
}

export async function updateMeetingRsvp(
  meetingId: number,
  status: "accepted" | "declined" | "maybe"
) {
  return apiJson<Meeting>(`/meetings/${meetingId}/rsvp`, {
    method: "POST",
    body: JSON.stringify({ status }),
  });
}