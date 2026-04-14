import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { handleAuthCallback } from "../contexts/AuthContext";

export function AuthCallbackPage() {
  const navigate = useNavigate();

  useEffect(() => {
    const token = handleAuthCallback();
    if (token) {
      // Small delay to ensure localStorage write is flushed before navigation.
      // Without this there's an occasional race where the new page loads
      // before the token is committed, and AuthContext thinks we're logged out.
      setTimeout(() => {
        window.location.href = "/";
      }, 100);
    } else {
      navigate("/login");
    }
  }, [navigate]);

  return (
    <div className="flex items-center justify-center h-screen">
      <div className="text-page-text-secondary">Signing in...</div>
    </div>
  );
}
