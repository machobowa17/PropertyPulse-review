import { Routes, Route } from 'react-router-dom';
import Home from './pages/Home';
import { ResultsPage } from './pages/ResultsPage';
import Attribution from './pages/Attribution';
import SavedAreas from './pages/SavedAreas';
import ErrorBoundary from './components/ErrorBoundary';

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/results" element={<ErrorBoundary><ResultsPage /></ErrorBoundary>} />
      <Route path="/saved" element={<SavedAreas />} />
      <Route path="/data-attribution" element={<Attribution />} />
    </Routes>
  );
}
