import React from "react";
import { BrowserRouter, Routes, Route, useLocation } from "react-router-dom";
import { Toaster } from "sonner";
import { AuthProvider } from "./context/AuthContext";
import AuthCallback from "./pages/AuthCallback";
import Landing from "./pages/Landing";
import ProtectedRoute from "./components/ProtectedRoute";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import HealthChat from "./pages/HealthChat";
import PillIdentify from "./pages/PillIdentify";
import Medications from "./pages/Medications";
import Dependents from "./pages/Dependents";
import DoctorPortal from "./pages/DoctorPortal";

function AppRouter() {
  const location = useLocation();
  // Check URL fragment synchronously during render for session_id (prevents race conditions)
  if (location.hash?.includes("session_id=")) {
    return <AuthCallback />;
  }
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/chat" element={<HealthChat />} />
        <Route path="/pill-id" element={<PillIdentify />} />
        <Route path="/medications" element={<Medications />} />
        <Route path="/dependents" element={<Dependents />} />
        <Route path="/doctor" element={<DoctorPortal />} />
      </Route>
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRouter />
        <Toaster position="top-right" richColors />
      </AuthProvider>
    </BrowserRouter>
  );
}
