import React, { useEffect, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { BrandMark } from "../components/BrandMark";
import {
  ArrowRight, Stethoscope, Mic, ScanLine, Pill, ShieldCheck, Building2, Languages, Siren, ShoppingBag,
  FileHeart, Users, CheckCircle2, Smartphone, Palette, Globe, UploadCloud, ToggleRight, Lock, UserCheck,
} from "lucide-react";
import { DemoForm } from "../components/landing/DemoForm";
import { AudienceTabs } from "../components/landing/AudienceTabs";
import { ScribeProof } from "../components/landing/ScribeProof";
import { WhiteLabelPreview } from "../components/landing/WhiteLabelPreview";
import { LanguageToggle } from "../components/LanguageToggle";

const DOCTOR_IMG = "https://images.unsplash.com/photo-1758691463000-08b98131daf3?crop=entropy&cs=srgb&fm=jpg&q=80&w=1400";

const capabilities = [
  { icon: Siren, title: "Safety-first triage", desc: "Hard red-flag rules set an urgency floor the AI can raise but never lower. Emergencies are routed to 997, not a booking form." },
  { icon: Mic, title: "Live Arabic scribe", desc: "Consultations are transcribed as the doctor speaks and drafted into a SOAP note the clinician reviews and signs." },
  { icon: ScanLine, title: "Pill identification", desc: "A photo returns the likely medicine, its uses, dose and warnings, and adds it to the patient's list in one tap." },
  { icon: Pill, title: "Refill intelligence", desc: "Deterministic runout forecasts from real doses taken. Refills are proposed, never silently substituted." },
  { icon: ShoppingBag, title: "Pharmacy marketplace", desc: "Patients find partner pharmacies that stock their medicine. Pharmacists verify every prescription." },
  { icon: FileHeart, title: "Visit summaries", desc: "Plain-language notes in Arabic and English, with the warning signs to watch for, sent only after the doctor reviews them." },
];

const safeguards = [
  "Doctors review and sign every AI-drafted note and summary",
  "Controlled medicines can never be ordered through the app",
  "Only the dispensing pharmacist verifies a prescription",
  "Patient data is scoped per profile and shared only with consent",
  "Separate staging environment for testing — production stays untouched",
  "Brute-force and account-enumeration protection on every sign-in",
];

const steps = [
  { icon: Building2, title: "Create the account", desc: "Each hospital gets a unique ID and its own staff and patient space." },
  { icon: Palette, title: "Brand it", desc: "Logo, name, colours and default language — previewed live." },
  { icon: ToggleRight, title: "Pick the modules", desc: "Switch features on or off per hospital, no code changes." },
  { icon: UploadCloud, title: "Bring the data", desc: "Import existing patients and history, invite doctors by email." },
  { icon: Globe, title: "Go live on their address", desc: "care.yourhospital.sa — one DNS record and it's theirs." },
];

export default function Landing() {
  const { user, loading } = useAuth();
  const navigate = useNavigate();
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 12);
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);
  if (!loading && user) return <Navigate to={user.role === "doctor" ? "/doctor" : "/dashboard"} replace />;

  return (
    <div className="min-h-screen bg-sand text-ink overflow-x-hidden" data-testid="landing-page">
      <header className={`sticky z-30 border-b ${scrolled ? "bg-white/85 backdrop-blur-xl border-line" : "bg-transparent border-transparent"}`}
        style={{ top: "var(--env-bar, 0px)", transition: "background-color 0.3s ease, border-color 0.3s ease" }}>
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center gap-6">
          <span className="shrink-0"><BrandMark testid="landing-brand" /></span>
          <nav className="hidden lg:flex items-center gap-7 text-sm text-ink-soft ml-6">
            {[["#platform", "Platform"], ["#scribe", "AI scribe"], ["#hospitals", "For hospitals"], ["#safety", "Safety"]].map(([href, label]) => (
              <a key={href} href={href} className="hover:text-forest" data-testid={`landing-nav-${href.slice(1)}`} style={{ transition: "color 0.2s ease" }}>{label}</a>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <LanguageToggle testid="landing-language-toggle" />
            <button onClick={() => navigate("/auth/clinician")} data-testid="clinician-login-btn" className="btn-outline hidden sm:inline-flex">
              <Stethoscope className="h-4 w-4" /> Clinicians
            </button>
            <button onClick={() => navigate("/auth")} data-testid="login-btn" className="btn-primary whitespace-nowrap !px-4 sm:!px-6">
              <span className="sm:hidden">Sign in</span><span className="hidden sm:inline">Patient sign in</span>
            </button>
          </div>
        </div>
      </header>

      <section className="relative max-w-7xl mx-auto px-6 pt-16 lg:pt-24 pb-20 grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
        <div className="lg:col-span-6 fade-up">
          <p className="inline-flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-forest font-semibold mb-6 border border-forest/20 rounded-full px-3 py-1.5 bg-white">
            <span className="h-1.5 w-1.5 rounded-full bg-terracotta" /> Patent-pending · Arabic-first
          </p>
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight leading-[1.02]">
            The AI care platform built for <span className="text-forest">Saudi healthcare.</span>
          </h1>
          <p className="mt-7 text-base sm:text-lg text-ink-soft leading-relaxed max-w-xl">
            One connected system for patients, doctors, pharmacies and hospitals — AI screening and triage, a live Arabic clinical scribe,
            prescriptions and refills, delivered under each hospital's own brand.
          </p>
          <div className="mt-9 flex flex-wrap gap-3">
            <a href="#demo" data-testid="hero-demo-btn" className="btn-primary text-base px-7 py-3">Book a hospital demo <ArrowRight className="h-4 w-4" /></a>
            <button onClick={() => navigate("/auth")} data-testid="hero-cta-btn" className="btn-outline text-base px-7 py-3">Try the patient app</button>
          </div>
          <div className="mt-10 flex flex-wrap gap-x-6 gap-y-3 text-sm text-ink-soft" data-testid="hero-proof-points">
            {[[Languages, "Arabic & English"], [UserCheck, "Doctor-in-the-loop AI"], [Lock, "Consent-based sharing"]].map(([Icon, label]) => (
              <span key={label} className="inline-flex items-center gap-2"><Icon className="h-4 w-4 text-forest" /> {label}</span>
            ))}
          </div>
        </div>
        <div className="lg:col-span-6 relative fade-up" style={{ animationDelay: "0.15s" }}>
          <div className="relative rounded-[28px] overflow-hidden aspect-[4/5] sm:aspect-[5/4] lg:aspect-[4/5] shadow-2xl">
            <img src={DOCTOR_IMG} alt="A doctor consulting with a patient using a tablet" className="absolute inset-0 h-full w-full object-cover" />
            <div className="absolute inset-0 bg-gradient-to-t from-black/50 via-black/0 to-black/0" />
          </div>
          <div className="absolute -left-4 sm:-left-10 bottom-8 w-[78%] sm:w-80 bg-white/95 backdrop-blur-xl rounded-2xl border border-line shadow-xl p-4" data-testid="hero-scribe-card">
            <p className="text-[10px] uppercase tracking-[0.15em] text-ink-soft font-semibold flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-terracotta animate-pulse" /> Live transcript
            </p>
            <p dir="rtl" className="mt-2 text-sm leading-relaxed">عندي ألم في الصدر منذ يومين ويزيد مع المشي</p>
            <div className="mt-3 pt-3 border-t border-line text-xs text-ink-soft"><b className="text-forest">Assessment:</b> exertional chest pain — urgent review advised</div>
          </div>
          <div className="absolute -right-2 sm:-right-6 top-8 bg-forest text-white rounded-2xl shadow-xl px-4 py-3" data-testid="hero-triage-card">
            <p className="text-[10px] uppercase tracking-[0.15em] text-sage font-semibold">Triage</p>
            <p className="text-sm font-semibold mt-0.5">Urgent · within 24h</p>
          </div>
        </div>
      </section>

      <section id="platform" className="max-w-7xl mx-auto px-6 py-20">
        <p className="text-xs uppercase tracking-[0.2em] text-forest font-semibold">One platform, three sides of care</p>
        <h2 className="text-3xl sm:text-4xl font-bold tracking-tight mt-3 max-w-2xl">Patients, clinicians and hospitals on the same record.</h2>
        <AudienceTabs />
      </section>

      <section id="scribe" className="bg-forest text-white">
        <ScribeProof />
      </section>

      <section className="max-w-7xl mx-auto px-6 py-24">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-px bg-line rounded-3xl overflow-hidden border border-line" data-testid="capabilities-grid">
          {capabilities.map(({ icon: Icon, title, desc }, i) => (
            <div key={title} className="bg-white p-8 group hover:bg-sand" style={{ transition: "background-color 0.25s ease" }} data-testid={`capability-${i}`}>
              <span className="h-11 w-11 rounded-xl bg-sage/30 text-forest flex items-center justify-center group-hover:bg-forest group-hover:text-white" style={{ transition: "background-color 0.25s ease, color 0.25s ease" }}>
                <Icon className="h-5 w-5" />
              </span>
              <h3 className="text-lg font-semibold mt-5">{title}</h3>
              <p className="text-sm text-ink-soft mt-2 leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>
      </section>

      <section id="hospitals" className="bg-white border-y border-line">
        <div className="max-w-7xl mx-auto px-6 py-24 grid grid-cols-1 lg:grid-cols-12 gap-12 items-start">
          <div className="lg:col-span-5">
            <p className="text-xs uppercase tracking-[0.2em] text-forest font-semibold">White-label, plug and play</p>
            <h2 className="text-3xl sm:text-4xl font-bold tracking-tight mt-3">Their brand. Our intelligence.</h2>
            <p className="text-ink-soft mt-5 leading-relaxed">Hospitals launch Sihha under their own name, colours and web address — with only the modules they want — and manage every doctor and patient from one console.</p>
            <ol className="mt-10 space-y-6" data-testid="hospital-steps">
              {steps.map(({ icon: Icon, title, desc }, i) => (
                <li key={title} className="flex gap-4">
                  <span className="h-10 w-10 rounded-full border border-line bg-sand flex items-center justify-center shrink-0 text-forest"><Icon className="h-4 w-4" /></span>
                  <span><span className="block font-semibold"><span className="text-ink-soft font-mono text-xs mr-2">0{i + 1}</span>{title}</span><span className="block text-sm text-ink-soft mt-0.5">{desc}</span></span>
                </li>
              ))}
            </ol>
          </div>
          <div className="lg:col-span-7"><WhiteLabelPreview /></div>
        </div>
      </section>

      <section id="safety" className="max-w-7xl mx-auto px-6 py-24 grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-forest font-semibold">Safety by design</p>
          <h2 className="text-3xl sm:text-4xl font-bold tracking-tight mt-3">AI that assists. Clinicians who decide.</h2>
          <p className="text-ink-soft mt-5 leading-relaxed max-w-lg">Every high-stakes step keeps a qualified human in control, and the rules that protect patients are deterministic — not left to a language model.</p>
        </div>
        <ul className="grid grid-cols-1 sm:grid-cols-2 gap-3" data-testid="safety-list">
          {safeguards.map((s) => (
            <li key={s} className="card p-4 flex gap-3 text-sm"><ShieldCheck className="h-5 w-5 text-forest shrink-0" /> {s}</li>
          ))}
        </ul>
      </section>

      <section className="max-w-7xl mx-auto px-6 pb-24">
        <div className="rounded-3xl bg-ink text-white p-8 sm:p-12 grid grid-cols-1 md:grid-cols-2 gap-8 items-center" data-testid="landing-install-section">
          <div>
            <Smartphone className="h-8 w-8 text-sage" />
            <h2 className="text-2xl sm:text-3xl font-bold tracking-tight mt-4">On every phone, today.</h2>
            <p className="text-white/70 mt-3 max-w-md">Install Sihha from the browser on iPhone or Android and it opens full-screen like a native app. App Store and Google Play listings are next.</p>
          </div>
          <ul className="space-y-3 text-sm text-white/80">
            <li className="flex gap-3"><CheckCircle2 className="h-5 w-5 text-sage shrink-0" /> iPhone: Safari → Share → Add to Home Screen</li>
            <li className="flex gap-3"><CheckCircle2 className="h-5 w-5 text-sage shrink-0" /> Android: Chrome → menu → Install app</li>
            <li className="flex gap-3"><Users className="h-5 w-5 text-sage shrink-0" /> Family profiles, reminders and visits in one place</li>
          </ul>
        </div>
      </section>

      <section id="demo" className="bg-forest text-white">
        <div className="max-w-7xl mx-auto px-6 py-24 grid grid-cols-1 lg:grid-cols-2 gap-12">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-sage font-semibold">For hospitals, clinic groups and partners</p>
            <h2 className="text-3xl sm:text-4xl font-bold tracking-tight mt-3">See Sihha running under your brand.</h2>
            <p className="text-white/70 mt-5 max-w-md leading-relaxed">Tell us about your organisation and we'll set up a branded staging workspace for your team to try — separate from any live patient data.</p>
          </div>
          <DemoForm />
        </div>
      </section>

      <footer className="max-w-7xl mx-auto px-6 py-10 flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between text-sm text-ink-soft">
        <BrandMark testid="footer-brand" />
        <p>Sihha AI provides decision support and does not replace professional medical advice. In an emergency call 997.</p>
        <p>© {new Date().getFullYear()} Sihha AI</p>
      </footer>
    </div>
  );
}
