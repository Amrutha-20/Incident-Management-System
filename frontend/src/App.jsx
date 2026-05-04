import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/common/Layout'
import DashboardPage from './pages/DashboardPage'
import IncidentDetailPage from './pages/IncidentDetailPage'
import IngestPage from './pages/IngestPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<DashboardPage />} />
          <Route path="incidents/:id" element={<IncidentDetailPage />} />
          <Route path="ingest" element={<IngestPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}