import type { CalendarEvent } from "./PersonalCalendar";

interface Props {
  currentDate: Date;
  events: CalendarEvent[];
  onEventClick: (event: CalendarEvent) => void;
}

const HOURS = Array.from({ length: 16 }, (_, i) => i + 7);

export default function WeekView({ currentDate, events, onEventClick }: Props) {
  const startOfWeek = new Date(currentDate);
  startOfWeek.setDate(currentDate.getDate() - currentDate.getDay());

  const days = Array.from({ length: 7 }, (_, i) => {
    const d = new Date(startOfWeek);
    d.setDate(startOfWeek.getDate() + i);
    return d;
  });

  const today = new Date();

  function dateStr(d: Date) {
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  }

  function isToday(d: Date) {
    return (
      d.getFullYear() === today.getFullYear() &&
      d.getMonth() === today.getMonth() &&
      d.getDate() === today.getDate()
    );
  }

  function eventsForSlot(d: Date, hour: number) {
    return events.filter(e => {
      if (e.date !== dateStr(d)) return false;
      const startTotal = e.startHour * 60 + e.startMinute;
      const endTotal = e.endHour * 60 + e.endMinute;
      const slotStart = hour * 60;
      const slotEnd = slotStart + 60;
      return startTotal < slotEnd && endTotal > slotStart;
    });
  }

  function formatTime(hour: number, minute: number) {
    const h = hour % 12 === 0 ? 12 : hour % 12;
    const m = String(minute).padStart(2, "0");
    return `${h}:${m}${hour < 12 ? "am" : "pm"}`;
  }

  const weekRange = `${days[0].toLocaleDateString("default", { month: "short", day: "numeric" })} – ${days[6].toLocaleDateString("default", { month: "short", day: "numeric", year: "numeric" })}`;

  return (
    <div style={{ backgroundColor: "white", borderRadius: "12px", boxShadow: "0 2px 12px rgba(0,0,0,0.08)", overflow: "hidden" }}>
      <div style={styles.weekTitle}>{weekRange}</div>
      <div style={{ overflowX: "auto" }}>
        <div style={{ minWidth: "700px" }}>
          <div style={styles.headerRow}>
            <div style={styles.timeGutter}></div>
            {days.map((d, i) => (
              <div key={i} style={{ ...styles.dayHeader, ...(isToday(d) ? styles.todayHeader : {}) }}>
                <div style={styles.dayName}>{["Sun","Mon","Tue","Wed","Thu","Fri","Sat"][i]}</div>
                <div style={{ ...styles.dayNum, ...(isToday(d) ? styles.todayNum : {}) }}>{d.getDate()}</div>
              </div>
            ))}
          </div>

          {HOURS.map(hour => (
            <div key={hour} style={styles.hourRow}>
              <div style={styles.timeLabel}>
                {hour === 12 ? "12pm" : hour < 12 ? `${hour}am` : `${hour - 12}pm`}
              </div>
              {days.map((d, i) => {
                const slotEvents = eventsForSlot(d, hour);
                return (
                  <div key={i} style={{ ...styles.slot, ...(isToday(d) ? styles.todaySlot : {}) }}>
                    {slotEvents.map(ev => {
                      if (ev.startHour !== hour) return null;
                      const durationMins = (ev.endHour * 60 + ev.endMinute) - (ev.startHour * 60 + ev.startMinute);
                      const heightPx = Math.max((durationMins / 60) * 44, 22);
                      return (
                        <div
                          key={ev.id}
                          onClick={() => onEventClick(ev)}
                          style={{
                            ...styles.eventBlock,
                            backgroundColor: ev.color || "#3498db",
                            height: `${heightPx}px`,
                          }}
                          title={ev.title}
                        >
                          <div style={styles.eventTitle}>{ev.title}</div>
                          <div style={styles.eventTime}>
                            {formatTime(ev.startHour, ev.startMinute)} – {formatTime(ev.endHour, ev.endMinute)}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

const styles: { [key: string]: React.CSSProperties } = {
  weekTitle: {
    textAlign: "center",
    padding: "1rem",
    fontWeight: 700,
    fontSize: "1.05rem",
    backgroundColor: "#2c3e50",
    color: "white",
    letterSpacing: "0.5px",
  },
  headerRow: { display: "grid", gridTemplateColumns: "60px repeat(7, 1fr)", borderBottom: "2px solid #f0f0f0" },
  timeGutter: { padding: "0.5rem" },
  dayHeader: { textAlign: "center", padding: "0.75rem 0.5rem" },
  todayHeader: { backgroundColor: "#f0f7ff" },
  dayName: {
    fontSize: "0.75rem",
    fontWeight: 600,
    color: "#888",
    textTransform: "uppercase" as const,
    letterSpacing: "0.5px",
  },
  dayNum: { fontSize: "1.1rem", fontWeight: 600, color: "#333", marginTop: "2px" },
  todayNum: {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    width: "30px",
    height: "30px",
    backgroundColor: "#2c3e50",
    color: "white",
    borderRadius: "50%",
  },
  hourRow: { display: "grid", gridTemplateColumns: "60px repeat(7, 1fr)", borderBottom: "1px solid #f5f5f5" },
  timeLabel: { fontSize: "0.72rem", color: "#aaa", padding: "0.4rem 0.5rem", textAlign: "right", fontWeight: 500 },
  slot: {
    height: "44px",
    borderLeft: "1px solid #f5f5f5",
    padding: "2px",
    position: "relative" as const,
    overflow: "visible" as const,
  },
  todaySlot: { backgroundColor: "#fafeff" },
  eventBlock: {
    position: "absolute" as const,
    left: "2px",
    right: "2px",
    borderRadius: "4px",
    padding: "2px 6px",
    cursor: "pointer",
    zIndex: 10,
    overflow: "hidden",
  },
  eventTitle: {
    fontSize: "0.75rem",
    color: "white",
    fontWeight: 600,
    whiteSpace: "nowrap" as const,
    overflow: "hidden",
    textOverflow: "ellipsis",
  },
  eventTime: { fontSize: "0.68rem", color: "rgba(255,255,255,0.85)" },
};