import React from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "sonner";
import { AuthProvider } from "./context/AuthContext";
import Landing from "./pages/Landing";
import Auth from "./pages/Auth";
import Onboarding from "./pages/Onboarding";
import ProtectedRoute from "./components/ProtectedRoute";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import HealthChat from "./pages/HealthChat";
import PillIdentify from "./pages/PillIdentify";
import Medications from "./pages/Medications";
import Dependents from "./pages/Dependents";
import DoctorPortal from "./pages/DoctorPortal";

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/auth" element={<Auth />} />
          <Route path="/onboarding" element={<Onboarding />} />
          <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/chat" element={<HealthChat />} />
            <Route path="/pill-id" element={<PillIdentify />} />
            <Route path="/medications" element={<Medications />} />
            <Route path="/dependents" element={<Dependents />} />
            <Route path="/doctor" element={<DoctorPortal />} />
          </Route>
        </Routes>
        <Toaster position="top-right" richColors />
      </AuthProvider>
    </BrowserRouter>
  );
}
