import React, { PropsWithChildren } from "react";

// Jotai already stores; this wrapper is for future user bootstrap (/me) if needed
export default function AuthProvider({ children }: PropsWithChildren) {
  return <>{children}</>;
}
