import { useState, useEffect } from "react";
import MonthView from "./MonthView";
import WeekView from "./WeekView";
import {
  fetchEvents,
  createEvent,
  updateEvent,
  deleteEvent,
} from "../../services/calendarApi";

export type CalendarEvent = {
  id: number;
  date: string;
  title: string;
  startHour: number;
  startMinute: number;
  endHour: number;
  endMinute: number;
  color?: string;
  location?: string;
};

function toLocalEvent(e: any): CalendarEvent {
  // Parse the time string directly without timezone conversion
  const startStr = e.start_time.replace("Z", "").split("T");
  const endStr = e.end_time.replace("Z", "").split("T");
  const [startH, startM] = startStr[1].split(":").map(Number);
  const [endH, endM] = endStr[1].split(":").map(Number);
  return {
    id: e.id,
    date: startStr[0],
    title: e.title,
    startHour: startH,
    startMinute: startM,
    endHour: endH,
    endMinute: endM,
    color: e.color || "#3498db",
    location: e.location,
  };
}

function toISOString(date: string, hour: number, minute: number) {
  return `${date}T${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}:00`;
}

export default function PersonalCalendar() {
  const [view, setView] = useState<"month" | "week">("month");
  const [currentDate, setCurrentDate] = useState(new Date());
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showAddModal, setShowAddModal] = useState(false);
  const [selectedEvent, setSelectedEvent] = useState<CalendarEvent | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [saving, setSaving] = useState(false);

  // Add modal state
  const [newTitle, setNewTitle] = useState("");
  const [newDate, setNewDate] = useState("");
  const [newStartHour, setNewStartHour] = useState(9);
  const [newStartMinute, setNewStartMinute] = useState(0);
  const [newEndHour, setNewEndHour] = useState(10);
  const [newEndMinute, setNewEndMinute] = useState(0);
  const [newColor, setNewColor] = useState("#3498db");
  const [newLocation, setNewLocation] = useState("");

  // Edit state
  const [editTitle, setEditTitle] = useState("");
  const [editDate, setEditDate] = useState("");
  const [editStartHour, setEditStartHour] = useState(9);
  const [editStartMinute, setEditStartMinute] = useState(0);
  const [editEndHour, setEditEndHour] = useState(10);
  const [editEndMinute, setEditEndMinute] = useState(0);
  const [editColor, setEditColor] = useState("#3498db");
  const [editLocation, setEditLocation] = useState("");

  // Load events on mount
  useEffect(() => {
    loadEvents();
  }, []);

  async function loadEvents() {
    setLoading(true);
    setError("");
    try {
      const data = await fetchEvents();
      setEvents(data.map(toLocalEvent));
    } catch {
      setError("Failed to load events. Make sure you are logged in.");
    } finally {
      setLoading(false);
    }
  }

  function openAddModal() {
    const today = new Date();
    setNewDate(`${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`);
    setNewTitle("");
    setNewStartHour(9);
    setNewStartMinute(0);
    setNewEndHour(10);
    setNewEndMinute(0);
    setNewColor("#3498db");
    setNewLocation("");
    setShowAddModal(true);
  }

  async function addEvent() {
    if (!newTitle.trim() || !newDate) return;
    const startTotal = newStartHour * 60 + newStartMinute;
    const endTotal = newEndHour * 60 + newEndMinute;
    if (endTotal <= startTotal) {
      alert("End time must be after start time.");
      return;
    }
    setSaving(true);
    try {
      const created = await createEvent({
        title: newTitle.trim(),
        start_time: toISOString(newDate, newStartHour, newStartMinute),
        end_time: toISOString(newDate, newEndHour, newEndMinute),
        location: newLocation || undefined,
        color: newColor,
      });
      setEvents(prev => [...prev, { ...toLocalEvent(created), color: newColor }]);
      setShowAddModal(false);
    } catch {
      alert("Failed to save event. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  function openEdit(ev: CalendarEvent) {
    setEditTitle(ev.title);
    setEditDate(ev.date);
    setEditStartHour(ev.startHour);
    setEditStartMinute(ev.startMinute);
    setEditEndHour(ev.endHour);
    setEditEndMinute(ev.endMinute);
    setEditColor(ev.color || "#3498db");
    setEditLocation(ev.location || "");
    setIsEditing(true);
  }

  async function saveEdit() {
    if (!editTitle.trim() || !editDate || !selectedEvent) return;
    const startTotal = editStartHour * 60 + editStartMinute;
    const endTotal = editEndHour * 60 + editEndMinute;
    if (endTotal <= startTotal) {
      alert("End time must be after start time.");
      return;
    }
    setSaving(true);
    try {
      const updated = await updateEvent(selectedEvent.id, {
        title: editTitle.trim(),
        start_time: toISOString(editDate, editStartHour, editStartMinute),
        end_time: toISOString(editDate, editEndHour, editEndMinute),
        location: editLocation || undefined,
        color: editColor,
      });
      setEvents(prev => prev.map(e =>
        e.id === selectedEvent.id
          ? { ...toLocalEvent(updated), color: editColor }
          : e
      ));
      setSelectedEvent(null);
      setIsEditing(false);
    } catch {
      alert("Failed to update event. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDeleteEvent(id: number) {
    setSaving(true);
    try {
      await deleteEvent(id);
      setEvents(prev => prev.filter(e => e.id !== id));
      setSelectedEvent(null);
      setIsEditing(false);
    } catch {
      alert("Failed to delete event. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  function closeDetailModal() {
    setSelectedEvent(null);
    setIsEditing(false);
  }

  function goBack() {
    const d = new Date(currentDate);
    if (view === "month") d.setMonth(d.getMonth() - 1);
    else d.setDate(d.getDate() - 7);
    setCurrentDate(d);
  }

  function goForward() {
    const d = new Date(currentDate);
    if (view === "month") d.setMonth(d.getMonth() + 1);
    else d.setDate(d.getDate() + 7);
    setCurrentDate(d);
  }

  function formatTime(hour: number, minute: number) {
    const h = hour % 12 === 0 ? 12 : hour % 12;
    const m = String(minute).padStart(2, "0");
    const ampm = hour < 12 ? "AM" : "PM";
    return `${h}:${m} ${ampm}`;
  }

  function getDuration(startHour: number, startMinute: number, endHour: number, endMinute: number) {
    const mins = (endHour * 60 + endMinute) - (startHour * 60 + startMinute);
    if (mins < 60) return `${mins} min`;
    const h = Math.floor(mins / 60);
    const m = mins % 60;
    return `${h}h${m ? ` ${m}m` : ""}`;
  }

  const timeSlots = Array.from({ length: 16 * 2 }, (_, i) => {
    const totalMins = (7 * 60) + i * 30;
    const h = Math.floor(totalMins / 60);
    const m = totalMins % 60;
    return { hour: h, minute: m };
  });

  const colorOptions = ["#3498db", "#e74c3c", "#2ecc71", "#f39c12", "#9b59b6", "#1abc9c"];

  if (loading) return <div style={{ padding: "2rem", textAlign: "center" }}>Loading your calendar...</div>;
  if (error) return <div style={{ padding: "2rem", color: "#e74c3c" }}>{error}</div>;

  return (
    <div style={{ fontFamily: "'Segoe UI', system-ui, sans-serif", color: "#1a1a2e" }}>

      {/* Header */}
      <div style={styles.header}>
        <h1 style={styles.title}>My Calendar</h1>
        <div style={styles.controls}>
          <button type="button" onClick={goBack} style={styles.navBtn}>◀</button>
          <button type="button" onClick={() => setCurrentDate(new Date())} style={styles.todayBtn}>Today</button>
          <button type="button" onClick={goForward} style={styles.navBtn}>▶</button>
          <div style={styles.viewToggle}>
            <button type="button" onClick={() => setView("month")} style={view === "month" ? styles.activeToggle : styles.toggleBtn}>Month</button>
            <button type="button" onClick={() => setView("week")} style={view === "week" ? styles.activeToggle : styles.toggleBtn}>Week</button>
          </div>
          <button type="button" onClick={openAddModal} style={styles.addEventBtn}>+ Add Event</button>
        </div>
      </div>

      {/* Calendar */}
      {view === "month" ? (
        <MonthView currentDate={currentDate} events={events} onEventClick={ev => { setSelectedEvent(ev); setIsEditing(false); }} />
      ) : (
        <WeekView currentDate={currentDate} events={events} onEventClick={ev => { setSelectedEvent(ev); setIsEditing(false); }} />
      )}

      {/* Add Event Modal */}
      {showAddModal && (
        <div style={styles.overlay}>
          <div style={styles.modal}>
            <h2 style={styles.modalTitle}>Add Event</h2>

            <label style={styles.label}>Title</label>
            <input placeholder="e.g. Team Meeting" value={newTitle} onChange={e => setNewTitle(e.target.value)} style={styles.input} autoFocus />

            <label style={styles.label}>Date</label>
            <input type="date" value={newDate} onChange={e => setNewDate(e.target.value)} style={styles.input} />

            <label style={styles.label}>Location (optional)</label>
            <input placeholder="e.g. Conference Room A" value={newLocation} onChange={e => setNewLocation(e.target.value)} style={styles.input} />

            <div style={styles.row}>
              <div style={{ flex: 1 }}>
                <label style={styles.label}>Start Time</label>
                <select value={`${newStartHour}:${newStartMinute}`} onChange={e => { const [h, m] = e.target.value.split(":").map(Number); setNewStartHour(h); setNewStartMinute(m); }} style={styles.input}>
                  {timeSlots.map(({ hour, minute }) => (
                    <option key={`${hour}:${minute}`} value={`${hour}:${minute}`}>{formatTime(hour, minute)}</option>
                  ))}
                </select>
              </div>
              <div style={{ flex: 1 }}>
                <label style={styles.label}>End Time</label>
                <select value={`${newEndHour}:${newEndMinute}`} onChange={e => { const [h, m] = e.target.value.split(":").map(Number); setNewEndHour(h); setNewEndMinute(m); }} style={styles.input}>
                  {timeSlots.map(({ hour, minute }) => (
                    <option key={`${hour}:${minute}`} value={`${hour}:${minute}`}>{formatTime(hour, minute)}</option>
                  ))}
                </select>
              </div>
            </div>

            <label style={styles.label}>Color</label>
            <div style={styles.colorRow}>
              {colorOptions.map(c => (
                <div key={c} onClick={() => setNewColor(c)} style={{ ...styles.colorDot, backgroundColor: c, border: newColor === c ? "3px solid #1a1a2e" : "3px solid transparent" }} />
              ))}
            </div>

            <div style={styles.modalActions}>
              <button type="button" onClick={() => setShowAddModal(false)} style={styles.cancelBtn}>Cancel</button>
              <button type="button" onClick={addEvent} disabled={saving} style={styles.addBtn}>{saving ? "Saving..." : "Add Event"}</button>
            </div>
          </div>
        </div>
      )}

      {/* Event Detail / Edit Modal */}
      {selectedEvent && (
        <div style={styles.overlay}>
          <div style={styles.modal}>
            <div style={{ ...styles.eventColorBar, backgroundColor: selectedEvent.color || "#3498db" }} />

            {isEditing ? (
              <>
                <h2 style={styles.modalTitle}>Edit Event</h2>

                <label style={styles.label}>Title</label>
                <input value={editTitle} onChange={e => setEditTitle(e.target.value)} style={styles.input} autoFocus />

                <label style={styles.label}>Date</label>
                <input type="date" value={editDate} onChange={e => setEditDate(e.target.value)} style={styles.input} />

                <label style={styles.label}>Location (optional)</label>
                <input placeholder="e.g. Conference Room A" value={editLocation} onChange={e => setEditLocation(e.target.value)} style={styles.input} />

                <div style={styles.row}>
                  <div style={{ flex: 1 }}>
                    <label style={styles.label}>Start Time</label>
                    <select value={`${editStartHour}:${editStartMinute}`} onChange={e => { const [h, m] = e.target.value.split(":").map(Number); setEditStartHour(h); setEditStartMinute(m); }} style={styles.input}>
                      {timeSlots.map(({ hour, minute }) => (
                        <option key={`${hour}:${minute}`} value={`${hour}:${minute}`}>{formatTime(hour, minute)}</option>
                      ))}
                    </select>
                  </div>
                  <div style={{ flex: 1 }}>
                    <label style={styles.label}>End Time</label>
                    <select value={`${editEndHour}:${editEndMinute}`} onChange={e => { const [h, m] = e.target.value.split(":").map(Number); setEditEndHour(h); setEditEndMinute(m); }} style={styles.input}>
                      {timeSlots.map(({ hour, minute }) => (
                        <option key={`${hour}:${minute}`} value={`${hour}:${minute}`}>{formatTime(hour, minute)}</option>
                      ))}
                    </select>
                  </div>
                </div>

                <label style={styles.label}>Color</label>
                <div style={styles.colorRow}>
                  {colorOptions.map(c => (
                    <div key={c} onClick={() => setEditColor(c)} style={{ ...styles.colorDot, backgroundColor: c, border: editColor === c ? "3px solid #1a1a2e" : "3px solid transparent" }} />
                  ))}
                </div>

                <div style={styles.modalActions}>
                  <button type="button" onClick={() => setIsEditing(false)} style={styles.cancelBtn}>Back</button>
                  <button type="button" onClick={saveEdit} disabled={saving} style={styles.addBtn}>{saving ? "Saving..." : "Save Changes"}</button>
                </div>
              </>
            ) : (
              <>
                <h2 style={styles.modalTitle}>{selectedEvent.title}</h2>
                <div style={styles.detailRow}>
                  <span style={styles.detailLabel}>📅 Date</span>
                  <span style={styles.detailValue}>{selectedEvent.date}</span>
                </div>
                <div style={styles.detailRow}>
                  <span style={styles.detailLabel}>🕐 Start</span>
                  <span style={styles.detailValue}>{formatTime(selectedEvent.startHour, selectedEvent.startMinute)}</span>
                </div>
                <div style={styles.detailRow}>
                  <span style={styles.detailLabel}>🕑 End</span>
                  <span style={styles.detailValue}>{formatTime(selectedEvent.endHour, selectedEvent.endMinute)}</span>
                </div>
                <div style={styles.detailRow}>
                  <span style={styles.detailLabel}>⏱ Duration</span>
                  <span style={styles.detailValue}>{getDuration(selectedEvent.startHour, selectedEvent.startMinute, selectedEvent.endHour, selectedEvent.endMinute)}</span>
                </div>
                {selectedEvent.location && (
                  <div style={styles.detailRow}>
                    <span style={styles.detailLabel}>📍 Location</span>
                    <span style={styles.detailValue}>{selectedEvent.location}</span>
                  </div>
                )}
                <div style={{ ...styles.modalActions, justifyContent: "space-between" }}>
                  <button type="button" onClick={() => handleDeleteEvent(selectedEvent.id)} disabled={saving} style={styles.deleteBtn}>Delete</button>
                  <div style={{ display: "flex", gap: "0.75rem" }}>
                    <button type="button" onClick={closeDetailModal} style={styles.cancelBtn}>Close</button>
                    <button type="button" onClick={() => openEdit(selectedEvent)} style={styles.addBtn}>Edit</button>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

const styles: { [key: string]: React.CSSProperties } = {
  header: { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem", flexWrap: "wrap", gap: "1rem" },
  title: { margin: 0, fontSize: "1.8rem", fontWeight: 700, letterSpacing: "-0.5px" },
  controls: { display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" as const },
  navBtn: { padding: "0.4rem 0.8rem", backgroundColor: "#2c3e50", color: "white", border: "none", borderRadius: "6px", cursor: "pointer", fontSize: "1rem" },
  todayBtn: { padding: "0.4rem 0.8rem", backgroundColor: "#7f8c8d", color: "white", border: "none", borderRadius: "6px", cursor: "pointer", fontSize: "0.9rem" },
  viewToggle: { display: "flex", borderRadius: "6px", overflow: "hidden", border: "1px solid #2c3e50" },
  toggleBtn: { padding: "0.4rem 1rem", backgroundColor: "white", color: "#2c3e50", border: "none", cursor: "pointer", fontSize: "0.9rem" },
  activeToggle: { padding: "0.4rem 1rem", backgroundColor: "#2c3e50", color: "white", border: "none", cursor: "pointer", fontSize: "0.9rem" },
  addEventBtn: { padding: "0.4rem 1rem", backgroundColor: "#27ae60", color: "white", border: "none", borderRadius: "6px", cursor: "pointer", fontSize: "0.9rem", fontWeight: 600 },
  overlay: { position: "fixed", top: 0, left: 0, right: 0, bottom: 0, backgroundColor: "rgba(0,0,0,0.4)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 },
  modal: { backgroundColor: "white", borderRadius: "12px", padding: "2rem", width: "100%", maxWidth: "420px", boxShadow: "0 20px 60px rgba(0,0,0,0.2)" },
  eventColorBar: { height: "6px", borderRadius: "3px", marginBottom: "1rem" },
  modalTitle: { margin: "0 0 1.25rem 0", fontSize: "1.3rem", fontWeight: 700 },
  label: { display: "block", fontSize: "0.85rem", fontWeight: 600, marginBottom: "0.35rem", color: "#444" },
  input: { width: "100%", padding: "0.6rem 0.75rem", borderRadius: "6px", border: "1px solid #ddd", fontSize: "0.95rem", marginBottom: "1rem", boxSizing: "border-box" as const, fontFamily: "inherit" },
  row: { display: "flex", gap: "1rem" },
  colorRow: { display: "flex", gap: "0.5rem", marginBottom: "1.5rem", marginTop: "0.35rem" },
  colorDot: { width: "28px", height: "28px", borderRadius: "50%", cursor: "pointer" },
  modalActions: { display: "flex", justifyContent: "flex-end", gap: "0.75rem", marginTop: "1rem" },
  cancelBtn: { padding: "0.6rem 1.2rem", backgroundColor: "#ecf0f1", color: "#333", border: "none", borderRadius: "6px", cursor: "pointer", fontSize: "0.9rem" },
  addBtn: { padding: "0.6rem 1.2rem", backgroundColor: "#27ae60", color: "white", border: "none", borderRadius: "6px", cursor: "pointer", fontSize: "0.9rem", fontWeight: 600 },
  deleteBtn: { padding: "0.6rem 1.2rem", backgroundColor: "#e74c3c", color: "white", border: "none", borderRadius: "6px", cursor: "pointer", fontSize: "0.9rem", fontWeight: 600 },
  detailRow: { display: "flex", justifyContent: "space-between", alignItems: "center", padding: "0.6rem 0", borderBottom: "1px solid #f0f0f0" },
  detailLabel: { fontSize: "0.9rem", color: "#666" },
  detailValue: { fontSize: "0.9rem", fontWeight: 600, color: "#1a1a2e" },
};