import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";

export default function Login() {
  const { setToken } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleLogin() {
    if (!email || !password) {
      setError("Please enter your email and password.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const res = await fetch("http://127.0.0.1:8000/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) {
        setError("Invalid email or password.");
        return;
      }
      const data = await res.json();
      setToken(data.access_token);
      navigate("/");
    } catch {
      setError("Could not connect to server.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ maxWidth: "400px", margin: "4rem auto", padding: "2rem", backgroundColor: "white", borderRadius: "8px", boxShadow: "0 2px 12px rgba(0,0,0,0.1)" }}>
      <h1 style={{ marginTop: 0 }}>Login</h1>
      {error && <p style={{ color: "#e74c3c", fontSize: "0.9rem" }}>{error}</p>}
      <input
        placeholder="Email"
        value={email}
        onChange={e => setEmail(e.target.value)}
        style={{ display: "block", width: "100%", marginBottom: "1rem", padding: "0.6rem", borderRadius: "6px", border: "1px solid #ddd", boxSizing: "border-box" as const }}
      />
      <input
        type="password"
        placeholder="Password"
        value={password}
        onChange={e => setPassword(e.target.value)}
        onKeyDown={e => e.key === "Enter" && handleLogin()}
        style={{ display: "block", width: "100%", marginBottom: "1rem", padding: "0.6rem", borderRadius: "6px", border: "1px solid #ddd", boxSizing: "border-box" as const }}
      />
      <button
        type="button"
        onClick={handleLogin}
        disabled={loading}
        style={{ width: "100%", padding: "0.75rem", backgroundColor: "#2c3e50", color: "white", border: "none", borderRadius: "6px", cursor: "pointer", fontSize: "1rem" }}
      >
        {loading ? "Logging in..." : "Login"}
      </button>
      <p style={{ textAlign: "center", marginTop: "1rem" }}>
        Don't have an account? <Link to="/signup">Sign Up</Link>
      </p>
    </div>
  );
}