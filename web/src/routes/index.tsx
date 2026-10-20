import { createFileRoute } from "@tanstack/react-router";
import { AgentHome } from "@/components/agent/agent-home";

export const Route = createFileRoute("/")({ component: AgentHome });
