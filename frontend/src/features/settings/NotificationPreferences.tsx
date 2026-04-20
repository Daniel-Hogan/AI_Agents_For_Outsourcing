import { useMemo, useState } from "react";

interface NotificationPreferencesState {
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

const STORAGE_KEY = "notification_preferences";

function loadPreferences(): NotificationPreferencesState {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return DEFAULT_PREFERENCES;

  try {
    const parsed = JSON.parse(raw) as Partial<NotificationPreferencesState>;
    return {
      ...DEFAULT_PREFERENCES,
      ...parsed,
    };
  } catch {
    return DEFAULT_PREFERENCES;
  }
}

const TIME_OPTIONS = Array.from({ length: 24 * 2 }, (_, index) => {
  const hours = Math.floor(index / 2)
    .toString()
    .padStart(2, "0");
  const minutes = index % 2 === 0 ? "00" : "30";
  return `${hours}:${minutes}`;
});

export default function NotificationPreferences() {
  const [prefs, setPrefs] = useState<NotificationPreferencesState>(loadPreferences);
  const [isSaving, setIsSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);

  const channelsSummary = useMemo(() => {
    const channels = [];
    if (prefs.email) channels.push("Email");
    if (prefs.inApp) channels.push("In-app");
    if (channels.length === 0) return "No channels enabled";
    return channels.join(" + ");
  }, [prefs.email, prefs.inApp]);

  function updatePref<K extends keyof NotificationPreferencesState>(
    key: K,
    value: NotificationPreferencesState[K]
  ) {
    setPrefs((current) => ({ ...current, [key]: value }));
    if (saveMessage) setSaveMessage(null);
  }

  async function handleSave() {
    setIsSaving(true);

    // Keep local persistence until a backend endpoint is available.
    localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));

    await new Promise((resolve) => setTimeout(resolve, 250));

    setSaveMessage("Notification preferences saved.");
    setIsSaving(false);
  }

  return (
    <section className="bg-white dark:bg-slate-900 p-6 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm mt-6">
      <div className="mb-6">
        <h2 className="text-xl font-bold text-slate-800 dark:text-white">Notification Preferences</h2>
        <p className="mt-2 text-slate-500 dark:text-slate-400">
          Choose where alerts appear and when we should stay quiet.
        </p>
      </div>

      <div className="space-y-6">
        <div className="rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/40 p-4">
          <p className="text-sm text-slate-600 dark:text-slate-300 mb-4">Delivery channels: {channelsSummary}</p>

          <label className="flex items-center justify-between py-2">
            <span className="text-slate-800 dark:text-slate-100">Email notifications</span>
            <input
              type="checkbox"
              checked={prefs.email}
              onChange={(event) => updatePref("email", event.target.checked)}
              className="w-5 h-5 rounded border-slate-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
            />
          </label>

          <label className="flex items-center justify-between py-2">
            <span className="text-slate-800 dark:text-slate-100">In-app notifications</span>
            <input
              type="checkbox"
              checked={prefs.inApp}
              onChange={(event) => updatePref("inApp", event.target.checked)}
              className="w-5 h-5 rounded border-slate-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
            />
          </label>
        </div>

        <div className="rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/40 p-4">
          <h3 className="font-semibold text-slate-900 dark:text-white mb-2">What to notify</h3>

          <label className="flex items-center justify-between py-2">
            <span className="text-slate-800 dark:text-slate-100">Meeting reminders</span>
            <input
              type="checkbox"
              checked={prefs.meetingReminders}
              onChange={(event) => updatePref("meetingReminders", event.target.checked)}
              className="w-5 h-5 rounded border-slate-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
            />
          </label>

          <label className="flex items-center justify-between py-2">
            <span className="text-slate-800 dark:text-slate-100">Group activity updates</span>
            <input
              type="checkbox"
              checked={prefs.groupActivity}
              onChange={(event) => updatePref("groupActivity", event.target.checked)}
              className="w-5 h-5 rounded border-slate-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
            />
          </label>

          <label className="flex items-center justify-between py-2 gap-4">
            <span className="text-slate-800 dark:text-slate-100">Digest emails</span>
            <div className="flex items-center gap-3">
              <input
                type="checkbox"
                checked={prefs.weeklyDigest}
                onChange={(event) => updatePref("weeklyDigest", event.target.checked)}
                className="w-5 h-5 rounded border-slate-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
              />
              <select
                value={prefs.digestFrequency}
                onChange={(event) => updatePref("digestFrequency", event.target.value as "daily" | "weekly")}
                disabled={!prefs.weeklyDigest}
                className="px-3 py-2 bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-white outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
              >
                <option value="daily">Daily</option>
                <option value="weekly">Weekly</option>
              </select>
            </div>
          </label>
        </div>

        <div className="rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/40 p-4">
          <h3 className="font-semibold text-slate-900 dark:text-white mb-2">Quiet hours</h3>

          <label className="flex items-center justify-between py-2">
            <span className="text-slate-800 dark:text-slate-100">Pause non-urgent notifications</span>
            <input
              type="checkbox"
              checked={prefs.quietHoursEnabled}
              onChange={(event) => updatePref("quietHoursEnabled", event.target.checked)}
              className="w-5 h-5 rounded border-slate-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
            />
          </label>

          <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-3">
            <label className="text-sm text-slate-600 dark:text-slate-300">
              Start
              <select
                value={prefs.quietHoursStart}
                onChange={(event) => updatePref("quietHoursStart", event.target.value)}
                disabled={!prefs.quietHoursEnabled}
                className="mt-1 w-full px-3 py-2 bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-white outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
              >
                {TIME_OPTIONS.map((time) => (
                  <option key={`start-${time}`} value={time}>
                    {time}
                  </option>
                ))}
              </select>
            </label>

            <label className="text-sm text-slate-600 dark:text-slate-300">
              End
              <select
                value={prefs.quietHoursEnd}
                onChange={(event) => updatePref("quietHoursEnd", event.target.value)}
                disabled={!prefs.quietHoursEnabled}
                className="mt-1 w-full px-3 py-2 bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-800 dark:text-white outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
              >
                {TIME_OPTIONS.map((time) => (
                  <option key={`end-${time}`} value={time}>
                    {time}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>
      </div>

      <div className="mt-8 flex items-center justify-between gap-3">
        <p className="text-sm text-slate-500 dark:text-slate-400">{saveMessage ?? " "}</p>
        <button
          type="button"
          onClick={handleSave}
          disabled={isSaving}
          className="px-6 py-2.5 bg-blue-600 hover:bg-blue-500 text-white font-medium rounded-lg transition disabled:opacity-50"
        >
          {isSaving ? "Saving..." : "Save Preferences"}
        </button>
      </div>
    </section>
  );
}
