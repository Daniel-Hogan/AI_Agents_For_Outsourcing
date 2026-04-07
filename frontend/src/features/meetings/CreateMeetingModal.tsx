import { type FormEvent, useEffect, useState } from "react";
import { createMeeting } from "../../services/meetingsApi";

interface CreateMeetingModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

function toDateTimeString(date: string, time: string) {
  return `${date}T${time}:00`;
}

const DEFAULT_COLOR = "#2563eb";

export default function CreateMeetingModal({ isOpen, onClose, onSuccess }: CreateMeetingModalProps) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [location, setLocation] = useState("");
  const [date, setDate] = useState("");
  const [startTime, setStartTime] = useState("09:00");
  const [endTime, setEndTime] = useState("10:00");
  const [attendeeEmails, setAttendeeEmails] = useState("");
  
  // State for recommended slots
  const [recommendedSlots, setRecommendedSlots] = useState<{start: string, end: string}[] | null>(null);
  const [loadingSlots, setLoadingSlots] = useState(false);

  // Pre-fill today's date when modal opens
  useEffect(() => {
    if (isOpen) {
      const now = new Date();
      setDate(`${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`);
      setRecommendedSlots(null);
    }
  }, [isOpen]);

  if (!isOpen) return null;

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
      await createMeeting({
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

      // Reset form and close
      setTitle("");
      setDescription("");
      setLocation("");
      setAttendeeEmails("");
      onSuccess(); // Refresh the list
      onClose();   // Close modal
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create meeting.");
    } finally {
      setSaving(false);
    }
  }

  // replace this with an API call to get recommended times
  const fetchRecommendedSlots = () => {
    setLoadingSlots(true);
    setTimeout(() => {
      setRecommendedSlots([
        { start: "10:00", end: "11:00" },
        { start: "13:30", end: "14:30" },
        { start: "15:00", end: "16:00" }
      ]);
      setLoadingSlots(false);
    }, 500); 
  };

  const handleSelectSlot = (slot: {start: string, end: string}) => {
    setStartTime(slot.start);
    setEndTime(slot.end);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/60 backdrop-blur-sm">
      <div className="relative w-full max-w-lg p-6 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-2xl">
        <h2 className="text-2xl font-bold text-slate-800 dark:text-white mb-2">Schedule a Meeting</h2>
        <p className="text-slate-500 dark:text-slate-400 text-sm mb-6">Manually block out time on the calendar.</p>

        <form onSubmit={handleCreateMeeting} className="grid gap-4">
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
              onChange={(event) => { setDate(event.target.value); setRecommendedSlots(null); }}
              className="rounded-lg border border-slate-200 px-4 py-3 text-slate-900 outline-none focus:border-blue-500 dark:border-slate-700 dark:bg-slate-950 dark:text-white [color-scheme:dark]"
            />
            <input
              type="time"
              value={startTime}
              onChange={(event) => setStartTime(event.target.value)}
              className="rounded-lg border border-slate-200 px-4 py-3 text-slate-900 outline-none focus:border-blue-500 dark:border-slate-700 dark:bg-slate-950 dark:text-white [color-scheme:dark]"
            />
            <input
              type="time"
              value={endTime}
              onChange={(event) => setEndTime(event.target.value)}
              className="rounded-lg border border-slate-200 px-4 py-3 text-slate-900 outline-none focus:border-blue-500 dark:border-slate-700 dark:bg-slate-950 dark:text-white [color-scheme:dark]"
            />
          </div>

          {/* recommended time slots  */}
          <div className="bg-slate-50 dark:bg-slate-800/50 p-3 rounded-lg border border-slate-200 dark:border-slate-700">
            <div className="flex justify-between items-center">
              <span className="text-sm font-medium text-slate-700 dark:text-slate-300">Recommended Times</span>
              <button 
                type="button" 
                onClick={fetchRecommendedSlots} 
                disabled={loadingSlots}
                className="text-blue-600 dark:text-blue-400 text-sm hover:underline disabled:opacity-50"
              >
                {loadingSlots ? "Searching..." : "Find Slots"}
              </button>
            </div>
            
            {recommendedSlots && (
              <div className="flex flex-wrap gap-2 mt-3">
                {recommendedSlots.map((slot, index) => (
                  <button
                    key={index}
                    type="button"
                    onClick={() => handleSelectSlot(slot)}
                    className="px-3 py-1.5 text-xs font-medium bg-blue-100 text-blue-700 hover:bg-blue-200 dark:bg-blue-900/40 dark:text-blue-300 dark:hover:bg-blue-900/60 rounded-full transition-colors"
                  >
                    {slot.start} - {slot.end}
                  </button>
                ))}
                {recommendedSlots.length === 0 && (
                  <span className="text-xs text-slate-500">No recommended slots found for this date.</span>
                )}
              </div>
            )}
          </div>

          <input
            value={attendeeEmails}
            onChange={(event) => setAttendeeEmails(event.target.value)}
            placeholder="Invite attendee emails, comma-separated"
            className="rounded-lg border border-slate-200 px-4 py-3 text-slate-900 outline-none focus:border-blue-500 dark:border-slate-700 dark:bg-slate-950 dark:text-white"
          />

          {error ? <p className="text-sm text-red-500">{error}</p> : null}

          <div className="flex justify-end gap-3 mt-4 pt-4 border-t border-slate-200 dark:border-slate-800">
            <button 
              type="button"
              onClick={onClose}
              className="px-5 py-2.5 text-sm font-medium text-slate-500 dark:text-slate-300 hover:text-slate-800 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-blue-500 disabled:opacity-50"
            >
              {saving ? "Creating..." : "Create Meeting"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}