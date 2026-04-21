import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function Navbar() {
  const { logout, user } = useAuth();
  const navigate = useNavigate();

  async function handleLogout() {
    await logout();
    navigate("/login");
  }

  return (
    <nav style={styles.nav}>
      <div style={styles.brand}>
        <h2>AI Scheduler</h2>
        {user ? <small style={styles.userLabel}>{user.first_name} {user.last_name}</small> : null}
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
  brand: { marginRight: "2rem" },
  userLabel: {
    display: "block",
    marginTop: "0.2rem",
    fontSize: "0.75rem",
    opacity: 0.8,
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
