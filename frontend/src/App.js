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
import VisitSummaries from "./pages/VisitSummaries";
import BookVisit from "./pages/BookVisit";
import Prescriptions from "./pages/Prescriptions";
import Pharmacy from "./pages/Pharmacy";
import PharmacyOrders from "./pages/PharmacyOrders";
import DoctorPortal from "./pages/DoctorPortal";
import DoctorDashboard from "./pages/DoctorDashboard";
import DoctorSchedule from "./pages/DoctorSchedule";
import AdminAssignments from "./pages/AdminAssignments";
import Intake from "./pages/Intake";
import EncounterDetail from "./pages/EncounterDetail";
import Settings from "./pages/Settings";

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/auth" element={<Auth />} />
          <Route path="/auth/clinician" element={<Auth portal="doctor" />} />
          <Route path="/onboarding" element={<Onboarding />} />
          <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/chat" element={<HealthChat />} />
            <Route path="/pill-id" element={<PillIdentify />} />
            <Route path="/medications" element={<Medications />} />
            <Route path="/dependents" element={<Dependents />} />
            <Route path="/visits" element={<VisitSummaries />} />
            <Route path="/book" element={<BookVisit />} />
            <Route path="/prescriptions" element={<Prescriptions />} />
            <Route path="/pharmacy" element={<Pharmacy />} />
            <Route path="/pharmacy/orders" element={<PharmacyOrders />} />
            <Route path="/doctor" element={<DoctorDashboard />} />
            <Route path="/doctor/patients" element={<DoctorPortal />} />
            <Route path="/doctor/schedule" element={<DoctorSchedule />} />
            <Route path="/admin/assignments" element={<AdminAssignments />} />
            <Route path="/intake/:encounterId" element={<Intake />} />
            <Route path="/doctor/encounters/:id" element={<EncounterDetail />} />
            <Route path="/settings" element={<Settings />} />
          </Route>
        </Routes>
        <Toaster position="top-right" richColors />
      </AuthProvider>
    </BrowserRouter>
  );
}
