// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// Copyright 2026 Serverless Ventures LLC
import { Route, Routes } from "react-router";
import { Placeholder } from "./routes/Placeholder";

export const LICENSE_NOTICE = "Copyright Serverless Ventures LLC. Noncommercial use only.";

export function AppRoutes() {
  return (
    <>
      <Routes>
        <Route path="/" element={<Placeholder />} />
      </Routes>
      <footer>{LICENSE_NOTICE}</footer>
    </>
  );
}
