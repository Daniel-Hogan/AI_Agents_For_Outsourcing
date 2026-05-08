import { Outlet } from "react-router-dom";
import Navbar from "../components/Navbar";

export default function AppLayout() {
  return (
    <div style={{ minHeight: "100vh", backgroundColor: "#ecf0f1" }}>
      <Navbar />
      <main style={{ padding: "2rem", maxWidth: "1200px", margin: "0 auto" }}>
        <Outlet />
      </main>
    </div>
  );
}