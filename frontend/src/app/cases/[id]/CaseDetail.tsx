"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";

export default function CaseDetail() {
  const params = useParams();
  const caseId = params?.id as string;
  const [caseData, setCaseData] = useState<any>(null);
  const [text, setText] = useState("");
  const [sourceId, setSourceId] = useState("");
  const [statements, setStatements] = useState<any[]>([]);
  const [findings, setFindings] = useState<any[]>([]);
  const [queue, setQueue] = useState<any[]>([]);
  const [report, setReport] = useState("");
  const [msg, setMsg] = useState("");
  const [loading, setLoading] = useState(false);

  async function load() {
    try {
      const c: any = await api(`/api/v1/cases/${caseId}`);
      setCaseData(c.data);
      const st: any = await api(`/api/v1/cases/${caseId}/statements`);
      setStatements(st.data || []);
      const f: any = await api(`/api/v1/cases/${caseId}/findings`);
      setFindings(f.data || []);
      const q: any = await api(`/api/v1/cases/${caseId}/verification-queue`);
      setQueue(q.data || []);
    } catch (e: any) { setMsg(e.message); }
  }

  useEffect(() => { if (caseId) void load(); }, [caseId]); // eslint-disable-line react-hooks/set-state-in-effect

  async function uploadText() {
    if (!text.trim()) return;
    setLoading(true);
    try {
      const res: any = await api(`/api/v1/cases/${caseId}/sources/text`, { method: "POST", body: JSON.stringify({ text, meta: { source_type: "policy", title: "Manual source" } }) });
      setSourceId(res.data.id);
      setMsg("Source uploaded: " + res.data.id);
      await load();
    } catch (e: any) { setMsg(e.message); }
    finally { setLoading(false); }
  }

  async function extract() {
    if (!sourceId) { setMsg("Upload a source first"); return; }
    setLoading(true);
    try {
      const res: any = await api(`/api/v1/sources/${sourceId}/extract`, { method: "POST" });
      setMsg(`Extracted ${res.data.statements_created} statements`);
      await load();
    } catch (e: any) { setMsg(e.message); }
    finally { setLoading(false); }
  }

  async function analyze() {
    setLoading(true);
    try {
      const res: any = await api(`/api/v1/cases/${caseId}/analyze`, { method: "POST", body: JSON.stringify({}) });
      setMsg(`Analyzed: ${JSON.stringify(res.data.alignment_type_counts)}`);
      await load();
    } catch (e: any) { setMsg(e.message); }
    finally { setLoading(false); }
  }

  async function genReport() {
    setLoading(true);
    try {
      const res: any = await api(`/api/v1/cases/${caseId}/reports?format=markdown`);
      setReport(res.data.content);
    } catch (e: any) { setMsg(e.message); }
    finally { setLoading(false); }
  }

  async function genVerification(findingId: string) {
    try {
      await api(`/api/v1/findings/${findingId}/verification`, { method: "POST", body: JSON.stringify({}) });
      const q: any = await api(`/api/v1/cases/${caseId}/verification-queue`);
      setQueue(q.data || []);
    } catch (e: any) { setMsg(e.message); }
  }

  async function patchFinding(findingId: string, status: string) {
    try {
      await api(`/api/v1/findings/${findingId}/status`, { method: "PATCH", body: JSON.stringify({ status }) });
      await load();
    } catch (e: any) { setMsg(e.message); }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">{caseData?.title || "Case"}</h1>
      {msg && <p className="text-sm text-blue-700">{msg}</p>}

      <section className="rounded border bg-white p-4">
        <h2 className="mb-2 font-medium">Ingest text source</h2>
        <textarea className="h-32 w-full rounded border p-2" value={text} onChange={(e) => setText(e.target.value)} />
        <div className="mt-2 flex gap-2">
          <button className="rounded bg-slate-800 px-3 py-1 text-white" onClick={uploadText} disabled={loading}>Upload</button>
          <button className="rounded bg-slate-600 px-3 py-1 text-white" onClick={extract} disabled={loading}>Extract</button>
          <button className="rounded bg-emerald-700 px-3 py-1 text-white" onClick={analyze} disabled={loading}>Analyze</button>
        </div>
      </section>

      <section className="rounded border bg-white p-4">
        <h2 className="mb-2 font-medium">Statements ({statements.length})</h2>
        <ul className="space-y-1 text-sm">
          {statements.map((s) => (
            <li key={s.id}><span className="font-mono text-xs text-slate-500">{s.statement_type}</span> {s.original_text}</li>
          ))}
        </ul>
      </section>

      <section className="rounded border bg-white p-4">
        <h2 className="mb-2 font-medium">Findings ({findings.length})</h2>
        <ul className="space-y-3">
          {findings.map((f) => (
            <li key={f.id} className="rounded border p-3">
              <div className="flex items-center justify-between">
                <strong>{f.title}</strong>
                <span className="text-xs text-slate-500">{f.priority} / {f.status}</span>
              </div>
              <p className="text-sm text-slate-700">{f.summary}</p>
              <div className="mt-2 flex gap-2">
                <button className="rounded bg-slate-200 px-2 py-1 text-xs" onClick={() => patchFinding(f.id, "accepted")}>Accept</button>
                <button className="rounded bg-slate-200 px-2 py-1 text-xs" onClick={() => patchFinding(f.id, "rejected")}>Reject</button>
                <button className="rounded bg-blue-200 px-2 py-1 text-xs" onClick={() => genVerification(f.id)}>Generate MRE</button>
              </div>
            </li>
          ))}
        </ul>
      </section>

      <section className="rounded border bg-white p-4">
        <h2 className="mb-2 font-medium">Verification queue ({queue.length})</h2>
        <ul className="space-y-2 text-sm">
          {queue.map((q) => (
            <li key={q.task_id} className="rounded border p-2">
              <p className="font-medium">{q.question}</p>
              <p className="text-xs text-slate-500">{q.status} / {q.priority}</p>
            </li>
          ))}
        </ul>
      </section>

      <section className="rounded border bg-white p-4">
        <h2 className="mb-2 font-medium">Report</h2>
        <button className="rounded bg-slate-800 px-3 py-1 text-white" onClick={genReport} disabled={loading}>Generate Markdown</button>
        {report && <pre className="mt-3 whitespace-pre-wrap rounded bg-slate-100 p-3 text-xs">{report}</pre>}
      </section>
    </div>
  );
}
