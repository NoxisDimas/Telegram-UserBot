import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import Login from './pages/Login';
import DashboardLayout from './layouts/DashboardLayout';
import Overview from './pages/Overview';
import Fsub from './pages/Fsub';
import Content from './pages/Content';
import Broadcast from './pages/Broadcast';
import Users from './pages/Users';

// Simple auth check component
const PrivateRoute = ({ children }) => {
  const token = localStorage.getItem('token');
  return token ? children : <Navigate to="/login" />;
};

function App() {
  return (
    <>
      <Toaster
        position="top-right"
        toastOptions={{
          duration: 3000,
          style: {
            background: '#161616',
            color: '#f5f5f5',
            border: '1px solid #1e1e1e',
            borderRadius: '10px',
            fontSize: '14px',
          },
          success: {
            iconTheme: {
              primary: '#39FF14',
              secondary: '#0a0a0a',
            },
          },
          error: {
            iconTheme: {
              primary: '#ef4444',
              secondary: '#0a0a0a',
            },
          },
        }}
      />
      <Router>
        <Routes>
          <Route path="/login" element={<Login />} />

          <Route path="/" element={
            <PrivateRoute>
              <DashboardLayout />
            </PrivateRoute>
          }>
            <Route index element={<Overview />} />
            <Route path="fsub" element={<Fsub />} />
            <Route path="content" element={<Content />} />
            <Route path="broadcast" element={<Broadcast />} />
            <Route path="users" element={<Users />} />
          </Route>
        </Routes>
      </Router>
    </>
  );
}

export default App;
