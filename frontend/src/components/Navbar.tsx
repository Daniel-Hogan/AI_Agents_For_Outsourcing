import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const AVATAR_COLORS: Record<string, string> = {
  blue: "#3b82f6",
  purple: "#a855f7",
  green: "#22c55e",
  orange: "#f97316",
  pink: "#ec4899",
  teal: "#14b8a6",
  red: "#ef4444",
  yellow: "#eab308",
};

function getInitials(firstName: string, lastName: string) {
  return `${firstName.charAt(0)}${lastName.charAt(0)}`.toUpperCase();
}

export default function Navbar() {
  const { logout, user } = useAuth();
  const navigate = useNavigate();
  const avatarColorId = user?.avatar_color ?? localStorage.getItem("avatar_color_id") ?? "blue";
  const avatarColor = AVATAR_COLORS[avatarColorId] ?? AVATAR_COLORS.blue;

  async function handleLogout() {
    await logout();
    navigate("/login");
  }

  return (
    <nav style={styles.nav}>
      <div style={styles.brand}>
        <h2 style={{ margin: 0 }}>Scheduler AI</h2>
        {user ? (
          <button type="button" onClick={() => navigate("/settings")} style={styles.userButton}>
            <div style={{ ...styles.avatar, backgroundColor: avatarColor }}>
              {getInitials(user.first_name, user.last_name)}
            </div>
            <span style={styles.userLabel}>
              {user.first_name} {user.last_name}
            </span>
          </button>
        ) : null}
      </div>
      <div style={styles.links}>
        <Link to="/" style={styles.link}>Dashboard</Link>
        <Link to="/groups" style={styles.link}>Groups</Link>
        <Link to="/calendar" style={styles.link}>Calendar</Link>
        <Link to="/meetings" style={styles.link}>Meetings</Link>
        <Link to="/settings" style={styles.link}>Settings</Link>
      </div>
      <button type="button" style={styles.logoutBtn} onClick={handleLogout}>
        Logout
      </button>
    </nav>
  );
}

const styles: { [key: string]: React.CSSProperties } = {
  nav: {
    display: "flex",
    alignItems: "center",
    padding: "1rem 2rem",
    backgroundColor: "#2c3e50",
    color: "white",
  },
  brand: {
    marginRight: "2rem",
    display: "flex",
    flexDirection: "column",
    gap: "0.5rem",
  },
  userButton: {
    display: "flex",
    alignItems: "center",
    gap: "0.5rem",
    background: "none",
    border: "none",
    color: "white",
    cursor: "pointer",
    padding: 0,
  },
  avatar: {
    width: "28px",
    height: "28px",
    borderRadius: "50%",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: "0.7rem",
    fontWeight: 700,
    color: "white",
    flexShrink: 0,
  },
  userLabel: {
    fontSize: "0.75rem",
    opacity: 0.85,
    textDecoration: "underline",
    textUnderlineOffset: "2px",
  },
  links: { display: "flex", gap: "1.5rem", flex: 1 },
  link: { color: "white", textDecoration: "none", padding: "0.5rem 1rem" },
  logoutBtn: {
    padding: "0.5rem 1rem",
    backgroundColor: "#e74c3c",
    color: "white",
    border: "none",
    borderRadius: "4px",
    cursor: "pointer",
  },
};
