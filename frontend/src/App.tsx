import React from "react";
import AuthProvider from "./auth/AuthProvider";
import AppRouter from "./routes/Router";

export default function App() {
  return (
    <AuthProvider>
      <AppRouter />
    </AuthProvider>
  );
}
