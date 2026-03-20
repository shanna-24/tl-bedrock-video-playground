import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { AuthProvider } from './contexts/AuthContext'
import { WebSocketProvider } from './contexts/WebSocketContext'
import ProtectedRoute from './components/Auth/ProtectedRoute'
import Login from './components/Auth/Login'
import DashboardLayout from './components/Layout/DashboardLayout'

function App() {
  return (
    <AuthProvider>
      <WebSocketProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/*" element={
              <ProtectedRoute>
                <DashboardLayout />
              </ProtectedRoute>
            } />
          </Routes>
        </BrowserRouter>
      </WebSocketProvider>
    </AuthProvider>
  )
}

export default App
