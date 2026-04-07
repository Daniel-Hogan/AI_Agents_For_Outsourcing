import { type FormEvent, useEffect, useMemo, useState } from "react";
import {
  cancelMeeting,
  createMeeting,
  listMeetings,
  updateMeetingRsvp,
  type Meeting,
} from "../../services/meetingsApi";

function toDateTimeString(date: string, time: string) {
  return `${date}T${time}:00`;
}

function formatDateTime(value: string) {
  return new Date(value).toLocaleString([], {
    timeZone: "UTC",
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

const DEFAULT_COLOR = "#2563eb";

export default function MeetingList() {
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [location, setLocation] = useState("");
  const [date, setDate] = useState("");
  const [startTime, setStartTime] = useState("09:00");
  const [endTime, setEndTime] = useState("10:00");
  const [attendeeEmails, setAttendeeEmails] = useState("");

  async function loadMeetings() {
    setLoading(true);
    setError("");
    try {
      const data = await listMeetings();
      setMeetings(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load meetings.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const now = new Date();
    setDate(
      `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(
        now.getDate()
      ).padStart(2, "0")}`
    );
    loadMeetings();
  }, []);

  const groupedMeetings = useMemo(() => {
    const upcoming = meetings.filter(
      (meeting) => new Date(meeting.end_time) >= new Date()
    );
    const past = meetings.filter(
      (meeting) => new Date(meeting.end_time) < new Date()
    );
    return { upcoming, past };
  }, [meetings]);

  async function handleCreateMeeting(event: FormEvent) {
    event.preventDefault();

    if (!title.trim() || !date) {
      setError("Please provide a title and date.");
      return;
    }

    if (endTime <= startTime) {
      setError("Meeting end time must be after the start time.");
      return;
    }

    setSaving(true);
    setError("");

    try {
      const created = await createMeeting({
        title: title.trim(),
        description: description.trim() || undefined,
        location: location.trim() || undefined,
        color: DEFAULT_COLOR,
        start_time: toDateTimeString(date, startTime),
        end_time: toDateTimeString(date, endTime),
        attendee_emails: attendeeEmails
          .split(",")
          .map((email) => email.trim())
          .filter(Boolean),
      });

      setMeetings((prev) =>
        [...prev, created].sort((a, b) =>
          a.start_time.localeCompare(b.start_time)
        )
      );

      setTitle("");
      setDescription("");
      setLocation("");
      setAttendeeEmails("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create meeting.");
    } finally {
      setSaving(false);
    }
  }

  async function handleCancelMeeting(meetingId: number) {
    try {
      await cancelMeeting(meetingId);
      // Refetch so calendar sync and all derived state are fresh
      await loadMeetings();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to cancel meeting.");
    }
  }

  async function handleRsvp(
    meetingId: number,
    status: "accepted" | "declined" | "maybe"
  ) {
    // Optimistic update — no full reload needed
    setMeetings((prev) =>
      prev.map((meeting) =>
        meeting.id === meetingId
          ? { ...meeting, current_user_status: status }
          : meeting
      )
    );

    try {
      const updated = await updateMeetingRsvp(meetingId, status);
      // Reconcile with server response
      setMeetings((prev) =>
        prev.map((meeting) => (meeting.id === meetingId ? updated : meeting))
      );
    } catch (err) {
      // Roll back optimistic update on failure
      await loadMeetings();
      setError(err instanceof Error ? err.message : "Failed to update RSVP.");
    }
  }

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-slate-800 dark:text-white">
          Meetings
        </h1>
        <p className="mt-2 text-slate-500 dark:text-slate-400">
          Create team meetings, invite registered users by email, and manage RSVP status.
        </p>
      </div>

      {/* ORIGINAL FORM (UNCHANGED) */}
      <form
        onSubmit={handleCreateMeeting}
        className="grid gap-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900"
      >
        <div className="grid gap-4 md:grid-cols-2">
          <input
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="Meeting title"
            className="rounded-lg border border-slate-200 px-4 py-3 text-slate-900 outline-none focus:border-blue-500 dark:border-slate-700 dark:bg-slate-950 dark:text-white"
          />
          <input
            value={location}
            onChange={(event) => setLocation(event.target.value)}
            placeholder="Location or meeting link"
            className="rounded-lg border border-slate-200 px-4 py-3 text-slate-900 outline-none focus:border-blue-500 dark:border-slate-700 dark:bg-slate-950 dark:text-white"
          />
        </div>

        <textarea
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          placeholder="Description"
          rows={3}
          className="rounded-lg border border-slate-200 px-4 py-3 text-slate-900 outline-none focus:border-blue-500 dark:border-slate-700 dark:bg-slate-950 dark:text-white"
        />

        <div className="grid gap-4 md:grid-cols-3">
          <input
            type="date"
            value={date}
            onChange={(event) => setDate(event.target.value)}
            className="rounded-lg border border-slate-200 px-4 py-3"
          />
          <input
            type="time"
            value={startTime}
            onChange={(event) => setStartTime(event.target.value)}
            className="rounded-lg border border-slate-200 px-4 py-3"
          />
          <input
            type="time"
            value={endTime}
            onChange={(event) => setEndTime(event.target.value)}
            className="rounded-lg border border-slate-200 px-4 py-3"
          />
        </div>

        <input
          value={attendeeEmails}
          onChange={(event) => setAttendeeEmails(event.target.value)}
          placeholder="Invite attendee emails, comma-separated"
          className="rounded-lg border border-slate-200 px-4 py-3"
        />

        {error ? <p className="text-sm text-red-500">{error}</p> : null}

        <div className="flex justify-end">
          <button
            type="submit"
            disabled={saving}
            className="rounded-lg bg-blue-600 px-5 py-3 font-medium text-white"
          >
            {saving ? "Creating..." : "Create Meeting"}
          </button>
        </div>
      </form>

      {!loading && (
        <div className="grid gap-8 lg:grid-cols-2">
          <section className="space-y-4">
            <h2 className="text-xl font-semibold">Upcoming</h2>
            {groupedMeetings.upcoming.map((meeting) => (
              <MeetingCard
                key={meeting.id}
                meeting={meeting}
                onCancel={handleCancelMeeting}
                onRsvp={handleRsvp}
              />
            ))}
          </section>

          <section className="space-y-4">
            <h2 className="text-xl font-semibold">Past</h2>
            {groupedMeetings.past.map((meeting) => (
              <MeetingCard
                key={meeting.id}
                meeting={meeting}
                onCancel={handleCancelMeeting}
                onRsvp={handleRsvp}
              />
            ))}
          </section>
        </div>
      )}
    </div>
  );
}

function MeetingCard({
  meeting,
  onCancel,
  onRsvp,
}: {
  meeting: Meeting;
  onCancel: (meetingId: number) => Promise<void>;
  onRsvp: (
    meetingId: number,
    status: "accepted" | "declined" | "maybe"
  ) => Promise<void>;
}) {
  const isCancelled = meeting.status === "cancelled";

  return (
    <article
      className={`rounded-2xl border p-5 shadow-sm transition-opacity ${
        isCancelled
          ? "border-slate-200 bg-slate-50 opacity-50 dark:border-slate-800 dark:bg-slate-900/50"
          : "border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900"
      }`}
    >
      <div className="flex justify-between">
        <h3 className="text-lg font-semibold">{meeting.title}</h3>
        <span
          className={`text-sm font-medium ${
            isCancelled
              ? "text-red-500"
              : "text-slate-500 dark:text-slate-400"
          }`}
        >
          {isCancelled ? "Cancelled" : meeting.status}
        </span>
      </div>

      <p className="text-sm text-slate-500 dark:text-slate-400">
        {formatDateTime(meeting.start_time)}
      </p>

      {meeting.location && (
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          📍 {meeting.location}
        </p>
      )}

      <p className="mt-1 text-sm">
        Your RSVP:{" "}
        <span className="font-medium capitalize">
          {meeting.current_user_status ?? "n/a"}
        </span>
      </p>

      {/* Attendees + their RSVP status */}
      {meeting.attendees && meeting.attendees.length > 0 && (
        <div className="mt-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            Attendees
          </p>
          <ul className="mt-1 space-y-1">
            {meeting.attendees.map((attendee) => (
              <li
                key={attendee.email}
                className="flex items-center justify-between text-sm"
              >
                <span className="text-slate-700 dark:text-slate-300">
                  {attendee.name ?? attendee.email}
                </span>
                <span
                  className={`text-xs font-medium capitalize ${
                    attendee.status === "accepted"
                      ? "text-green-600"
                      : attendee.status === "declined"
                      ? "text-red-500"
                      : attendee.status === "maybe"
                      ? "text-yellow-500"
                      : "text-slate-400"
                  }`}
                >
                  {attendee.status ?? "pending"}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* RSVP actions — hidden when cancelled */}
      {!isCancelled && !meeting.is_organizer && (
        <div className="mt-4 flex gap-2">
          <button
            onClick={() => onRsvp(meeting.id, "accepted")}
            className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
              meeting.current_user_status === "accepted"
                ? "bg-green-600 text-white"
                : "border border-slate-200 text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
            }`}
          >
            Accept
          </button>
          <button
            onClick={() => onRsvp(meeting.id, "declined")}
            className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
              meeting.current_user_status === "declined"
                ? "bg-red-500 text-white"
                : "border border-slate-200 text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
            }`}
          >
            Decline
          </button>
          <button
            onClick={() => onRsvp(meeting.id, "maybe")}
            className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
              meeting.current_user_status === "maybe"
                ? "bg-yellow-400 text-white"
                : "border border-slate-200 text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
            }`}
          >
            Maybe
          </button>
        </div>
      )}

      {/* Cancel — organizer only, not already cancelled */}
      {meeting.is_organizer && !isCancelled && (
        <button
          onClick={() => onCancel(meeting.id)}
          className="mt-4 rounded-lg border border-red-200 px-3 py-1.5 text-sm font-medium text-red-600 transition-colors hover:bg-red-50 dark:border-red-900 dark:text-red-400 dark:hover:bg-red-950"
        >
          Cancel Meeting
        </button>
      )}
    </article>
  );
}