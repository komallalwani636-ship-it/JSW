import { Navigate, Outlet } from "react-router-dom";
import { isAuthenticated } from "../auth";

export function ProtectedRoute() {
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace />;
  }
  return <Outlet />;
}
