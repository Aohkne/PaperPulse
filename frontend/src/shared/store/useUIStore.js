import { create } from 'zustand';

export const useUIStore = create((set) => ({
  graphOpen: false,
  setGraphOpen: (open) => set({ graphOpen: open }),
}));
