import { lazy } from "react";
import { RouteObject } from "react-router-dom";

const MappingMatrixPage = lazy(() => import("../screens/MappingMatrixPage"));

export const adminRoutes: RouteObject[] = [
  { path: "/admin/mapping-matrix", element: <MappingMatrixPage /> },
];