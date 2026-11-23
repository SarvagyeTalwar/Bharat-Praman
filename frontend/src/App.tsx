import { useState, useEffect } from 'react';
import { Topbar } from './components/Topbar';
import { MinistryFilter } from './components/MinistryFilter';
import { ByodDropzone } from './components/ByodDropzone';
import { DossierCard } from './components/DossierCard';
import { AuthModal } from './components/AuthModal';
import { getCurrentUser, setAuthToken, streamIntelligence, askIntelligence } from './lib/api';
import type { UserProfile, ByodDoc, RagResultItem, DetailLevel, ReasoningMode } from './lib/types';

const BENCHMARKS = [
  {
    q: 'What was the BE vs RE budget outlay and actual funds released for PM-SHRI, Samagra Shiksha, and school infrastructure in 2023-24?',
    min: 'education',
    label: 'PM-SHRI & Samagra Shiksha',
  },
  {
    q: 'How much was allocated to CRPF, BSF and police modernisation, and was it fully used?',
    min: 'home',
    label: 'CRPF & BSF Modernisation',
  },
  {
    q: 'Compare the budget growth of Education, Home Affairs and Defence from 2021-22 to 2025-26',
    min: 'all',
    label: '5-Year Growth Trajectory',
  },
];

export function App() {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [isAuthOpen, setIsAuthOpen] = useState(false);
  const [ministry, setMinistry] = useState('all');
  const [detailLevel, setDetailLevel] = useState<DetailLevel>('long');
  const [reasoningMode] = useState<ReasoningMode>('auto');
  const [question, setQuestion] = useState('');
  const [byodDocs, setByodDocs] = useState<ByodDoc[]>([]);
  const [results, setResults] = useState<RagResultItem[]>([]);
  const [isQuerying, setIsQuerying] = useState(false);
  const [statusText, setStatusText] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    getCurrentUser().then(setUser);
    const params = new URLSearchParams(window.location.search);
    const qParam = params.get('q');
    const minParam = params.get('ministry');
    const detailParam = params.get('detail');
    if (qParam) setQuestion(qParam);
    if (minParam) setMinistry(minParam.toLowerCase());
    if (detailParam === 'short' || detailParam === 'long') setDetailLevel(detailParam);
  }, []);

  const handleLogout = () => {
    setAuthToken('');
    setUser(null);
  };

  const handleRunQuery = async () => {
    if (!question.trim()) return;

    setIsQuerying(true);
    setErrorMessage(null);
    setStatusText('Synthesizing intelligence across sovereign records...');

    const req = {
      question: question.trim(),
      ministry,
      detail_level: detailLevel,
      reasoning_mode: reasoningMode,
      byod_doc_ids: byodDocs.map((d) => d.doc_id),
    };

    try {
      let currentResult: RagResultItem = {
        ministry: ministry.toUpperCase(),
        detail_level: detailLevel,
        reasoning_mode: reasoningMode,
        answer: '',
        sources: [],
      };
      setResults([currentResult]);

      try {
        await streamIntelligence(
          req,
          (meta) => {
            currentResult = {
              ...currentResult,
              sources: meta.sources || [],
              graph_context: meta.graph_context,
              reasoning_mode: meta.reasoning_mode || reasoningMode,
            };
            setResults([{ ...currentResult }]);
          },
          (delta) => {
            currentResult.answer += delta;
            setResults([{ ...currentResult }]);
          }
        );
        setStatusText(null);
      } catch (streamErr) {
        // Fallback to standard request if stream encounters network interruption
        const res = await askIntelligence(req);
        if (res.results && res.results.length) {
          setResults(res.results);
          setStatusText(null);
        } else if (res.error) {
          throw new Error(res.error);
        }
      }
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to fetch intelligence response. Please check network.');
      setStatusText(null);
    } finally {
      setIsQuerying(false);
    }
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col font-sans selection:bg-zinc-800">
      <Topbar user={user} onOpenAuth={() => setIsAuthOpen(true)} onLogout={handleLogout} />

      {/* Full viewport width fluid canvas */}
      <main className="w-full px-6 md:px-10 lg:px-14 xl:px-16 py-8 flex-1 space-y-8 animate-fade-in">
        <div className="border-b border-zinc-900 pb-5">
          <h1 className="text-xl font-semibold tracking-tight text-zinc-100">
            Union Ministry Fiscal &amp; Policy Intelligence
          </h1>
          <p className="text-xs text-zinc-500 mt-1 max-w-2xl leading-normal">
            Grounded across 5 fiscal years of verified Union Ministry Annual Reports and Expenditure Profiles.
          </p>
        </div>

        {/* Input & Parameters */}
        <div className="space-y-4">
          <MinistryFilter selected={ministry} onChange={setMinistry} />

          <div className="relative group">
            <textarea
              rows={3}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => {
                if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
                  e.preventDefault();
                  handleRunQuery();
                }
              }}
              placeholder="Ask a fiscal or policy question (e.g. Compare BE vs RE allocation and actual releases for PM-SHRI in 2023-24)..."
              className="w-full text-sm p-4 bg-zinc-900/80 border border-zinc-800 rounded text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:border-zinc-600 focus:bg-zinc-900 transition-all duration-150 leading-relaxed resize-none shadow-sm"
            />
          </div>

          <ByodDropzone
            user={user}
            docs={byodDocs}
            onAddDoc={(doc) => setByodDocs([...byodDocs, doc])}
            onRemoveDoc={(idx) => setByodDocs(byodDocs.filter((_, i) => i !== idx))}
            onOpenUpgrade={() => setIsAuthOpen(true)}
          />

          <div className="flex flex-wrap items-center justify-between gap-4 pt-1">
            <div className="flex flex-wrap items-center gap-1.5 text-xs text-zinc-500">
              <span className="font-mono text-[11px] mr-1 text-zinc-600">Suggested:</span>
              {BENCHMARKS.map((b, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => {
                    setQuestion(b.q);
                    setMinistry(b.min);
                  }}
                  className="px-2.5 py-1 rounded text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900 active:scale-[0.98] transition-all duration-100"
                >
                  {b.label}
                </button>
              ))}
            </div>

            <div className="flex items-center gap-3">
              <div className="flex items-center text-xs text-zinc-500 font-mono">
                <button
                  type="button"
                  onClick={() => setDetailLevel(detailLevel === 'short' ? 'long' : 'short')}
                  className="hover:text-zinc-300 transition-colors py-1 px-1.5 rounded hover:bg-zinc-900"
                >
                  {detailLevel === 'short' ? 'Brief' : 'Comprehensive'}
                </button>
              </div>

              <button
                type="button"
                disabled={isQuerying || !question.trim()}
                onClick={handleRunQuery}
                className="text-xs font-medium px-4 py-1.5 rounded bg-zinc-100 text-zinc-950 hover:bg-white active:scale-[0.98] transition-all duration-100 disabled:opacity-30 disabled:cursor-not-allowed shadow-sm"
              >
                {isQuerying ? (
                  <span className="inline-flex items-center gap-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-zinc-950 animate-pulse"></span>
                    Querying...
                  </span>
                ) : (
                  'Run Query ↵'
                )}
              </button>
            </div>
          </div>

          {statusText && (
            <div className="text-xs font-mono text-zinc-500 pt-1 animate-pulse-subtle flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-zinc-600"></span>
              {statusText}
            </div>
          )}

          {errorMessage && (
            <div className="text-xs font-mono text-rose-400 bg-rose-950/30 border border-rose-900/50 rounded px-3 py-2 flex items-center justify-between">
              <span>{errorMessage}</span>
              <button
                type="button"
                onClick={() => setErrorMessage(null)}
                className="text-zinc-400 hover:text-zinc-200 ml-3 text-xs"
              >
                Dismiss
              </button>
            </div>
          )}
        </div>

        {/* Results Area */}
        <section className="space-y-6 pt-2">
          {results.length > 0 && results.map((item, idx) => (
            <DossierCard
              key={idx}
              item={item}
              isStreaming={isQuerying && idx === results.length - 1}
            />
          ))}
        </section>
      </main>

      <AuthModal
        isOpen={isAuthOpen}
        onClose={() => setIsAuthOpen(false)}
        onSuccess={(u) => setUser(u)}
      />
    </div>
  );
}

export default App;
