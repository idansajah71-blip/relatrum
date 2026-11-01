"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, setToken } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const path = mode === "login" ? "/api/v1/auth/login" : "/api/v1/auth/register";
      const body = mode === "login" ? { email, password } : { email, password, display_name: name };
      const res: any = await api(path, { method: "POST", body: JSON.stringify(body) });
      setToken(res.data.token);
      router.push("/dashboard");
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-md rounded border bg-white p-6">
      <h1 className="mb-4 text-xl font-semibold">{mode === "login" ? "Login" : "Register"}</h1>
      <form onSubmit={submit} className="space-y-3">
        {mode === "register" && (
          <input className="w-full rounded border px-3 py-2" placeholder="Display name" value={name} onChange={(e) => setName(e.target.value)} />
        )}
        <input className="w-full rounded border px-3 py-2" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} />
        <input className="w-full rounded border px-3 py-2" type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} />
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button disabled={loading} className="w-full rounded bg-slate-800 px-3 py-2 text-white disabled:opacity-50">
          {loading ? "..." : mode === "login" ? "Login" : "Register"}
        </button>
      </form>
      <button className="mt-3 text-sm text-blue-600 hover:underline" onClick={() => setMode(mode === "login" ? "register" : "login")}>
        {mode === "login" ? "Need an account? Register" : "Have an account? Login"}
      </button>
    </div>
  );
}
