import { Routes, Route } from 'react-router-dom';
import Home from './pages/Home';
import Results from './pages/Results';
import Attribution from './pages/Attribution';
import SavedAreas from './pages/SavedAreas';

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/results" element={<Results />} />
      <Route path="/saved" element={<SavedAreas />} />
      <Route path="/data-attribution" element={<Attribution />} />
    </Routes>
  );
}
