import { Link } from 'react-router-dom';
import { ArrowLeft, Leaf, Bookmark } from 'lucide-react';
import SearchBox from '../SearchBox';
import DecisionModeSelector from '../DecisionModeSelector';
import PersonaSelector from '../PersonaSelector';
import { useResults } from '../../context/ResultsContext';

export function ResultsHeader() {
  const { q, decisionMode, handleDecisionModeChange, persona, setPersona, enhancedMode, setEnhancedMode } = useResults();

  return (
    <header className="sticky top-0 z-50 bg-white/95 backdrop-blur-md border-b border-divider/60">
      <div className="max-w-[1400px] mx-auto px-4 lg:px-6 py-2.5 flex items-center gap-3">
        <Link to="/" className="p-2 rounded-xl hover:bg-surface transition-colors" aria-label="Back to home">
          <ArrowLeft className="w-5 h-5 text-ink-muted" aria-hidden="true" />
        </Link>
        <Link to="/" className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-brand-500 flex items-center justify-center">
            <Leaf className="w-3.5 h-3.5 text-white" />
          </div>
          <span className="font-bold text-sm tracking-tight text-ink hidden sm:block">PropertyPulse</span>
        </Link>
        <div className="flex-1 max-w-md">
          <SearchBox size="sm" initialValue={q} />
        </div>
        <DecisionModeSelector current={decisionMode} onChange={handleDecisionModeChange} variant="dropdown" />
        <PersonaSelector current={persona} onChange={setPersona} />
        <button
          onClick={() => setEnhancedMode((v: boolean) => !v)}
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-surface text-xs font-medium text-ink-muted hover:bg-surface-warm transition-colors"
          title={enhancedMode ? 'Switch to current view' : 'Switch to enhanced view'}
        >
          <span className={enhancedMode ? 'text-ink-muted' : 'text-ink font-semibold'}>Current</span>
          <div className={`relative w-8 h-4.5 rounded-full transition-colors ${enhancedMode ? 'bg-brand-500' : 'bg-ink-faint/40'}`}>
            <div className={`absolute top-0.5 w-3.5 h-3.5 rounded-full bg-white shadow-sm transition-transform ${enhancedMode ? 'translate-x-4' : 'translate-x-0.5'}`} />
          </div>
          <span className={enhancedMode ? 'text-ink font-semibold' : 'text-ink-muted'}>Enhanced</span>
        </button>
        <Link
          to="/saved"
          className="p-2 rounded-xl hover:bg-surface transition-colors"
          aria-label="Saved areas"
          title="Saved areas"
        >
          <Bookmark className="w-5 h-5 text-ink-muted" aria-hidden="true" />
        </Link>
      </div>
    </header>
  );
}
