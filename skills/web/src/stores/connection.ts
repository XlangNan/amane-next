import { create } from "zustand";

type ConnectionStatus = "connected" | "disconnected" | "reconnecting";

interface ConnectionState {
  status: ConnectionStatus;
  lastEventAt: number | null;
  setStatus: (status: ConnectionStatus) => void;
  setLastEventAt: (timestamp: number) => void;
}

export const useConnectionStore = create<ConnectionState>((set) => ({
  status: "disconnected",
  lastEventAt: null,
  setStatus: (status) => set({ status }),
  setLastEventAt: (lastEventAt) => set({ lastEventAt }),
}));
