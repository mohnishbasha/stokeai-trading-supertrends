// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// Copyright 2026 Serverless Ventures LLC
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";
import { AppRoutes } from "./App";

const root = document.getElementById("root");
if (root === null) {
  throw new Error("missing #root element");
}
createRoot(root).render(
  <StrictMode>
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  </StrictMode>,
);
