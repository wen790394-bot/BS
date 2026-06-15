import { Routes, Route, Navigate } from 'react-router-dom'
import AppLayout from './components/Layout/AppLayout'
import Dashboard from './pages/Dashboard'
import Vehicles from './pages/Vehicles'
import Tasks from './pages/Tasks'
import ChargeStations from './pages/ChargeStations'
import Scheduling from './pages/Scheduling'
import Routing from './pages/Routing'
import Visualization from './pages/Visualization'
import BatteryHealth from './pages/BatteryHealth'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<AppLayout />}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="vehicles" element={<Vehicles />} />
        <Route path="tasks" element={<Tasks />} />
        <Route path="charge-stations" element={<ChargeStations />} />
        <Route path="routing" element={<Routing />} />
        <Route path="scheduling" element={<Scheduling />} />
        <Route path="battery" element={<BatteryHealth />} />
        <Route path="visualization" element={<Visualization />} />
      </Route>
    </Routes>
  )
}
