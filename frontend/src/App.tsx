import { Navigate, Route, Routes } from 'react-router-dom'
import AppLayout from './components/layout/AppLayout'
import ProtectedRoute from './components/layout/ProtectedRoute'
import RequireRole from './components/layout/RequireRole'
import AdminSecurity from './pages/AdminSecurity'
import ChallengeView from './pages/ChallengeView'
import Dashboard from './pages/Dashboard'
import Datasources from './pages/Datasources'
import EvalDashboard from './pages/EvalDashboard'
import EvidenceGraph from './pages/EvidenceGraph'
import ExperimentRecord from './pages/ExperimentRecord'
import InvestigationWorkspace from './pages/InvestigationWorkspace'
import Login from './pages/Login'
import QueryWorkspace from './pages/QueryWorkspace'
import Reports from './pages/Reports'
import SemanticLayer from './pages/SemanticLayer'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<ProtectedRoute><AppLayout /></ProtectedRoute>}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/query" element={<QueryWorkspace />} />
        <Route path="/saved" element={<Reports />} />
        <Route path="/datasources" element={<Datasources />} />
        <Route path="/metrics" element={<SemanticLayer />} />
        <Route path="/investigate" element={<InvestigationWorkspace />} />
        <Route path="/evidence" element={<EvidenceGraph />} />
        <Route path="/challenge" element={<RequireRole roles={['admin', 'analyst']}><ChallengeView /></RequireRole>} />
        <Route path="/record" element={<ExperimentRecord />} />
        <Route path="/eval" element={<EvalDashboard />} />
        <Route path="/admin" element={<RequireRole roles={['admin']}><AdminSecurity /></RequireRole>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
