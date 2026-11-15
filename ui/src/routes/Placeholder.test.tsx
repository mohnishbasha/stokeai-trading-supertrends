// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// Copyright 2026 Serverless Ventures LLC
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { AppRoutes } from "../App";

describe("placeholder route", () => {
  it("renders the product name and tagline at /", () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <AppRoutes />
      </MemoryRouter>,
    );
    expect(screen.getByRole("heading", { name: "Super Trends" })).toBeInTheDocument();
    expect(screen.getByText("Know which way the tape is leaning.")).toBeInTheDocument();
  });

  it("shows the license notice in the footer", () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <AppRoutes />
      </MemoryRouter>,
    );
    expect(screen.getByRole("contentinfo")).toHaveTextContent(
      "Copyright Serverless Ventures LLC. Noncommercial use only.",
    );
  });
});
