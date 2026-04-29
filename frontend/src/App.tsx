import { lazy, Suspense } from 'react';
import { Routes, Route } from 'react-router-dom';
import Home from './pages/Home';
import { ResultsPage } from './pages/ResultsPage';
import Attribution from './pages/Attribution';
import SavedAreas from './pages/SavedAreas';
import ErrorBoundary from './components/ErrorBoundary';

const Prototype = lazy(() => import('./pages/Prototype'));
const Prototype2 = lazy(() => import('./pages/Prototype2'));
const IconShowcase = lazy(() => import('./pages/IconShowcase'));

export default function App() {
  return (
    <ErrorBoundary>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/results" element={<ResultsPage />} />
        <Route path="/saved" element={<SavedAreas />} />
        <Route path="/data-attribution" element={<Attribution />} />
        <Route path="/prototype" element={<Suspense fallback={null}><Prototype /></Suspense>} />
        <Route path="/prototype2" element={<Suspense fallback={null}><Prototype2 /></Suspense>} />
        <Route path="/icons" element={<Suspense fallback={null}><IconShowcase /></Suspense>} />
      </Routes>
    </ErrorBoundary>
  );
}
