import { Link, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "./auth";
import "./styles/app.css";

function AppLayout() {
  const { username, isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate("/login");
  }

  return (
    <div className="app-shell">
      {isAuthenticated && (
        <header className="app-header no-print">
          <h1>CPL-2 Scheduling</h1>
          <nav className="app-nav">
            <Link to="/">Dashboard</Link>
            <Link to="/history">History</Link>
            <span style={{ color: "var(--muted)", fontSize: "0.875rem" }}>{username}</span>
            <button className="btn btn-secondary" onClick={handleLogout}>Logout</button>
          </nav>
        </header>
      )}
      <main className="app-main">
        <Outlet />
      </main>
    </div>
  );
}

export default AppLayout;
