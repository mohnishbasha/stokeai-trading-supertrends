// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// Copyright 2026 Serverless Ventures LLC
import { defineConfig } from "@playwright/test";

// E2E flows arrive in Sprint 4 (ui/tests/e2e). Base URL follows the smoke suite convention.
export default defineConfig({
  testDir: "./tests/e2e",
  use: { baseURL: process.env["SMOKE_BASE_URL"] ?? "http://localhost:8080" },
  reporter: [["list"], ["html", { open: "never" }]],
});
