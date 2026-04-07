import { useEffect, useMemo, useState } from "react";
import {
  cancelMeeting,
  listMeetings,
  updateMeetingRsvp,
  type Meeting,
} from "../../services/meetingsApi";
import CreateMeetingModal from "./CreateMeetingModal"; 

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

export default function MeetingList() {
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [isModalOpen, setIsModalOpen] = useState(false);

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

  async function handleCancelMeeting(meetingId: number) {
    try {
      await cancelMeeting(meetingId);
      await loadMeetings();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to cancel meeting.");
    }
  }

  async function handleRsvp(
    meetingId: number,
    status: "accepted" | "declined" | "maybe"
  ) {
    setMeetings((prev) =>
      prev.map((meeting) =>
        meeting.id === meetingId
          ? { ...meeting, current_user_status: status }
          : meeting
      )
    );
    try {
      const updated = await updateMeetingRsvp(meetingId, status);
      setMeetings((prev) =>
        prev.map((meeting) => (meeting.id === meetingId ? updated : meeting))
      );
    } catch (err) {
      await loadMeetings();
      setError(err instanceof Error ? err.message : "Failed to update RSVP.");
    }
  }

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      <div className="flex justify-between items-start md:items-center flex-col md:flex-row gap-4">
        <div>
          <h1 className="text-3xl font-bold text-slate-800 dark:text-white">Meetings</h1>
          <p className="mt-2 text-slate-500 dark:text-slate-400">
            Create team meetings, invite registered users by email, and manage RSVP status.
          </p>
        </div>
        <button
          onClick={() => setIsModalOpen(true)}
          className="rounded-lg bg-blue-600 px-5 py-3 font-medium text-white transition hover:bg-blue-500 shadow-sm shrink-0"
        >
          + Schedule Meeting
        </button>
      </div>

      {error ? <p className="text-sm text-red-500">{error}</p> : null}

      {!loading && (
        <div className="grid gap-8 lg:grid-cols-2">
          <section className="space-y-4">
            <h2 className="text-xl font-semibold dark:text-white">Upcoming</h2>
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
            <h2 className="text-xl font-semibold dark:text-white">Past</h2>
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

      {isModalOpen && (
        <CreateMeetingModal
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          onSuccess={() => { setIsModalOpen(false); loadMeetings(); }}
        />
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
  onRsvp: (meetingId: number, status: "accepted" | "declined" | "maybe") => Promise<void>;
}) {
  const isCancelled = meeting.status === "cancelled";

  return (
    <article className={`rounded-2xl border p-5 shadow-sm transition-opacity ${isCancelled ? "border-slate-200 bg-slate-50 opacity-50 dark:border-slate-800 dark:bg-slate-900/50" : "border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900"}`}>
      <div className="flex justify-between">
        <div className="flex items-center gap-3">
          <span className="inline-block h-3 w-3 rounded-full" style={{ backgroundColor: meeting.color }} />
          <h3 className="text-lg font-semibold dark:text-white">{meeting.title}</h3>
        </div>
        <span className={`text-sm font-medium ${isCancelled ? "text-red-500" : "text-slate-500 dark:text-slate-400"}`}>
          {isCancelled ? "Cancelled" : meeting.status}
        </span>
      </div>

      <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
        {formatDateTime(meeting.start_time)} — {formatDateTime(meeting.end_time)}
      </p>

      {meeting.location && (
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">📍 {meeting.location}</p>
      )}

      <p className="mt-1 text-sm dark:text-slate-300">
        Your RSVP: <span className="font-medium capitalize">{meeting.current_user_status ?? "n/a"}</span>
      </p>

      {meeting.attendees && meeting.attendees.length > 0 && (
        <div className="mt-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Attendees</p>
          <ul className="mt-1 space-y-1">
            {meeting.attendees.map((attendee) => (
              <li key={attendee.email} className="flex items-center justify-between text-sm">
                {/* FIX: Using first_name and last_name from the API instead of name */}
                <span className="text-slate-700 dark:text-slate-300">
                  {attendee.first_name ? `${attendee.first_name} ${attendee.last_name}` : attendee.email}
                </span>
                <span className={`text-xs font-medium capitalize ${attendee.status === "accepted" ? "text-green-600" : attendee.status === "declined" ? "text-red-500" : attendee.status === "maybe" ? "text-yellow-500" : "text-slate-400"}`}>
                  {attendee.status ?? "pending"}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {!isCancelled && !meeting.is_organizer && (
        <div className="mt-4 flex gap-2">
          <button onClick={() => onRsvp(meeting.id, "accepted")} className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${meeting.current_user_status === "accepted" ? "bg-green-600 text-white" : "border border-slate-200 text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"}`}>Accept</button>
          <button onClick={() => onRsvp(meeting.id, "declined")} className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${meeting.current_user_status === "declined" ? "bg-red-500 text-white" : "border border-slate-200 text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"}`}>Decline</button>
          <button onClick={() => onRsvp(meeting.id, "maybe")} className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${meeting.current_user_status === "maybe" ? "bg-yellow-400 text-white" : "border border-slate-200 text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"}`}>Maybe</button>
        </div>
      )}

      {meeting.is_organizer && !isCancelled && (
        <button onClick={() => onCancel(meeting.id)} className="mt-4 rounded-lg border border-red-200 px-3 py-1.5 text-sm font-medium text-red-600 transition-colors hover:bg-red-50 dark:border-red-900 dark:text-red-400 dark:hover:bg-red-950">
          Cancel Meeting
        </button>
      )}
    </article>
  );
}