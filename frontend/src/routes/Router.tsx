import React, { Suspense, lazy } from "react";
import { Route, Routes } from "react-router-dom";
import RequireAuth from "../auth/RequireAuth";
import NavBar from "../components/NavBar";

const Login = lazy(() => import("../pages/Login"));
const Dashboard = lazy(() => import("../pages/Dashboard"));
const TeamDashboard = lazy(() => import("../pages/TeamDashboard"));
const NotFound = lazy(() => import("../pages/NotFound"));
const WorkItemPage = lazy(() => import("../pages/WorkItemPage"));
const ComplianceDashboard = lazy(() => import("../pages/ComplianceDashboard"));
const UserDashboard = lazy(() => import("../pages/UserDashboard"));
const AdminHome = React.lazy(() => import("../pages/admin/AdminHome"));
const AdminBoards = React.lazy(() => import("../pages/admin/AdminBoards"));
const AdminBoardEdit = React.lazy(() => import("../pages/admin/AdminBoardEdit"));
const AdminMappings = React.lazy(() => import("../pages/admin/AdminMappings"));
const AdminMappingEdit = React.lazy(() => import("../pages/admin/AdminMappingEdit"));
const AdminETLRunner = React.lazy(() => import("../pages/admin/AdminETLRunner"));

export default function AppRouter() {
  return (
    <>
      <NavBar />
      <Suspense fallback={<div style={{padding:16}}>Loading…</div>}>
        <Routes>
          <Route path="/" element={<div style={{padding:16}}>Welcome</div>} />
          <Route path="/login" element={<Login />} />
          <Route path="/dashboard" element={
            <RequireAuth><Dashboard /></RequireAuth>
          } />
          <Route path="/teams/:teamId/dashboard" element={
            <RequireAuth><TeamDashboard /></RequireAuth>
          } />
          <Route path="*" element={<NotFound />} />
          <Route path="/workitems/:id" element={
            <RequireAuth><WorkItemPage /></RequireAuth>
          } />
          <Route path="/workitems/by-key/:source/:sourceId" element={
            <RequireAuth><WorkItemPage /></RequireAuth>
          } />
          <Route path="/boards/:boardId/compliance" element={
            <RequireAuth><ComplianceDashboard /></RequireAuth>
          } />
          <Route path="/me/dashboard" element={
            <RequireAuth><UserDashboard /></RequireAuth>
          } />
          <Route path="/admin" element={<RequireAuth><AdminHome /></RequireAuth>} />
          <Route path="/admin/boards" element={<RequireAuth><AdminBoards /></RequireAuth>} />
          <Route path="/admin/boards/:boardId" element={<RequireAuth><AdminBoardEdit /></RequireAuth>} />
          <Route path="/admin/mappings" element={<RequireAuth><AdminMappings /></RequireAuth>} />
          <Route path="/admin/mappings/:mappingId" element={<RequireAuth><AdminMappingEdit /></RequireAuth>} />
          <Route path="/admin/etl" element={<RequireAuth><AdminETLRunner /></RequireAuth>} />
        </Routes>
      </Suspense>
    </>
  );
}
