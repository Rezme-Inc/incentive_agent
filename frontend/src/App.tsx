import { Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { WizardProvider } from './context/WizardContext';
import { DevModeProvider } from './context/DevModeContext';
import { InputPage } from './pages/InputPage';
import { ProcessingPage } from './pages/ProcessingPage';
import { ReportPage } from './pages/ReportPage';
import { AdminPage } from './pages/AdminPage';

const queryClient = new QueryClient();

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <DevModeProvider>
        <WizardProvider>
          <Routes>
            <Route path="/" element={<Navigate to="/input" replace />} />
            <Route path="/input" element={<InputPage />} />
            <Route path="/processing/:sessionId" element={<ProcessingPage />} />
            <Route path="/report/:sessionId" element={<ReportPage />} />
            <Route path="/admin" element={<AdminPage />} />
            <Route path="*" element={<Navigate to="/input" replace />} />
          </Routes>
        </WizardProvider>
      </DevModeProvider>
    </QueryClientProvider>
  );
}

export default App;
