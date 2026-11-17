import { useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { getHealth, getModels } from "./api.js";
import Layout from "./components/Layout.jsx";
import Home from "./pages/Home.jsx";
import ScanHistory from "./pages/ScanHistory.jsx";
import ScanDetail from "./pages/ScanDetail.jsx";
import Models from "./pages/Models.jsx";

export default function App() {
  const [models, setModels] = useState([]);
  const [status, setStatus] = useState("checking"); // checking / online / offline

  function connect() {
    setStatus("checking");
    Promise.all([getHealth(), getModels()])
      .then(([, m]) => {
        setModels(m);
        setStatus("online");
      })
      .catch(() => setStatus("offline"));
  }

  useEffect(connect, []);

  return (
    <Routes>
      <Route element={<Layout status={status} onRetry={connect} models={models} />}>
        <Route index element={<Navigate to="/home" replace />} />
        <Route path="/home" element={<Home />} />
        <Route path="/history" element={<ScanHistory />} />
        <Route path="/history/:id" element={<ScanDetail />} />
        <Route path="/models" element={<Models />} />
        <Route path="*" element={<Navigate to="/home" replace />} />
      </Route>
    </Routes>
  );
}
