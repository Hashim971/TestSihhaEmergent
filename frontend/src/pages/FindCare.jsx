import React, { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Building2, MapPin, Search, Stethoscope, CheckCircle2, ArrowRight, Award } from "lucide-react";
import { api } from "../lib/api";
import { Stars } from "../components/RecentVisits";
import { HospitalReviews } from "../components/HospitalReviews";

export default function FindCare() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [hospitals, setHospitals] = useState(null);
  const [reviewing, setReviewing] = useState(null);
  const [filters, setFilters] = useState({ q: "", city: "", specialty: "" });
  const reportId = params.get("report");
  const suggested = params.get("specialty");

  const load = (f) => {
    setHospitals(null);
    api.get("/care/hospitals", { params: { q: f.q || undefined, city: f.city || undefined, specialty: f.specialty || undefined } })
      .then(({ data }) => setHospitals(data)).catch(() => setHospitals([]));
  };
  useEffect(() => { load(filters); /* eslint-disable-next-line */ }, []);

  const open = (h) => {
    const next = new URLSearchParams({ hospital: h.account_id, hospital_name: h.name });
    ["report", "reason"].forEach((k) => params.get(k) && next.set(k, params.get(k)));
    navigate(`/book?${next.toString()}`);
  };

  const input = "border border-line rounded-lg px-3 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-forest";

  return (
    <div className="space-y-6 fade-up max-w-5xl" data-testid="find-care-page">
      <div>
        <p className="text-[10px] uppercase tracking-[0.2em] text-terracotta font-semibold">Find care</p>
        <h1 className="text-3xl sm:text-4xl font-bold tracking-tight mt-1">Choose a hospital, then a doctor</h1>
        <p className="text-ink-soft mt-2 max-w-2xl">
          {reportId
            ? "Your screening is ready. Pick where you'd like to be seen — you decide whether to share your record when you book."
            : "Sihha works on its own for your medications and screenings. When you want to see someone, pick a hospital here."}
        </p>
        {suggested && (
          <p className="mt-3 inline-flex items-center gap-2 text-sm bg-sage/20 text-forest rounded-full px-3 py-1" data-testid="find-care-suggested-specialty">
            <Stethoscope className="h-3.5 w-3.5" /> Your screening suggests: <bdi className="font-semibold">{suggested}</bdi>
          </p>
        )}
      </div>

      <form onSubmit={(e) => { e.preventDefault(); load(filters); }} className="card p-4 grid grid-cols-1 md:grid-cols-4 gap-3">
        <input value={filters.q} onChange={(e) => setFilters({ ...filters, q: e.target.value })} placeholder="Hospital name" className={input} data-testid="find-care-name-input" />
        <input value={filters.city} onChange={(e) => setFilters({ ...filters, city: e.target.value })} placeholder="City (e.g. Riyadh)" className={input} data-testid="find-care-city-input" />
        <input value={filters.specialty} onChange={(e) => setFilters({ ...filters, specialty: e.target.value })} placeholder="Specialty (e.g. Cardiology)" className={input} data-testid="find-care-specialty-input" />
        <button type="submit" className="btn-primary justify-center" data-testid="find-care-search-btn"><Search className="h-4 w-4" /> Search</button>
      </form>

      {hospitals === null && <div className="card p-6 text-sm text-ink-soft" data-testid="find-care-loading">Finding hospitals…</div>}
      {hospitals?.length === 0 && (
        <div className="card p-10 text-center" data-testid="find-care-empty">
          <Building2 className="h-7 w-7 text-forest mx-auto" />
          <p className="mt-3 font-semibold">No hospital matches that search</p>
          <p className="text-sm text-ink-soft mt-1">Try another city or specialty, or clear the filters.</p>
        </div>
      )}

      {reviewing && <HospitalReviews hospital={reviewing} onClose={() => setReviewing(null)} />}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {(hospitals || []).map((h, i) => <HospitalCard key={h.account_id} h={h} onOpen={() => open(h)} onReviews={() => setReviewing(h)} delay={i * 60} />)}
      </div>
    </div>
  );
}

function HospitalCard({ h, onOpen, onReviews, delay }) {
  return (
    <div role="button" tabIndex={0} onClick={onOpen} onKeyDown={(e) => e.key === "Enter" && onOpen()} data-testid={`hospital-card-${h.account_id}`} style={{ animationDelay: `${delay}ms`, transition: "box-shadow 0.2s ease, transform 0.2s ease" }}
      className="card p-6 text-start fade-up hover:shadow-md hover:-translate-y-0.5 flex flex-col gap-3 cursor-pointer">
      <div className="flex items-start gap-3">
        <span className="h-11 w-11 rounded-xl flex items-center justify-center shrink-0 text-white font-bold" style={{ background: h.primary_color || "#1F4D3A" }}>
          {h.logo_url ? <img src={`${process.env.REACT_APP_BACKEND_URL}${h.logo_url}`} alt="" className="h-11 w-11 rounded-xl object-cover" /> : h.name.charAt(0)}
        </span>
        <div className="min-w-0 flex-1">
          <p className="font-semibold flex items-center gap-2 flex-wrap">
            {h.name}
            {h.is_my_hospital && (
              <span className="text-[10px] uppercase tracking-wider bg-forest/10 text-forest px-1.5 py-0.5 rounded-full inline-flex items-center gap-1" data-testid={`my-hospital-badge-${h.account_id}`}>
                <CheckCircle2 className="h-3 w-3" /> Your hospital
              </span>
            )}
          </p>
          <p className="text-xs text-ink-soft mt-0.5 flex items-center gap-1"><MapPin className="h-3 w-3" /> {h.city || "City not listed"} · {h.type === "clinic" ? "Clinic" : "Hospital"}</p>
          <button onClick={(e) => { e.stopPropagation(); onReviews(); }} className="mt-1 inline-flex items-center gap-1.5 text-xs hover:underline" data-testid={`hospital-rating-${h.account_id}`}>
            {h.rating_count ? <><Stars value={h.rating_avg} size="h-3.5 w-3.5" /> <bdi className="font-semibold">{h.rating_avg}</bdi> <span className="text-ink-soft">(<bdi>{h.rating_count}</bdi>)</span></> : <span className="text-ink-soft">No ratings yet</span>}
          </button>
          {h.top_rated && <span className="ms-2 text-[10px] uppercase tracking-wider bg-amber-100 text-amber-800 px-1.5 py-0.5 rounded-full inline-flex items-center gap-1" data-testid={`top-rated-${h.account_id}`}><Award className="h-3 w-3" /> Top rated</span>}
        </div>
      </div>
      {h.about && <p className="text-sm text-ink-soft line-clamp-2">{h.about}</p>}
      <div className="flex flex-wrap gap-1.5">
        {h.specialties.slice(0, 4).map((s) => <span key={s} className="text-[11px] px-2 py-0.5 rounded-full bg-sand border border-line">{s}</span>)}
      </div>
      <div className="flex items-center justify-between pt-2 border-t border-line mt-auto">
        <span className="text-xs text-ink-soft flex items-center gap-1.5" data-testid={`hospital-doctors-${h.account_id}`}>
          <Stethoscope className="h-3.5 w-3.5 text-forest" /> {h.bookable_doctor_count} of {h.doctor_count} doctors taking bookings
        </span>
        <span className="text-sm font-semibold text-forest flex items-center gap-1">See doctors <ArrowRight className="h-4 w-4 rtl:rotate-180" /></span>
      </div>
    </div>
  );
}
