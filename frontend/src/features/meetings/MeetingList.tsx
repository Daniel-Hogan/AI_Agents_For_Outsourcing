import { useEffect, useMemo, useState } from "react";
import { cancelMeeting, listMeetings, updateMeetingRsvp, type Meeting } from "../../services/meetingsApi";
import CreateMeetingModal from "./CreateMeetingModal";

function formatDateTime(value: string) {
  return new Date(value).toLocaleString([], {
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
    const upcoming = meetings.filter((meeting) => new Date(meeting.end_time) >= new Date());
    const past = meetings.filter((meeting) => new Date(meeting.end_time) < new Date());
    return { upcoming, past };
  }, [meetings]);

  async function handleCancelMeeting(meetingId: number) {
    try {
      const updated = await cancelMeeting(meetingId);
      setMeetings((prev) => prev.map((meeting) => (meeting.id === meetingId ? updated : meeting)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to cancel meeting.");
    }
  }

  async function handleRsvp(meetingId: number, status: "accepted" | "declined") {
    try {
      const updated = await updateMeetingRsvp(meetingId, status);
      setMeetings((prev) => prev.map((meeting) => (meeting.id === meetingId ? updated : meeting)));
    } catch (err) {
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

      {loading ? <div className="rounded-xl bg-white p-6 text-slate-500 shadow-sm dark:bg-slate-900 dark:text-slate-400">Loading meetings...</div> : null}

      {!loading ? (
        <div className="grid gap-8 lg:grid-cols-2">
          <section className="space-y-4">
            <h2 className="text-xl font-semibold text-slate-800 dark:text-white">Upcoming</h2>
            {groupedMeetings.upcoming.length === 0 ? (
              <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-6 text-slate-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400">
                No upcoming meetings yet.
              </div>
            ) : (
              groupedMeetings.upcoming.map((meeting) => (
                <MeetingCard
                  key={meeting.id}
                  meeting={meeting}
                  onCancel={handleCancelMeeting}
                  onRsvp={handleRsvp}
                />
              ))
            )}
          </section>

          <section className="space-y-4">
            <h2 className="text-xl font-semibold text-slate-800 dark:text-white">Past</h2>
            {groupedMeetings.past.length === 0 ? (
              <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-6 text-slate-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400">
                Past meetings will show up here after you start scheduling.
              </div>
            ) : (
              groupedMeetings.past.map((meeting) => (
                <MeetingCard
                  key={meeting.id}
                  meeting={meeting}
                  onCancel={handleCancelMeeting}
                  onRsvp={handleRsvp}
                />
              ))
            )}
          </section>
        </div>
      ) : null}

      
      <CreateMeetingModal 
        isOpen={isModalOpen} 
        onClose={() => setIsModalOpen(false)} 
        onSuccess={loadMeetings} 
      />
    </div>
  );
}

function MeetingCard({ meeting, onCancel, onRsvp }: { meeting: Meeting; onCancel: (meetingId: number) => Promise<void>; onRsvp: (meetingId: number, status: "accepted" | "declined") => Promise<void>; }) {
  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <span className="inline-block h-3 w-3 rounded-full" style={{ backgroundColor: meeting.color }} />
            <h3 className="text-lg font-semibold text-slate-900 dark:text-white">{meeting.title}</h3>
          </div>
          <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">{formatDateTime(meeting.start_time)} - {formatDateTime(meeting.end_time)}</p>
          {meeting.location ? <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{meeting.location}</p> : null}
        </div>

        <span className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wide ${meeting.status === "cancelled" ? "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300" : "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300"}`}>
          {meeting.status}
        </span>
      </div>

      {meeting.description ? <p className="mt-4 text-sm text-slate-600 dark:text-slate-300">{meeting.description}</p> : null}

      <div className="mt-4 flex flex-wrap gap-2 text-xs text-slate-500 dark:text-slate-400">
        <span>{meeting.accepted_count} accepted</span>
        <span>{meeting.invited_count} invited</span>
        <span>{meeting.declined_count} declined</span>
        <span>{meeting.is_organizer ? "Organizer" : `Your RSVP: ${meeting.current_user_status ?? "n/a"}`}</span>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        {meeting.attendees.map((attendee) => (
          <span key={attendee.user_id} className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600 dark:bg-slate-800 dark:text-slate-300">
            {attendee.first_name} {attendee.last_name} - {attendee.status}
          </span>
        ))}
      </div>

      {meeting.status !== "cancelled" ? (
        <div className="mt-5 flex flex-wrap gap-3">
          {meeting.is_organizer ? (
            <button type="button" onClick={() => void onCancel(meeting.id)} className="rounded-lg border border-red-200 px-4 py-2 text-sm font-medium text-red-600 transition hover:bg-red-50 dark:border-red-800 dark:text-red-300 dark:hover:bg-red-950/30">
              Cancel Meeting
            </button>
          ) : (
            <>
              <button type="button" onClick={() => void onRsvp(meeting.id, "accepted")} className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-emerald-500">Accept</button>
              <button type="button" onClick={() => void onRsvp(meeting.id, "declined")} className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800">Decline</button>
            </>
          )}
        </div>
      ) : null}
    </article>
  );
}