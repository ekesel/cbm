import React, { useEffect, useMemo, useState } from "react";
import axios from "axios";
import { z } from "zod";

type StatusMap = Record<string, string[]>;
type MappingConfig = {
  jira?: { points_field?: string; status_map?: StatusMap };
  clickup?: { points_field_name?: string };
  azure?: { points_field?: string };
  github?: { link_patterns?: Record<string, string> };
  validator?: Record<string, any>;
};

const CANONICAL_STEPS = [
  "dev_started","dev_done","ready_for_qa","qa_started","qa_verified",
  "signed_off","ready_for_uat","deployed_uat","done"
];

const JiraSchema = z.object({
  points_field: z.string().min(1, "Required"),
  status_map: z.record(z.array(z.string().min(1))).refine(
    (m) => CANONICAL_STEPS.every((s) => s in m),
    { message: "All canonical steps must be present" }
  )
});

const ClickUpSchema = z.object({
  points_field_name: z.string().min(1, "Required")
});

const AzureSchema = z.object({
  points_field: z.string().min(1, "Required")
});

const GitHubSchema = z.object({
  link_patterns: z.record(z.string().min(1))
});

const MappingSchema = z.object({
  jira: JiraSchema,
  clickup: ClickUpSchema,
  azure: AzureSchema,
  github: GitHubSchema,
}).partial().refine((cfg) => !!cfg.jira && !!cfg.clickup && !!cfg.azure && !!cfg.github, {
  message: "All sections (jira, clickup, azure, github) are required"
});

function defaultConfig(): MappingConfig {
  return {
    jira: {
      points_field: "customfield_10016",
      status_map: Object.fromEntries(CANONICAL_STEPS.map(s => [s, []]))
    },
    clickup: { points_field_name: "Story Points" },
    azure:   { points_field: "Microsoft.VSTS.Scheduling.StoryPoints" },
    github:  { link_patterns: { jira: "([A-Z]{2,}-\\d+)" } },
    validator: {}
  };
}

export default function MappingMatrixPage() {
  const [loading, setLoading] = useState(true);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [cfg, setCfg] = useState<MappingConfig>(defaultConfig());
  const [errors, setErrors] = useState<{path:string;msg:string}[]>([]);
  const [warnings, setWarnings] = useState<{path:string;msg:string}[]>([]);
  const [serverOk, setServerOk] = useState<boolean | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        // Get active mapping (first active)
        const res = await axios.get("/api/admin/mappings/");
        const rows = res.data || [];
        const active = rows.find((r:any) => r.active) || rows[0];
        if (active) {
          setActiveId(active.id);
          setCfg({ ...defaultConfig(), ...(active.config || {}) });
        }
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const clientValidate = () => {
    setErrors([]); setWarnings([]); setServerOk(null);
    try {
      MappingSchema.parse(cfg);
      return true;
    } catch (e:any) {
      const errs = (e.issues || []).map((i:any) => ({path:(i.path||[]).join("."), msg:i.message}));
      setErrors(errs);
      return false;
    }
  };

  const serverValidate = async (save=false) => {
    try {
      const res = await axios.post("/api/admin/mapping/validate/", { config: cfg, save });
      setWarnings(res.data.warnings || []);
      setServerOk(true);
      return true;
    } catch (e:any) {
      setServerOk(false);
      const data = e?.response?.data || {};
      setErrors(data.errors || [{path:"", msg:"Validation failed"}]);
      setWarnings(data.warnings || []);
      return false;
    }
  };

  const onValidateClick = async () => {
    if (!clientValidate()) return;
    await serverValidate(false);
  };

  const onSaveClick = async () => {
    if (!clientValidate()) return;
    setSaving(true);
    const ok = await serverValidate(true);
    setSaving(false);
    if (ok) alert("Mapping saved to active version.");
  };

  // --- editors ---
  const updateJiraStep = (step: string, val: string) => {
    const items = val.split(",").map(s => s.trim()).filter(Boolean);
    setCfg(prev => ({...prev, jira: {...(prev.jira||{}), status_map: {...(prev.jira?.status_map||{}), [step]: items}}));
  };

  if (loading) return <div className="p-6">Loading…</div>;

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-semibold">Mapping Matrix</h1>

      {(errors.length > 0) && (
        <div className="rounded-md border border-red-300 bg-red-50 p-3">
          <div className="font-semibold text-red-700">Errors</div>
          <ul className="list-disc ml-5 text-red-800">
            {errors.map((e, i) => <li key={i}><code>{e.path}</code>: {e.msg}</li>)}
          </ul>
        </div>
      )}

      {(warnings.length > 0) && (
        <div className="rounded-md border border-amber-300 bg-amber-50 p-3">
          <div className="font-semibold text-amber-700">Warnings</div>
          <ul className="list-disc ml-5 text-amber-800">
            {warnings.map((w, i) => <li key={i}><code>{w.path}</code>: {w.msg}</li>)}
          </ul>
        </div>
      )}

      {serverOk === true && errors.length === 0 && (
        <div className="rounded-md border border-emerald-300 bg-emerald-50 p-3 text-emerald-800">
          ✅ Server validation passed.
        </div>
      )}

      {/* Jira */}
      <section className="space-y-4">
        <h2 className="text-xl font-medium">Jira</h2>
        <div className="grid md:grid-cols-2 gap-4">
          <div>
            <label className="text-sm font-medium">Story Points Field</label>
            <input
              className="mt-1 w-full rounded-md border p-2"
              value={cfg.jira?.points_field || ""}
              onChange={(e)=> setCfg(prev => ({...prev, jira: {...(prev.jira||{}), points_field: e.target.value}}))}
              placeholder="customfield_10016"
            />
          </div>
        </div>

        <div className="mt-4">
          <div className="text-sm font-medium mb-2">Status → Canonical Steps (comma-separated status names)</div>
          <div className="grid lg:grid-cols-2 gap-3">
            {CANONICAL_STEPS.map(step => (
              <div key={step} className="rounded-md border p-3">
                <div className="text-xs uppercase text-gray-500">{step}</div>
                <input
                  className="mt-1 w-full rounded-md border p-2"
                  placeholder="e.g., In Progress, Development"
                  value={(cfg.jira?.status_map?.[step] || []).join(", ")}
                  onChange={(e)=> updateJiraStep(step, e.target.value)}
                />
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ClickUp */}
      <section className="space-y-3">
        <h2 className="text-xl font-medium">ClickUp</h2>
        <div className="grid md:grid-cols-2 gap-4">
          <div>
            <label className="text-sm font-medium">Points Custom Field Name</label>
            <input
              className="mt-1 w-full rounded-md border p-2"
              value={cfg.clickup?.points_field_name || ""}
              onChange={(e)=> setCfg(prev => ({...prev, clickup: {...(prev.clickup||{}), points_field_name: e.target.value}}))}
              placeholder="Story Points"
            />
          </div>
        </div>
      </section>

      {/* Azure */}
      <section className="space-y-3">
        <h2 className="text-xl font-medium">Azure Boards</h2>
        <div className="grid md:grid-cols-2 gap-4">
          <div>
            <label className="text-sm font-medium">Story Points Field RefName</label>
            <input
              className="mt-1 w-full rounded-md border p-2"
              value={cfg.azure?.points_field || ""}
              onChange={(e)=> setCfg(prev => ({...prev, azure: {...(prev.azure||{}), points_field: e.target.value}}))}
              placeholder="Microsoft.VSTS.Scheduling.StoryPoints"
            />
          </div>
        </div>
      </section>

      {/* GitHub */}
      <section className="space-y-3">
        <h2 className="text-xl font-medium">GitHub (PR Link Patterns)</h2>
        <div className="grid md:grid-cols-2 gap-4">
          <KVEditor
            label="link_patterns"
            value={cfg.github?.link_patterns || {}}
            onChange={(obj)=> setCfg(prev => ({...prev, github: {...(prev.github||{}), link_patterns: obj}}))}
          />
        </div>
      </section>

      {/* Actions */}
      <div className="flex gap-2 pt-4">
        <button className="rounded-md border px-4 py-2" onClick={onValidateClick}>
          Validate
        </button>
        <button className="rounded-md bg-black text-white px-4 py-2" onClick={onSaveClick} disabled={saving}>
          {saving ? "Saving..." : "Save to Active Mapping"}
        </button>
      </div>
    </div>
  );
}

function KVEditor({label, value, onChange}:{label:string; value:Record<string,string>; onChange:(v:Record<string,string>)=>void}) {
  const [rows, setRows] = useState<{k:string; v:string}[]>([]);
  useEffect(()=>{
    const r = Object.entries(value||{}).map(([k,v])=>({k, v}));
    if (r.length === 0) r.push({k:"jira", v:"([A-Z]{2,}-\\d+)"});
    setRows(r);
  }, [value]);

  const update = (i:number, key:"k"|"v", val:string) => {
    const next = rows.slice();
    next[i] = {...next[i], [key]: val};
    setRows(next);
    onChange(Object.fromEntries(next.filter(r=>r.k.trim()).map(r=>[r.k, r.v])));
  };

  return (
    <div className="w-full">
      <div className="text-sm font-medium mb-2">{label}</div>
      <div className="space-y-2">
        {rows.map((r,i)=>(
          <div key={i} className="grid grid-cols-2 gap-2">
            <input className="rounded-md border p-2" placeholder="name (e.g., jira)" value={r.k} onChange={(e)=>update(i,"k",e.target.value)} />
            <input className="rounded-md border p-2" placeholder="regex" value={r.v} onChange={(e)=>update(i,"v",e.target.value)} />
          </div>
        ))}
        <button className="mt-2 rounded-md border px-3 py-1" onClick={()=> setRows([...rows, {k:"", v:""}])}>+ Add</button>
      </div>
    </div>
  );
}
