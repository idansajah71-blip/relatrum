"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, getToken } from "@/lib/api";
import Link from "next/link";

export default function DashboardPage() {
  const router = useRouter();
  const [workspaces, setWorkspaces] = useState<any[]>([]);
  const [cases, setCases] = useState<any[]>([]);
  const [selectedWs, setSelectedWs] = useState<string>("");
  const [newWs, setNewWs] = useState("");
  const [newCase, setNewCase] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!getToken()) { router.push("/login"); return; }
    (async () => {
      try {
        const res: any = await api("/api/v1/workspaces");
        setWorkspaces(res.data || []);
        if (res.data?.length) setSelectedWs(res.data[0].id);
      } catch (e: any) { setError(e.message); }
      finally { setLoading(false); }
    })();
  }, [router]);

  useEffect(() => {
    if (!selectedWs) return;
    (async () => {
      try {
        const res: any = await api(`/api/v1/workspaces/${selectedWs}/cases`);
        setCases(res.data || []);
      } catch (e: any) { setError(e.message); }
    })();
  }, [selectedWs]);

  async function createWs() {
    if (!newWs.trim()) return;
    const res: any = await api("/api/v1/workspaces", { method: "POST", body: JSON.stringify({ name: newWs }) });
    setWorkspaces((w) => [...w, res.data]);
    setSelectedWs(res.data.id);
    setNewWs("");
  }

  async function createCase() {
    if (!newCase.trim() || !selectedWs) return;
    const res: any = await api(`/api/v1/workspaces/${selectedWs}/cases`, { method: "POST", body: JSON.stringify({ title: newCase }) });
    setCases((c) => [...c, res.data]);
    setNewCase("");
  }

  if (loading) return <p>Loading...</p>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Dashboard</h1>
      {error && <p className="text-red-600">{error}</p>}
      <div className="rounded border bg-white p-4">
        <h2 className="mb-2 font-medium">Workspaces</h2>
        <div className="flex gap-2">
          <select className="rounded border px-2 py-1" value={selectedWs} onChange={(e) => setSelectedWs(e.target.value)}>
            {workspaces.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
          </select>
          <input className="rounded border px-2 py-1" placeholder="New workspace" value={newWs} onChange={(e) => setNewWs(e.target.value)} />
          <button className="rounded bg-slate-800 px-3 py-1 text-white" onClick={createWs}>Create</button>
        </div>
      </div>
      <div className="rounded border bg-white p-4">
        <h2 className="mb-2 font-medium">Cases</h2>
        <div className="mb-3 flex gap-2">
          <input className="rounded border px-2 py-1" placeholder="New case title" value={newCase} onChange={(e) => setNewCase(e.target.value)} />
          <button className="rounded bg-slate-800 px-3 py-1 text-white" onClick={createCase}>Create</button>
        </div>
        <ul className="space-y-1">
          {cases.map((c) => (
            <li key={c.id}>
              <Link className="text-blue-600 hover:underline" href={`/cases/${c.id}`}>{c.title}</Link>
              <span className="ml-2 text-xs text-slate-500">{c.status}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
