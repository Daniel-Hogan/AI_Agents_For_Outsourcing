import type { CalendarEvent } from "./PersonalCalendar";

interface Props {
  currentDate: Date;
  events: CalendarEvent[];
  onEventClick: (event: CalendarEvent) => void;
}

const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

export default function MonthView({ currentDate, events, onEventClick }: Props) {
  const year = currentDate.getFullYear();
  const month = currentDate.getMonth();
  const firstDay = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const today = new Date();
  const monthName = currentDate.toLocaleString("default", { month: "long", year: "numeric" });

  function dateStr(day: number) {
    return `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
  }

  function isToday(day: number) {
    return today.getFullYear() === year && today.getMonth() === month && today.getDate() === day;
  }

  function eventsForDay(day: number) {
    return events
      .filter(e => e.date === dateStr(day))
      .sort((a, b) => a.startHour * 60 + a.startMinute - (b.startHour * 60 + b.startMinute));
  }

  function formatTime(hour: number, minute: number) {
    const h = hour % 12 === 0 ? 12 : hour % 12;
    const m = String(minute).padStart(2, "0");
    const ampm = hour < 12 ? "am" : "pm";
    return `${h}:${m}${ampm}`;
  }

  const cells = [];
  for (let i = 0; i < firstDay; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(d);

  return (
    <div style={{ backgroundColor: "white", borderRadius: "12px", boxShadow: "0 2px 12px rgba(0,0,0,0.08)", overflow: "hidden" }}>
      <div style={styles.monthTitle}>{monthName}</div>
      <div style={styles.grid}>
        {DAYS.map(d => (
          <div key={d} style={styles.dayLabel}>{d}</div>
        ))}
        {cells.map((day, i) => {
          const dayEvents = day ? eventsForDay(day) : [];
          return (
            <div key={i} style={{ ...styles.cell, ...(day && isToday(day) ? styles.todayCell : {}) }}>
              {day && (
                <>
                  <span style={isToday(day) ? styles.todayNumber : styles.dayNumber}>{day}</span>
                  <div style={styles.eventList}>
                    {dayEvents.map(ev => (
                      <div
                        key={ev.id}
                        style={{ ...styles.eventChip, backgroundColor: ev.color || "#3498db" }}
                        onClick={() => onEventClick(ev)}
                        title={ev.title}
                      >
                        {formatTime(ev.startHour, ev.startMinute)} {ev.title}
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

const styles: { [key: string]: React.CSSProperties } = {
  monthTitle: {
    textAlign: "center",
    padding: "1rem",
    fontWeight: 700,
    fontSize: "1.05rem",
    backgroundColor: "#2c3e50",
    color: "white",
    letterSpacing: "0.5px",
  },
  grid: { display: "grid", gridTemplateColumns: "repeat(7, 1fr)" },
  dayLabel: {
    textAlign: "center",
    padding: "0.6rem",
    fontWeight: 600,
    fontSize: "0.78rem",
    backgroundColor: "#f8f9fa",
    color: "#666",
    letterSpacing: "0.5px",
    textTransform: "uppercase" as const,
  },
  cell: {
    minHeight: "90px",
    padding: "0.4rem",
    border: "1px solid #f0f0f0",
    verticalAlign: "top",
  },
  todayCell: { backgroundColor: "#f0f7ff", border: "1px solid #3498db" },
  dayNumber: { fontSize: "0.85rem", color: "#555", fontWeight: 500, display: "block", marginBottom: "4px" },
  todayNumber: {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    width: "24px",
    height: "24px",
    backgroundColor: "#2c3e50",
    color: "white",
    borderRadius: "50%",
    fontSize: "0.8rem",
    fontWeight: 700,
    marginBottom: "4px",
  },
  eventList: { display: "flex", flexDirection: "column" as const, gap: "2px" },
  eventChip: {
    fontSize: "0.72rem",
    color: "white",
    borderRadius: "4px",
    padding: "2px 5px",
    whiteSpace: "nowrap" as const,
    overflow: "hidden",
    textOverflow: "ellipsis",
    cursor: "pointer",
    fontWeight: 500,
  },
};