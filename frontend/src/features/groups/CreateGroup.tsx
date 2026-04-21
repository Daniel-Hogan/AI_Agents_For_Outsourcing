import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { createGroup, joinGroup } from "./groups.api";

type Mode = "create" | "join";

export default function CreateGroup() {
	const navigate = useNavigate();
	const location = useLocation();

	const [mode, setMode] = useState<Mode>("create");
	const [groupName, setGroupName] = useState("");
	const [description, setDescription] = useState("");
	const [inviteCode, setInviteCode] = useState("");
	const [groupId, setGroupId] = useState("");

	const [isSubmitting, setIsSubmitting] = useState(false);
	const [error, setError] = useState("");
	const [success, setSuccess] = useState("");

	useEffect(() => {
		if (location.pathname.includes("/join")) {
			setMode("join");
			return;
		}
		setMode("create");
	}, [location.pathname]);

	async function handleCreateSubmit(e: FormEvent<HTMLFormElement>) {
		e.preventDefault();
		setIsSubmitting(true);
		setError("");
		setSuccess("");

		try {
			await createGroup({
				name: groupName.trim(),
				description: description.trim() || undefined,
			});
			setSuccess("Group created successfully. Redirecting...");
			setGroupName("");
			setDescription("");
			window.setTimeout(() => navigate("/groups"), 700);
		} catch (err) {
			setError(err instanceof Error ? err.message : "Could not create group");
		} finally {
			setIsSubmitting(false);
		}
	}

	async function handleJoinSubmit(e: FormEvent<HTMLFormElement>) {
		e.preventDefault();
		setIsSubmitting(true);
		setError("");
		setSuccess("");

		const parsedGroupId = groupId.trim() ? Number(groupId) : undefined;

		if (!inviteCode.trim() && !parsedGroupId) {
			setError("Enter an invite code or a group ID.");
			setIsSubmitting(false);
			return;
		}

		try {
			await joinGroup({
				inviteCode: inviteCode.trim() || undefined,
				groupId: Number.isFinite(parsedGroupId) ? parsedGroupId : undefined,
			});
			setSuccess("You joined the group. Redirecting...");
			setInviteCode("");
			setGroupId("");
			window.setTimeout(() => navigate("/groups"), 700);
		} catch (err) {
			setError(err instanceof Error ? err.message : "Could not join group");
		} finally {
			setIsSubmitting(false);
		}
	}

	return (
		<div className="max-w-2xl mx-auto">
			<div className="mb-6">
				<h1 className="text-3xl font-bold text-slate-900 dark:text-white">Groups</h1>
				<p className="text-slate-600 dark:text-slate-400 mt-2">
					Create a new group for your team or join one with an invite code.
				</p>
			</div>

			<div className="inline-flex bg-slate-100 dark:bg-slate-800 p-1 rounded-xl mb-6 border border-slate-200 dark:border-slate-700">
				<button
					type="button"
					onClick={() => {
						setMode("create");
						setError("");
						setSuccess("");
					}}
					className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
						mode === "create"
							? "bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow"
							: "text-slate-600 dark:text-slate-300"
					}`}
				>
					Create Group
				</button>
				<button
					type="button"
					onClick={() => {
						setMode("join");
						setError("");
						setSuccess("");
					}}
					className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
						mode === "join"
							? "bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow"
							: "text-slate-600 dark:text-slate-300"
					}`}
				>
					Join Group
				</button>
			</div>

			<div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-2xl p-6 shadow-sm">
				{mode === "create" ? (
					<form className="space-y-4" onSubmit={handleCreateSubmit}>
						<div>
							<label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1">
								Group Name
							</label>
							<input
								value={groupName}
								onChange={(e) => setGroupName(e.target.value)}
								required
								className="w-full rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 text-slate-900 dark:text-white"
								placeholder="Design Team"
							/>
						</div>
						<div>
							<label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1">
								Description (Optional)
							</label>
							<textarea
								value={description}
								onChange={(e) => setDescription(e.target.value)}
								className="w-full rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 text-slate-900 dark:text-white"
								rows={3}
								placeholder="Weekly sync and planning"
							/>
						</div>
						<button
							type="submit"
							disabled={isSubmitting}
							className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white px-4 py-2 rounded-lg font-medium transition"
						>
							{isSubmitting ? "Creating..." : "Create Group"}
						</button>
					</form>
				) : (
					<form className="space-y-4" onSubmit={handleJoinSubmit}>
						<div>
							<label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1">
								Invite Code
							</label>
							<input
								value={inviteCode}
								onChange={(e) => setInviteCode(e.target.value)}
								className="w-full rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 text-slate-900 dark:text-white"
								placeholder="ABC123"
							/>
						</div>

						<div className="text-xs font-semibold tracking-wide uppercase text-slate-500 dark:text-slate-400">
							or
						</div>

						<div>
							<label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1">
								Group ID
							</label>
							<input
								type="number"
								min={1}
								value={groupId}
								onChange={(e) => setGroupId(e.target.value)}
								className="w-full rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 text-slate-900 dark:text-white"
								placeholder="12"
							/>
						</div>

						<button
							type="submit"
							disabled={isSubmitting}
							className="bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white px-4 py-2 rounded-lg font-medium transition"
						>
							{isSubmitting ? "Joining..." : "Join Group"}
						</button>
					</form>
				)}

				{error ? <p className="text-red-500 text-sm mt-4">{error}</p> : null}
				{success ? <p className="text-emerald-500 text-sm mt-4">{success}</p> : null}
			</div>
		</div>
	);
}
