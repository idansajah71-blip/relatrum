"use client";
import { Suspense } from "react";
import CaseDetail from "./CaseDetail";

export default function CasePage() {
  return (
    <Suspense fallback={<p>Loading case...</p>}>
      <CaseDetail />
    </Suspense>
  );
}
