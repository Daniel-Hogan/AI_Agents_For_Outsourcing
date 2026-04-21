import { useEffect, useMemo, useState } from "react";
import {
  listMeetings,
  updateMeetingRsvp,
  type Meeting,
} from "../../services/meetingsApi";
import CreateMeetingModal from "./CreateMeetingModal";
import RescheduleMeetingModal from "./RescheduleMeetingModal";
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

function AvailabilityBar({ attendees }: { attendees: { status: string }[] }) {
  return (
    <div className="flex gap-1 mt-2">
      {attendees.map((a, i) => {
        const color =
          a.status === "accepted"
            ? "bg-green-500"
            : a.status === "declined"
            ? "bg-red-500"
            : a.status === "maybe"
            ? "bg-yellow-400"
            : "bg-slate-300";

        return (
          <div
            key={i}
            className={`h-2 flex-1 rounded ${color}`}
          />
        );
      })}
    </div>
  );
}

const RSVP_STYLES = {
  accepted: {
    active: "bg-green-500 text-white border-green-500",
    inactive: "border border-green-200 text-green-700 hover:bg-green-50 dark:border-green-800 dark:text-green-400 dark:hover:bg-green-950",
    dot: "bg-green-500",
    label: "Accepted",
  },
  declined: {
    active: "bg-red-500 text-white border-red-500",
    inactive: "border border-red-200 text-red-700 hover:bg-red-50 dark:border-red-800 dark:text-red-400 dark:hover:bg-red-950",
    dot: "bg-red-500",
    label: "Declined",
  },
  maybe: {
    active: "bg-yellow-400 text-white border-yellow-400",
    inactive: "border border-yellow-200 text-yellow-700 hover:bg-yellow-50 dark:border-yellow-800 dark:text-yellow-400 dark:hover:bg-yellow-950",
    dot: "bg-yellow-400",
    label: "Maybe",
  },
} as const;

export default function MeetingList() {
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [reschedulingMeeting, setReschedulingMeeting] = useState<Meeting | null>(null);

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
            Manage your group meetings and availability.
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
            {groupedMeetings.upcoming.length === 0 && (
              <p className="text-sm text-slate-400">No upcoming meetings.</p>
            )}
            {groupedMeetings.upcoming.map((meeting) => (
              <MeetingCard
                key={meeting.id}
                meeting={meeting}
                onRsvp={handleRsvp}
                onReschedule={setReschedulingMeeting}
              />
            ))}
          </section>
          <section className="space-y-4">
            <h2 className="text-xl font-semibold dark:text-white">Past</h2>
            {groupedMeetings.past.map((meeting) => (
              <MeetingCard
                key={meeting.id}
                meeting={meeting}
                onRsvp={handleRsvp}
                onReschedule={setReschedulingMeeting}
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

      {reschedulingMeeting && (
        <RescheduleMeetingModal
          onClose={() => setReschedulingMeeting(null)}
          meeting={reschedulingMeeting}
          onSuccess={() => { setReschedulingMeeting(null); loadMeetings(); }}
        />
      )}
    </div>
  );
}

function MeetingCard({
  meeting,
  onRsvp,
  onReschedule,
}: {
  meeting: Meeting;
  onRsvp: (meetingId: number, status: "accepted" | "declined" | "maybe") => Promise<void>;
  onReschedule: (meeting: Meeting) => void;
}) {
  const isCancelled = meeting.status === "cancelled";
  const rsvp = meeting.current_user_status;
  const isVirtual = meeting.meeting_type === "virtual";

  const cardBg = isCancelled
    ? "border-slate-200 bg-slate-50 opacity-50 dark:border-slate-800 dark:bg-slate-900/50"
    : rsvp === "maybe"
    ? "border-yellow-400 bg-yellow-50 dark:border-yellow-700 dark:bg-yellow-900/20"
    : "border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900";

  return (
    <article className={`rounded-2xl border p-5 shadow-sm transition-all ${cardBg}`}>
      <div className="flex justify-between items-start gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className="inline-block h-3 w-3 rounded-full shrink-0" style={{ backgroundColor: meeting.color }} />
          <h3 className="text-lg font-semibold truncate dark:text-white">{meeting.title}</h3>
        </div>
        <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${isVirtual ? "bg-purple-100 text-purple-700" : "bg-slate-100 text-slate-600"}`}>
          {isVirtual ? "💻 Virtual" : "🏢 In Person"}
        </span>
      </div>

      <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
        🗓 {formatDateTime(meeting.start_time)} — {formatDateTime(meeting.end_time)}
      </p>

      {meeting.location && (
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">📍 {meeting.location}</p>
      )}

      {meeting.attendees && meeting.attendees.length > 0 && (
        <div className="mt-4 pt-4 border-t border-slate-100 dark:border-slate-800">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Group Availability</p>
          <AvailabilityBar attendees={meeting.attendees} />
          <ul className="mt-3 space-y-1">
            {meeting.attendees.map((attendee) => (
              <li key={attendee.email} className="flex items-center justify-between text-sm">
                <span className="text-slate-700 dark:text-slate-300">
                  {attendee.first_name ? `${attendee.first_name} ${attendee.last_name}` : attendee.email}
                </span>
                <span className={`text-xs font-medium capitalize ${
                  attendee.status === "accepted" ? "text-green-600"
                  : attendee.status === "declined" ? "text-red-500"
                  : attendee.status === "maybe" ? "text-yellow-500"
                  : "text-slate-400"
                }`}>
                  {attendee.status ?? "pending"}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {!isCancelled && meeting.is_organizer && (
        <div className="mt-4 flex gap-2">
          {meeting.declined_count > 0 && (
            <button
              onClick={() => onReschedule(meeting)}
              className="rounded-lg px-3 py-1.5 text-sm font-medium border border-orange-200 text-orange-700 hover:bg-orange-50 dark:border-orange-800 dark:text-orange-400 dark:hover:bg-orange-950 transition-colors"
            >
              🔄 Reschedule
            </button>
          )}
          <button
            onClick={() => onCancel(meeting.id)}
            className="rounded-lg px-3 py-1.5 text-sm font-medium border border-red-200 text-red-700 hover:bg-red-50 dark:border-red-800 dark:text-red-400 dark:hover:bg-red-950 transition-colors"
          >
            Cancel Meeting
          </button>
        </div>
      )}

      {!isCancelled && !meeting.is_organizer && (
        <div className="mt-4 flex gap-2">
          {(["accepted", "declined", "maybe"] as const).map((s) => (
            <button
              key={s}
              onClick={() => onRsvp(meeting.id, s)}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                rsvp === s ? RSVP_STYLES[s].active : RSVP_STYLES[s].inactive
              }`}
            >
              {RSVP_STYLES[s].label}
            </button>
          ))}
        </div>
      )}
      </article>
  );
}