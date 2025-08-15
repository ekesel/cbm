import React, { useEffect, useState } from "react";
import { api, endpoints } from "../lib/api";

export default function Dashboard() {
  const [health, setHealth] = useState<string>("loading...");
  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get(endpoints.health);
        setHealth(JSON.stringify(data));
      } catch (e: any) {
        setHealth("Error fetching health");
      }
    })();
  }, []);
  return (
    <div style={{padding:16}}>
      <h2>Dashboard</h2>
      <pre>{health}</pre>
    </div>
  );
}
