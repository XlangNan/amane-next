import { createFileRoute, Outlet } from "@tanstack/react-router";

export const Route = createFileRoute("/feeds")({
  component: () => <Outlet />,
});
