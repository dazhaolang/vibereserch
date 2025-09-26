import { create } from 'zustand';
import type { UserProfile } from '@/types/user';

interface SystemState {
  hydrated: boolean;
  profile: UserProfile | null;
  setHydrated: (value: boolean) => void;
  setProfile: (profile: UserProfile | null) => void;
}

export const useSystemStore = create<SystemState>()((set) => ({
  hydrated: false,
  profile: null,
  setHydrated: (value) => set({ hydrated: value }),
  setProfile: (profile) => set({ profile }),
}));
