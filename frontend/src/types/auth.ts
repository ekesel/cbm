export type JwtPair = {
    access: string;
    refresh: string;
  };
  
  export type AuthUser = {
    id?: string | number;
    email?: string;
    username?: string;
    role?: string; // if your backend exposes it on /me later
  };
  