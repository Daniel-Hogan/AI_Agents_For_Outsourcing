import AvailabilitySettings from "./AvailabilitySettings";
import NotificationPreferences from "./NotificationPreferences";

export default function ProfileSettings() {
  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-slate-800 dark:text-white">Profile Settings</h1>
        <p className="text-slate-500 dark:text-slate-400 mt-2">Manage your account preferences and working hours.</p>
      </div>

      <AvailabilitySettings />
      <NotificationPreferences />
    </div>
  );
}