"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchHealth, type HealthResponse } from "@/lib/api";

type Phase = "loading" | "ready" | "error";

/** Compact header indicator for API + DB reachability. */
export default function HealthBadge() {
  const [phase, setPhase] = useState<Phase>("loading");
  const [data, setData] = useState<HealthResponse | null>(null);

  const check = useCallback(async (signal?: AbortSignal) => {
    setPhase("loading");
    try {
      const payload = await fetchHealth(signal);
      setData(payload);
      setPhase("ready");
    } catch {
      if (signal?.aborted) return;
      setData(null);
      setPhase("error");
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void check(controller.signal);
    return () => controller.abort();
  }, [check]);

  const apiOk = phase === "ready";
  const dbOk = apiOk && data?.db === "connected";

  return (
    <div
      aria-live="polite"
      className="flex items-center gap-2 text-xs font-medium"
    >
      <Dot label="API" ok={apiOk} loading={phase === "loading"} />
      <Dot label="DB" ok={dbOk} loading={phase === "loading"} />
      <button
        type="button"
        onClick={() => void check()}
        disabled={phase === "loading"}
        className="rounded-md border border-slate-300 px-2 py-1 text-slate-600 transition hover:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-1 disabled:opacity-50"
      >
        重新檢查
      </button>
    </div>
  );
}

function Dot({
  label,
  ok,
  loading,
}: {
  label: string;
  ok: boolean;
  loading: boolean;
}) {
  const stateText = loading ? "檢查中" : ok ? "正常" : "異常";
  const classes = loading
    ? "bg-slate-100 text-slate-600"
    : ok
      ? "bg-emerald-100 text-emerald-800"
      : "bg-rose-100 text-rose-800";

  return (
    <span className={`rounded-full px-2 py-1 ${classes}`}>
      {label} {loading ? "…" : ok ? "✓" : "✕"}
      <span className="sr-only">{stateText}</span>
    </span>
  );
}
