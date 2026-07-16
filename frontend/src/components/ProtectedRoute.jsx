import React from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Activity } from "lucide-react";

export default function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-sand">
        <Activity className="h-8 w-8 text-forest animate-pulse" />
      </div>
    );
  }
  if (!user) return <Navigate to="/" replace />;
  return children;
}
