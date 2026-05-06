import { Route, Routes } from "react-router-dom";
import { AuthProvider } from "@/auth/AuthProvider";
import { ProtectedRoute } from "@/auth/ProtectedRoute";
import Login from "@/pages/Login";
import Layout from "@/pages/Layout";
import Overview from "@/pages/Overview";
import BestSellers from "@/pages/BestSellers";
import TimeSeries from "@/pages/TimeSeries";
import PeakHours from "@/pages/PeakHours";
import Comparison from "@/pages/Comparison";

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          element={
            <ProtectedRoute>
              <Layout />
            </ProtectedRoute>
          }
        >
          <Route index element={<Overview />} />
          <Route path="/best-sellers" element={<BestSellers />} />
          <Route path="/time-series" element={<TimeSeries />} />
          <Route path="/peak-hours" element={<PeakHours />} />
          <Route path="/comparison" element={<Comparison />} />
        </Route>
      </Routes>
    </AuthProvider>
  );
}
