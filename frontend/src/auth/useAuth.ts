import { atom, useAtom } from "jotai";
import { setTokens, clearTokens, getAccess, getRefresh, loginApi } from "../lib/api";

type AuthState = {
  isAuthed: boolean;
  loading: boolean;
  error?: string;
  user?: { email?: string; username?: string; role?: string };
};

const initial: AuthState = {
  isAuthed: Boolean(getAccess()),
  loading: false,
};

const authAtom = atom<AuthState>(initial);

export function useAuth() {
  const [state, set] = useAtom(authAtom);

  const login = async (identifier: string, password: string) => {
    set((s) => ({ ...s, loading: true, error: undefined }));
    try {
      const tokens = await loginApi(identifier, password);
      setTokens(tokens.access, tokens.refresh);
      set({ isAuthed: true, loading: false, error: undefined, user: { username: identifier } });
      return true;
    } catch (e: any) {
      set({ isAuthed: false, loading: false, error: "Invalid credentials" });
      return false;
    }
  };

  const logout = () => {
    clearTokens();
    set({ isAuthed: false, loading: false, user: undefined, error: undefined });
  };

  return { ...state, login, logout };
}
