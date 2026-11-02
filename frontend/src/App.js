import React from "react";
import { BrowserRouter, Routes, Route, useLocation, Navigate } from "react-router-dom";
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
import AdminLayout from "./pages/admin/AdminLayout";
import Accounts from "./pages/admin/Accounts";
import AccountWorkspace from "./pages/admin/AccountWorkspace";
import FeatureFlags from "./pages/admin/FeatureFlags";
import MyHospital from "./pages/MyHospital";
import { PlatformProvider } from "./context/PlatformContext";
import { StagingBar } from "./components/StagingBar";
import { FeatureRoute } from "./components/FeatureRoute";
import { LanguageProvider, useLang } from "./context/LanguageContext";
import DemoRequests from "./pages/admin/DemoRequests";
import Intake from "./pages/Intake";
import EncounterDetail from "./pages/EncounterDetail";
import Settings from "./pages/Settings";
import AuthCallback from "./pages/AuthCallback";
import ForgotPassword from "./pages/ForgotPassword";
import ResetPassword from "./pages/ResetPassword";
import { ServiceUnavailable } from "./components/ServiceUnavailable";
import FindCare from "./pages/FindCare";
import PharmacyAuth from "./pages/PharmacyAuth";
import PortalLayout from "./pages/pharmacy-portal/PortalLayout";
import PortalOrders from "./pages/pharmacy-portal/PortalOrders";
import PortalSponsorship from "./pages/pharmacy-portal/PortalSponsorship";
import AdminPharmacies from "./pages/admin/Pharmacies";

export default function App() {
  return (
    <BrowserRouter>
      <PlatformProvider>
        <LanguageProvider>
        <AuthProvider>
          <StagingBar />
          <AppRouter />
          <ServiceUnavailable />
          <LocalizedToaster />
        </AuthProvider>
        </LanguageProvider>
      </PlatformProvider>
    </BrowserRouter>
  );
}

function LocalizedToaster() {
  const { lang } = useLang();
  return <Toaster position={lang === "ar" ? "bottom-left" : "bottom-right"} richColors dir={lang === "ar" ? "rtl" : "ltr"} />;
}

function AppRouter() {
  const location = useLocation();
  // Process a fresh Google session before anything else tries to check /auth/me.
  if (location.hash?.includes("session_id=")) return <AuthCallback />;
  return (
    <>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/auth" element={<Auth />} />
          <Route path="/auth/clinician" element={<Auth portal="doctor" />} />
          <Route path="/auth/pharmacy" element={<PharmacyAuth />} />
          <Route element={<ProtectedRoute><PortalLayout /></ProtectedRoute>}>
            <Route path="/pharmacy-portal" element={<PortalOrders />} />
            <Route path="/pharmacy-portal/sponsorship" element={<PortalSponsorship />} />
          </Route>
          <Route path="/auth/forgot" element={<ForgotPassword />} />
          <Route path="/auth/reset" element={<ResetPassword />} />
          <Route path="/onboarding" element={<Onboarding />} />
          <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/chat" element={<FeatureRoute flag="health_chat"><HealthChat /></FeatureRoute>} />
            <Route path="/pill-id" element={<FeatureRoute flag="pill_id"><PillIdentify /></FeatureRoute>} />
            <Route path="/medications" element={<Medications />} />
            <Route path="/dependents" element={<Dependents />} />
            <Route path="/visits" element={<FeatureRoute flag="visit_summaries"><VisitSummaries /></FeatureRoute>} />
            <Route path="/book" element={<FeatureRoute flag="booking"><BookVisit /></FeatureRoute>} />
            <Route path="/find-care" element={<FeatureRoute flag="booking"><FindCare /></FeatureRoute>} />
            <Route path="/prescriptions" element={<FeatureRoute flag="prescriptions"><Prescriptions /></FeatureRoute>} />
            <Route path="/pharmacy" element={<FeatureRoute flag="pharmacy_marketplace"><Pharmacy /></FeatureRoute>} />
            <Route path="/pharmacy/orders" element={<FeatureRoute flag="pharmacy_marketplace"><PharmacyOrders /></FeatureRoute>} />
            <Route path="/doctor" element={<DoctorDashboard />} />
            <Route path="/doctor/patients" element={<DoctorPortal />} />
            <Route path="/doctor/schedule" element={<DoctorSchedule />} />
            <Route path="/intake/:encounterId" element={<Intake />} />
            <Route path="/doctor/encounters/:id" element={<EncounterDetail />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/my-hospital" element={<MyHospital />} />
          </Route>
          <Route element={<ProtectedRoute><AdminLayout /></ProtectedRoute>}>
            <Route path="/admin" element={<Navigate to="/admin/accounts" replace />} />
            <Route path="/admin/accounts" element={<Accounts />} />
            <Route path="/admin/accounts/:accountId" element={<AccountWorkspace />} />
            <Route path="/admin/flags" element={<FeatureFlags />} />
            <Route path="/admin/demo-requests" element={<DemoRequests />} />
            <Route path="/admin/assignments" element={<AdminAssignments />} />
            <Route path="/admin/pharmacies" element={<AdminPharmacies />} />
          </Route>
        </Routes>
    </>
  );
}
