import { useEffect, useState } from "react";

import type { SessionUser } from "../auth/auth.types";
import { useAuth } from "../../context/AuthContext";
import { apiJson } from "../../lib/api";

const AVATAR_COLORS = [
  { id: "blue", bg: "bg-blue-500" },
  { id: "purple", bg: "bg-purple-500" },
  { id: "green", bg: "bg-green-500" },
  { id: "orange", bg: "bg-orange-500" },
  { id: "pink", bg: "bg-pink-500" },
  { id: "teal", bg: "bg-teal-500" },
  { id: "red", bg: "bg-red-500" },
  { id: "yellow", bg: "bg-yellow-500" },
] as const;

const AVATAR_STORAGE_KEY = "avatar_color_id";

function getInitials(firstName: string, lastName: string) {
  return `${firstName.charAt(0)}${lastName.charAt(0)}`.toUpperCase();
}

export default function ProfileCard() {
  const { setUser } = useAuth();
  const [profile, setProfile] = useState<SessionUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");

  const [selectedColorId, setSelectedColorId] = useState<string>(() => localStorage.getItem(AVATAR_STORAGE_KEY) ?? "blue");

  const [showPasswordSection, setShowPasswordSection] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  useEffect(() => {
    apiJson<SessionUser>("/auth/me")
      .then((data) => {
        const savedColorId = data.avatar_color || localStorage.getItem(AVATAR_STORAGE_KEY) || "blue";
        setProfile(data);
        setFirstName(data.first_name);
        setLastName(data.last_name);
        setEmail(data.email);
        setSelectedColorId(savedColorId);
      })
      .catch(() => setError("Failed to load profile."))
      .finally(() => setLoading(false));
  }, []);

  const selectedColor = AVATAR_COLORS.find((color) => color.id === selectedColorId) ?? AVATAR_COLORS[0];

  async function handleSaveProfile() {
    setError("");
    setSuccess("");

    if (!firstName.trim() || !lastName.trim() || !email.trim()) {
      setError("First name, last name, and email are required.");
      return;
    }

    if (showPasswordSection) {
      if (!currentPassword) {
        setError("Please enter your current password.");
        return;
      }
      if (newPassword !== confirmPassword) {
        setError("New passwords do not match.");
        return;
      }
      if (newPassword.length < 8) {
        setError("New password must be at least 8 characters.");
        return;
      }
    }

    setSaving(true);
    try {
      const body: Record<string, string> = {
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        email: email.trim(),
        avatar_color: selectedColorId,
      };
      if (showPasswordSection && newPassword) {
        body.current_password = currentPassword;
        body.new_password = newPassword;
      }

      const updated = await apiJson<SessionUser>("/auth/me", {
        method: "PATCH",
        body: JSON.stringify(body),
      });

      localStorage.setItem(AVATAR_STORAGE_KEY, selectedColorId);
      setUser(updated);
      setProfile(updated);
      setSuccess("Profile updated successfully.");
      setShowPasswordSection(false);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update profile.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <div className="p-6 text-slate-400">Loading profile...</div>;

  const initials = profile ? getInitials(firstName, lastName) : "??";

  return (
    <div className="bg-white dark:bg-slate-900 p-6 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
      <h2 className="text-xl font-bold text-slate-800 dark:text-white mb-6">Profile</h2>

      <div className="flex items-center gap-6 mb-8">
        <div className={`w-20 h-20 rounded-full ${selectedColor.bg} flex items-center justify-center text-white text-2xl font-bold shadow-md shrink-0`}>
          {initials}
        </div>
        <div>
          <p className="text-lg font-semibold text-slate-800 dark:text-white">
            {firstName} {lastName}
          </p>
          <p className="text-sm text-slate-500 dark:text-slate-400 mb-3">{email}</p>
          <div className="flex gap-2 flex-wrap">
            {AVATAR_COLORS.map((color) => (
              <button
                key={color.id}
                type="button"
                onClick={() => setSelectedColorId(color.id)}
                className={`w-7 h-7 rounded-full ${color.bg} transition-transform hover:scale-110 ${
                  selectedColorId === color.id ? "ring-2 ring-offset-2 ring-slate-800 dark:ring-white scale-110" : ""
                }`}
                title={color.id}
              />
            ))}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
        <div>
          <label className="block text-sm font-medium text-slate-600 dark:text-slate-300 mb-1">
            First Name
          </label>
          <input
            value={firstName}
            onChange={(event) => setFirstName(event.target.value)}
            className="w-full px-4 py-2.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950 text-slate-900 dark:text-white outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-600 dark:text-slate-300 mb-1">
            Last Name
          </label>
          <input
            value={lastName}
            onChange={(event) => setLastName(event.target.value)}
            className="w-full px-4 py-2.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950 text-slate-900 dark:text-white outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      </div>

      <div className="mb-6">
        <label className="block text-sm font-medium text-slate-600 dark:text-slate-300 mb-1">
          Email
        </label>
        <input
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          className="w-full px-4 py-2.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950 text-slate-900 dark:text-white outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      <div className="mb-6">
        <button
          type="button"
          onClick={() => setShowPasswordSection((current) => !current)}
          className="text-sm font-medium text-blue-600 dark:text-blue-400 hover:underline"
        >
          {showPasswordSection ? "Cancel password change" : "Change password"}
        </button>

        {showPasswordSection && (
          <div className="mt-4 space-y-3">
            <div>
              <label className="block text-sm font-medium text-slate-600 dark:text-slate-300 mb-1">
                Current Password
              </label>
              <input
                type="password"
                value={currentPassword}
                onChange={(event) => setCurrentPassword(event.target.value)}
                className="w-full px-4 py-2.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950 text-slate-900 dark:text-white outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-600 dark:text-slate-300 mb-1">
                New Password
              </label>
              <input
                type="password"
                value={newPassword}
                onChange={(event) => setNewPassword(event.target.value)}
                className="w-full px-4 py-2.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950 text-slate-900 dark:text-white outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-600 dark:text-slate-300 mb-1">
                Confirm New Password
              </label>
              <input
                type="password"
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                className="w-full px-4 py-2.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950 text-slate-900 dark:text-white outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
        )}
      </div>

      {error ? <p className="text-sm text-red-500 mb-3">{error}</p> : null}
      {success ? <p className="text-sm text-green-600 mb-3">{success}</p> : null}

      <div className="flex justify-end">
        <button
          type="button"
          onClick={handleSaveProfile}
          disabled={saving}
          className="px-6 py-2.5 bg-blue-600 hover:bg-blue-500 text-white font-medium rounded-lg transition disabled:opacity-50"
        >
          {saving ? "Saving..." : "Save Changes"}
        </button>
      </div>
    </div>
  );
}
