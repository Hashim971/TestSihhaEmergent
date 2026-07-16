import React from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import {
  Leaf, MessageSquare, ScanLine, Pill, Activity, Users, Stethoscope, ArrowRight,
} from "lucide-react";

const features = [
  { icon: MessageSquare, title: "AI Health Screening", desc: "A conversational symptom checker that asks the right questions, one at a time, and produces a professional screening report for your doctor." },
  { icon: ScanLine, title: "Pill Identification", desc: "Photograph any medication and our vision AI identifies it — uses, dosage, side effects and safety warnings in seconds." },
  { icon: Pill, title: "Medication Adherence", desc: "Schedules, dose confirmations, missed-dose alerts and adherence reports shared with your care team." },
  { icon: Activity, title: "Real-Time Vitals", desc: "Track heart rate, blood pressure, glucose, SpO₂ and temperature with automatic out-of-range alerts." },
  { icon: Users, title: "Family Profiles", desc: "Manage dependents' health records, medications and screenings from a single account." },
  { icon: Stethoscope, title: "Doctor Portal", desc: "Providers see shared patient vitals, adherence and AI screening reports in one connected view." },
];

export default function Landing() {
  const { user, loading } = useAuth();
  const navigate = useNavigate();
  if (!loading && user) return <Navigate to="/dashboard" replace />;
  const handleLogin = () => navigate("/auth");

  return (
    <div className="min-h-screen bg-sand">
      <header className="bg-white/90 backdrop-blur-md border-b border-line sticky top-0 z-20">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="h-9 w-9 rounded-full bg-forest flex items-center justify-center">
              <Leaf className="h-5 w-5 text-sage" />
            </div>
            <span className="font-heading font-bold text-xl text-forest">Sihha AI</span>
          </div>
          <button onClick={handleLogin} data-testid="login-btn" className="btn-primary">
            Sign In
          </button>
        </div>
      </header>

      <section className="max-w-6xl mx-auto px-6 pt-20 pb-16 grid grid-cols-1 md:grid-cols-12 gap-8 items-center">
        <div className="md:col-span-7 fade-up">
          <p className="text-xs uppercase tracking-[0.2em] text-forest font-semibold mb-4">
            Patent-pending multimodal healthcare intelligence
          </p>
          <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold tracking-tight leading-none text-ink">
            Your health, understood in <span className="text-forest">real time.</span>
          </h1>
          <p className="mt-6 text-lg text-ink-soft leading-relaxed max-w-xl">
            Sihha AI unifies visual, textual and biometric data — identifying medications from a photo,
            screening symptoms like a clinician, and watching your vitals around the clock.
          </p>
          <div className="mt-8 flex gap-3">
            <button onClick={handleLogin} data-testid="hero-cta-btn" className="btn-primary text-base px-8 py-3">
              Get Started <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        </div>
        <div className="md:col-span-5 fade-up" style={{ animationDelay: "0.15s" }}>
          <img
            src="https://images.unsplash.com/photo-1666886573531-48d2e3c2b684?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NTYxOTJ8MHwxfHNlYXJjaHwzfHxtb2Rlcm4lMjBoZWFsdGhjYXJlJTIwcGF0aWVudCUyMGRvY3RvcnxlbnwwfHx8fDE3ODQyMzQyNzZ8MA&ixlib=rb-4.1.0&q=85"
            alt="Doctor with patient using Sihha AI"
            className="rounded-xl border border-line shadow-sm w-full object-cover aspect-[4/5]"
          />
        </div>
      </section>

      <section className="max-w-6xl mx-auto px-6 pb-24">
        <h2 className="text-2xl md:text-3xl font-bold tracking-tight text-ink mb-10">
          Everything from the patent, built in.
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map(({ icon: Icon, title, desc }, i) => (
            <div key={title} className="card p-8 fade-up" style={{ animationDelay: `${i * 0.08}s` }}>
              <div className="h-11 w-11 rounded-full bg-sage/40 flex items-center justify-center mb-5">
                <Icon className="h-5 w-5 text-forest" />
              </div>
              <h3 className="text-xl font-semibold text-ink">{title}</h3>
              <p className="mt-2 text-sm text-ink-soft leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>
      </section>

      <footer className="border-t border-line bg-white py-8">
        <div className="max-w-6xl mx-auto px-6 text-sm text-ink-soft flex flex-col md:flex-row justify-between gap-2">
          <span>© 2026 Sihha AI — Real-Time Healthcare Management Using Multimodal Data Integration.</span>
          <span>Not a substitute for professional medical advice.</span>
        </div>
      </footer>
    </div>
  );
}
