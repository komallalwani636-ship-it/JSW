import { useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { msLogin } from "../api/auth";
import { useLogin } from "../api/hooks";
import { useAuth } from "../auth";
import { isMsAuthEnabled, loginWithMicrosoft } from "../msalConfig";

export function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isMsLoading, setIsMsLoading] = useState(false);
  const login = useLogin();
  const { setToken, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const result = await login.mutateAsync({ username, password });
      setToken(result.access_token);
      navigate("/");
    } catch {
      setError("Invalid credentials. Please try again.");
    }
  }

  async function handleMicrosoftLogin() {
    setError(null);
    setIsMsLoading(true);
    try {
      const idToken = await loginWithMicrosoft();
      const result = await msLogin(idToken);
      setToken(result.access_token);
      navigate("/");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Microsoft sign-in failed";
      setError(msg.includes("user_cancelled") ? "Sign-in cancelled." : "Microsoft sign-in failed. Please try again.");
    } finally {
      setIsMsLoading(false);
    }
  }

  return (
    <div className="login-page">
      <form className="login-form" onSubmit={handleSubmit}>
        <h1>CPL-2 Scheduling</h1>
        <p style={{ margin: 0, color: "var(--muted)", fontSize: "0.875rem" }}>
          Sign in to access the scheduling dashboard
        </p>

        {isMsAuthEnabled && (
          <>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={handleMicrosoftLogin}
              disabled={isMsLoading || login.isPending}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "0.5rem",
                marginTop: "1rem",
              }}
            >
              <svg width="18" height="18" viewBox="0 0 21 21">
                <rect x="1" y="1" width="9" height="9" fill="#f25022" />
                <rect x="11" y="1" width="9" height="9" fill="#7fba00" />
                <rect x="1" y="11" width="9" height="9" fill="#00a4ef" />
                <rect x="11" y="11" width="9" height="9" fill="#ffb900" />
              </svg>
              {isMsLoading ? "Connecting to Microsoft…" : "Sign in with Microsoft"}
            </button>
            <div style={{ display: "flex", alignItems: "center", margin: "1rem 0", color: "var(--muted)" }}>
              <hr style={{ flex: 1, borderColor: "var(--border, #333)" }} />
              <span style={{ padding: "0 0.5rem", fontSize: "0.75rem" }}>OR</span>
              <hr style={{ flex: 1, borderColor: "var(--border, #333)" }} />
            </div>
          </>
        )}

        <label>
          Username
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            required
          />
        </label>
        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </label>
        {error && <p className="error-msg">{error}</p>}
        <button className="btn" type="submit" disabled={login.isPending || isMsLoading}>
          {login.isPending ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}

