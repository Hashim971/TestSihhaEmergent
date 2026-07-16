import React, { useState } from "react";
import { api } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { Plus, Trash2, Users } from "lucide-react";

export default function Dependents() {
  const { dependents, refreshDependents, setActiveProfile } = useAuth();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", relation: "Child", date_of_birth: "", gender: "" });

  const add = async (e) => {
    e.preventDefault();
    if (!form.name) return toast.error("Name is required");
    await api.post("/dependents", form);
    toast.success(`${form.name} added to your family profiles`);
    setForm({ name: "", relation: "Child", date_of_birth: "", gender: "" });
    setShowForm(false);
    refreshDependents();
  };

  const remove = async (id) => {
    await api.delete(`/dependents/${id}`);
    toast.success("Dependent removed");
    refreshDependents();
  };

  return (
    <div className="space-y-8 fade-up max-w-4xl" data-testid="dependents-page">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Dependents</h1>
          <p className="text-ink-soft mt-1">Manage family health profiles — vitals, medications and screenings for each.</p>
        </div>
        <button onClick={() => setShowForm(!showForm)} data-testid="add-dependent-btn" className="btn-primary">
          <Plus className="h-4 w-4" /> Add Dependent
        </button>
      </div>

      {showForm && (
        <form onSubmit={add} className="card p-6 grid grid-cols-1 md:grid-cols-4 gap-4" data-testid="dependent-form">
          <div>
            <label className="text-xs uppercase tracking-[0.15em] text-ink-soft">Name</label>
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} data-testid="dependent-input-name"
              className="mt-1 w-full border border-line rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-forest" />
          </div>
          <div>
            <label className="text-xs uppercase tracking-[0.15em] text-ink-soft">Relation</label>
            <select value={form.relation} onChange={(e) => setForm({ ...form, relation: e.target.value })} data-testid="dependent-input-relation"
              className="mt-1 w-full border border-line rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-forest">
              {["Child", "Spouse", "Parent", "Sibling", "Other"].map((r) => <option key={r}>{r}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs uppercase tracking-[0.15em] text-ink-soft">Date of Birth</label>
            <input type="date" value={form.date_of_birth} onChange={(e) => setForm({ ...form, date_of_birth: e.target.value })} data-testid="dependent-input-dob"
              className="mt-1 w-full border border-line rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-forest" />
          </div>
          <div>
            <label className="text-xs uppercase tracking-[0.15em] text-ink-soft">Gender</label>
            <select value={form.gender} onChange={(e) => setForm({ ...form, gender: e.target.value })} data-testid="dependent-input-gender"
              className="mt-1 w-full border border-line rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-forest">
              <option value="">—</option>
              {["Male", "Female", "Other"].map((g) => <option key={g}>{g}</option>)}
            </select>
          </div>
          <div className="col-span-full">
            <button type="submit" data-testid="dependent-submit-btn" className="btn-primary">Save Dependent</button>
          </div>
        </form>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4" data-testid="dependents-list">
        {dependents.length === 0 && (
          <div className="card p-10 col-span-full text-center">
            <Users className="h-10 w-10 text-sage mx-auto mb-3" />
            <p className="text-ink-soft">No dependents yet. Add a family member to manage their health.</p>
          </div>
        )}
        {dependents.map((d) => (
          <div key={d.dependent_id} className="card p-6 flex items-center justify-between" data-testid={`dependent-card-${d.dependent_id}`}>
            <div className="flex items-center gap-4">
              <span className="h-12 w-12 rounded-full bg-sage text-forest flex items-center justify-center text-lg font-bold font-heading">
                {d.name.charAt(0).toUpperCase()}
              </span>
              <div>
                <p className="font-semibold">{d.name}</p>
                <p className="text-sm text-ink-soft">{d.relation}{d.date_of_birth ? ` · b. ${d.date_of_birth}` : ""}</p>
              </div>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => { setActiveProfile({ id: d.dependent_id, name: d.name }); toast.success(`Now viewing ${d.name}'s profile`); }}
                data-testid={`switch-to-dependent-${d.dependent_id}`}
                className="btn-outline text-xs"
              >
                View Profile
              </button>
              <button onClick={() => remove(d.dependent_id)} data-testid={`delete-dependent-${d.dependent_id}`}
                className="p-2 rounded-full hover:bg-terracotta/10 text-terracotta" style={{ transition: "background-color 0.2s ease" }}>
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
