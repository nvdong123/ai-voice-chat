import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { AuthProvider } from './contexts/AuthContext';
import Layout from './components/Layout';
import ProtectedRoute from './components/ProtectedRoute';
import LoginPage from './pages/LoginPage';
import PromptPage from './pages/PromptPage';
import ConfigPage from './pages/ConfigPage';
import ScenesPage from './pages/ScenesPage';

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter basename="/admin">
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route index element={<Navigate to="/prompt" replace />} />
            <Route path="prompt" element={<PromptPage />} />
            <Route path="config" element={<ConfigPage />} />
            <Route path="scenes" element={<ScenesPage />} />
          </Route>
        </Routes>
      </BrowserRouter>

      <Toaster
        position="top-right"
        toastOptions={{
          duration: 4000,
          style: {
            background: '#161b22',
            color: '#e2e8f0',
            border: '1px solid rgba(255,255,255,0.08)',
            fontFamily: '"Be Vietnam Pro", sans-serif',
            fontSize: '0.875rem',
          },
          success: { iconTheme: { primary: '#34d399', secondary: '#161b22' } },
          error:   { iconTheme: { primary: '#f87171', secondary: '#161b22' } },
        }}
      />
    </AuthProvider>
  );
}
