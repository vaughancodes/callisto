import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { handleAuthCallback } from "../contexts/AuthContext";

export function AuthCallbackPage() {
  const navigate = useNavigate();

  useEffect(() => {
    const token = handleAuthCallback();
    if (token) {
      // Force full page reload so AuthContext picks up the new token
      window.location.href = "/";
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
