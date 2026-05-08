import { useEffect, useState } from "react";
import {
  fetchRescheduleSuggestions,
  updateMeeting,
  type Meeting,
  type MeetingRecommendation,
} from "../../services/meetingsApi";

interface Props {
  meeting: Meeting;
  onClose: () => void;
  onSuccess: () => void;
}

function extractDate(value: string) {
  return value.split("T")[0];
}

function extractTime(value: string) {
  return value.split("T")[1]?.slice(0, 5) ?? "";
}

function formatTimeChip(value: string) {
  const [hours, minutes] = extractTime(value).split(":").map(Number);
  const d = new Date();
  d.setHours(hours, minutes, 0, 0);
  return d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function formatDateChip(value: string) {
  const [year, month, day] = extractDate(value).split("-").map(Number);
  return new Date(year, month - 1, day).toLocaleDateString([], {
    weekday: "short", month: "short", day: "numeric",
  });
}

function getDurationMinutes(start: string, end: string) {
  const [sh, sm] = start.split(":").map(Number);
  const [eh, em] = end.split(":").map(Number);
  return eh * 60 + em - (sh * 60 + sm);
}

export default function RescheduleMeetingModal({ meeting, onClose, onSuccess }: Props) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [slotError, setSlotError] = useState("");
  const [loadingSlots, setLoadingSlots] = useState(false);
  const [suggestions, setSuggestions] = useState<MeetingRecommendation[] | null>(null);

  const [date, setDate] = useState(extractDate(meeting.start_time));
  const [startTime, setStartTime] = useState(extractTime(meeting.start_time));
  const [endTime, setEndTime] = useState(extractTime(meeting.end_time));
  const [searchDate, setSearchDate] = useState(extractDate(meeting.start_time));

  const declinedAttendees = meeting.attendees.filter(a => a.status === "declined");
  const duration = getDurationMinutes(
    extractTime(meeting.start_time),
    extractTime(meeting.end_time)
  );

  // Auto-fetch suggestions on open
  useEffect(() => {
    fetchSuggestions();
  }, []);

  async function fetchSuggestions() {
    setLoadingSlots(true);
    setSlotError("");
    setSuggestions(null);
    try {
      const attendeeEmails = meeting.attendees
        .filter(a => a.status !== "declined")
        .map(a => a.email);

      const response = await fetchRescheduleSuggestions(meeting.id, {
        attendee_emails: attendeeEmails,
        start_date: searchDate,
        end_date: searchDate,
        duration_minutes: duration,
        max_results: 4,
        include_organizer: true,
      });
      setSuggestions(response.recommendations);
    } catch (err) {
      setSlotError(err instanceof Error ? err.message : "Could not load suggestions.");
      setSuggestions([]);
    } finally {
      setLoadingSlots(false);
    }
  }

  function handleSelectSlot(slot: MeetingRecommendation) {
    setDate(extractDate(slot.start_time));
    setStartTime(extractTime(slot.start_time));
    setEndTime(extractTime(slot.end_time));
  }

  async function handleSave() {
    if (!date || !startTime || !endTime) {
      setError("Please fill in all time fields.");
      return;
    }
    if (endTime <= startTime) {
      setError("End time must be after start time.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await updateMeeting(meeting.id, {
        start_time: `${date}T${startTime}:00`,
        end_time: `${date}T${endTime}:00`,
      });
      onSuccess();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to reschedule meeting.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/60 backdrop-blur-sm">
      <div className="relative w-full max-w-lg p-6 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-2xl">
        <h2 className="text-2xl font-bold text-slate-800 dark:text-white mb-1">Reschedule Meeting</h2>
        <p className="text-sm text-slate-500 dark:text-slate-400 mb-5">
          {meeting.title}
        </p>

        {/* Declined attendees notice */}
        {declinedAttendees.length > 0 && (
          <div className="mb-4 p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800">
            <p className="text-xs font-semibold text-red-700 dark:text-red-400 uppercase tracking-wide mb-1">
              Declined
            </p>
            <p className="text-sm text-red-600 dark:text-red-300">
              {declinedAttendees.map(a =>
                a.first_name ? `${a.first_name} ${a.last_name}` : a.email
              ).join(", ")}
            </p>
          </div>
        )}

        {/* Suggested slots */}
        <div className="mb-4 p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700">
          <div className="flex justify-between items-center mb-2">
            <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
              Suggested Times
            </span>
            <div className="flex items-center gap-2">
              <input
                type="date"
                value={searchDate}
                onChange={e => setSearchDate(e.target.value)}
                className="text-xs rounded border border-slate-200 dark:border-slate-700 px-2 py-1 dark:bg-slate-950 dark:text-white [color-scheme:dark]"
              />
              <button
                type="button"
                onClick={fetchSuggestions}
                disabled={loadingSlots}
                className="text-xs text-blue-600 dark:text-blue-400 hover:underline disabled:opacity-50"
              >
                {loadingSlots ? "Searching..." : "Refresh"}
              </button>
            </div>
          </div>

          {slotError && <p className="text-xs text-red-500 mb-2">{slotError}</p>}

          {suggestions && suggestions.length === 0 && (
            <p className="text-xs text-slate-500">No available slots found for this date.</p>
          )}

          {suggestions && suggestions.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {suggestions.map((slot, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => handleSelectSlot(slot)}
                  title={slot.reason}
                  className={`px-3 py-1.5 text-xs font-medium rounded-full transition-colors ${
                    extractDate(slot.start_time) === date &&
                    extractTime(slot.start_time) === startTime
                      ? "bg-blue-600 text-white"
                      : "bg-blue-100 text-blue-700 hover:bg-blue-200 dark:bg-blue-900/40 dark:text-blue-300 dark:hover:bg-blue-900/60"
                  }`}
                >
                  {formatDateChip(slot.start_time)} · {formatTimeChip(slot.start_time)}–{formatTimeChip(slot.end_time)}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Manual time picker */}
        <div className="grid grid-cols-3 gap-3 mb-4">
          <input
            type="date"
            value={date}
            onChange={e => setDate(e.target.value)}
            className="rounded-lg border border-slate-200 px-3 py-2.5 text-sm text-slate-900 outline-none focus:border-blue-500 dark:border-slate-700 dark:bg-slate-950 dark:text-white [color-scheme:dark]"
          />
          <input
            type="time"
            value={startTime}
            onChange={e => setStartTime(e.target.value)}
            className="rounded-lg border border-slate-200 px-3 py-2.5 text-sm text-slate-900 outline-none focus:border-blue-500 dark:border-slate-700 dark:bg-slate-950 dark:text-white [color-scheme:dark]"
          />
          <input
            type="time"
            value={endTime}
            onChange={e => setEndTime(e.target.value)}
            className="rounded-lg border border-slate-200 px-3 py-2.5 text-sm text-slate-900 outline-none focus:border-blue-500 dark:border-slate-700 dark:bg-slate-950 dark:text-white [color-scheme:dark]"
          />
        </div>

        {error && <p className="text-sm text-red-500 mb-3">{error}</p>}

        <div className="flex justify-end gap-3 pt-4 border-t border-slate-200 dark:border-slate-800">
          <button
            type="button"
            onClick={onClose}
            className="px-5 py-2.5 text-sm font-medium text-slate-500 dark:text-slate-300 hover:text-slate-800 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-blue-500 disabled:opacity-50"
          >
            {saving ? "Saving..." : "Reschedule"}
          </button>
        </div>
      </div>
    </div>
  );
}