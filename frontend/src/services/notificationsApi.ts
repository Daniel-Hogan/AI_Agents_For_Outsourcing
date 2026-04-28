import { apiJson } from "../lib/api";

export interface NotificationPreferencesState {
  email: boolean;
  inApp: boolean;
  meetingReminders: boolean;
  groupActivity: boolean;
  weeklyDigest: boolean;
  digestFrequency: "daily" | "weekly";
  quietHoursEnabled: boolean;
  quietHoursStart: string;
  quietHoursEnd: string;
}

export interface NotificationItem {
  id: number;
  meeting_id: number | null;
  channel: "email" | "in_app";
  type: "invite" | "cancel" | "update" | "rsvp_update";
  title: string;
  message: string;
  status: "pending" | "sent" | "failed" | "read" | "skipped";
  created_at: string;
  sent_at: string | null;
  read_at: string | null;
}

export interface PendingInviteItem {
  meeting_id: number;
  title: string;
  organizer_name: string;
  organizer_email: string;
  start_time: string;
  end_time: string;
  location: string | null;
  current_status: "invited" | "accepted" | "declined" | "maybe";
}

const DEFAULT_PREFERENCES: NotificationPreferencesState = {
  email: true,
  inApp: true,
  meetingReminders: true,
  groupActivity: true,
  weeklyDigest: false,
  digestFrequency: "weekly",
  quietHoursEnabled: false,
  quietHoursStart: "22:00",
  quietHoursEnd: "07:00",
};

function normalizeTime(value: string | null | undefined, fallback: string) {
  if (!value) return fallback;
  return value.slice(0, 5);
}

function fromApiPreferences(data: {
  email: boolean;
  in_app: boolean;
  meeting_reminders: boolean;
  group_activity: boolean;
  weekly_digest: boolean;
  digest_frequency: "daily" | "weekly";
  quiet_hours_enabled: boolean;
  quiet_hours_start: string | null;
  quiet_hours_end: string | null;
}): NotificationPreferencesState {
  return {
    email: data.email,
    inApp: data.in_app,
    meetingReminders: data.meeting_reminders,
    groupActivity: data.group_activity,
    weeklyDigest: data.weekly_digest,
    digestFrequency: data.digest_frequency,
    quietHoursEnabled: data.quiet_hours_enabled,
    quietHoursStart: normalizeTime(data.quiet_hours_start, DEFAULT_PREFERENCES.quietHoursStart),
    quietHoursEnd: normalizeTime(data.quiet_hours_end, DEFAULT_PREFERENCES.quietHoursEnd),
  };
}

function toApiPreferences(prefs: NotificationPreferencesState) {
  return {
    email: prefs.email,
    in_app: prefs.inApp,
    meeting_reminders: prefs.meetingReminders,
    group_activity: prefs.groupActivity,
    weekly_digest: prefs.weeklyDigest,
    digest_frequency: prefs.digestFrequency,
    quiet_hours_enabled: prefs.quietHoursEnabled,
    quiet_hours_start: prefs.quietHoursEnabled ? `${prefs.quietHoursStart}:00` : null,
    quiet_hours_end: prefs.quietHoursEnabled ? `${prefs.quietHoursEnd}:00` : null,
  };
}

export async function fetchNotificationPreferences() {
  const data = await apiJson<{
    email: boolean;
    in_app: boolean;
    meeting_reminders: boolean;
    group_activity: boolean;
    weekly_digest: boolean;
    digest_frequency: "daily" | "weekly";
    quiet_hours_enabled: boolean;
    quiet_hours_start: string | null;
    quiet_hours_end: string | null;
  }>("/notifications/preferences");
  return fromApiPreferences(data);
}

export async function saveNotificationPreferences(prefs: NotificationPreferencesState) {
  const data = await apiJson<{
    email: boolean;
    in_app: boolean;
    meeting_reminders: boolean;
    group_activity: boolean;
    weekly_digest: boolean;
    digest_frequency: "daily" | "weekly";
    quiet_hours_enabled: boolean;
    quiet_hours_start: string | null;
    quiet_hours_end: string | null;
  }>("/notifications/preferences", {
    method: "PUT",
    body: JSON.stringify(toApiPreferences(prefs)),
  });
  return fromApiPreferences(data);
}

export async function fetchNotifications(limit = 20) {
  return apiJson<NotificationItem[]>(`/notifications/?limit=${limit}`);
}

export async function markNotificationRead(notificationId: number) {
  return apiJson<NotificationItem>(`/notifications/${notificationId}/read`, {
    method: "POST",
  });
}

export async function fetchPendingInvites() {
  return apiJson<PendingInviteItem[]>("/notifications/pending-invites");
}
