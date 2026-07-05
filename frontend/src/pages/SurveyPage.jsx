import { useEffect, useRef } from 'react';
import { Icon } from '@iconify/react';
import { useSurveyStore } from '@/shared/store/useSurveyStore';
import SearchBar from '@/features/survey/SearchBar';
import ResultsList from '@/features/survey/ResultsList';
import SearchHistory from '@/features/survey/SearchHistory';
import { friendlyError } from '@/shared/utils/errorMessage';

const BotAvatar = () => (
  <div className="w-8 h-8 rounded-full bg-[#6c27da] flex items-center justify-center shrink-0">
    <Icon icon="mdi:robot" className="w-4 h-4 text-[#ffd2a1]" />
  </div>
);

const WelcomeState = () => (
  <div className="flex flex-col items-center justify-center h-full gap-5 text-center px-4">
    <div className="w-16 h-16 rounded-2xl bg-[#6c27da] flex items-center justify-center shadow-lg">
      <Icon icon="mdi:book-open-page-variant" className="w-8 h-8 text-[#ffd2a1]" />
    </div>
    <div className="flex flex-col gap-2">
      <h2 className="text-2xl font-bold text-[#6c27da]">Hi, I'm PaperPulse</h2>
      <p className="text-sm text-[#ffd2a1] max-w-sm leading-relaxed">
        Ask me a research question and I'll find relevant papers, highlight key themes, and surface
        research gaps.
      </p>
    </div>
    <div className="flex flex-wrap justify-center gap-2 mt-2">
      {['transformer models in NLP', 'RAG vs fine-tuning LLMs', 'bias in clinical AI'].map(
        (hint) => (
          <ExampleChip key={hint} text={hint} />
        )
      )}
    </div>
  </div>
);

const ExampleChip = ({ text }) => {
  const setQuery = useSurveyStore((state) => state.setQuery);
  const runSearch = useSurveyStore((state) => state.runSearch);
  return (
    <button
      onClick={() => {
        setQuery(text);
        runSearch(text);
      }}
      className="text-xs px-3 py-1.5 rounded-full border border-[#ffd2a1]/40 text-[#ffd2a1]/80 hover:bg-[#ffd2a1]/10 hover:text-[#ffd2a1] transition-colors"
    >
      {text}
    </button>
  );
};

const UserBubble = ({ text }) => (
  <div className="flex justify-end">
    <div className="bg-[#6c27da] text-[#ffd2a1] rounded-2xl rounded-br-sm px-4 py-3 max-w-lg shadow-sm">
      <p className="text-sm leading-relaxed">{text}</p>
    </div>
  </div>
);

const ThinkingBubble = () => (
  <div className="flex items-end gap-3">
    <BotAvatar />
    <div className="bg-white/90 rounded-2xl rounded-bl-sm px-4 py-3 shadow-sm">
      <div className="flex items-center gap-2 text-[#0c6038]">
        <Icon icon="mdi:loading" className="w-4 h-4 animate-spin" />
        <span className="text-sm">Searching the literature…</span>
      </div>
    </div>
  </div>
);

const AssistantResponse = ({ results, count, query }) => (
  <div className="flex items-start gap-3">
    <BotAvatar />
    <div className="flex-1 min-w-0 flex flex-col gap-3">
      <div className="bg-white/90 rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm self-start">
        <p className="text-sm text-[#0c6038]">
          Found <strong>{count}</strong> paper{count !== 1 ? 's' : ''} for{' '}
          <em className="text-[#6c27da]">"{query}"</em>
        </p>
      </div>
      <ResultsList results={results} status="success" error={null} />
    </div>
  </div>
);

const ErrorBubble = ({ error }) => (
  <div className="flex items-end gap-3">
    <BotAvatar />
    <div className="bg-white/90 rounded-2xl rounded-bl-sm px-4 py-3 shadow-sm">
      <p className="text-sm text-red-600">{friendlyError(error, 'Something went wrong.')}</p>
    </div>
  </div>
);

const SurveyPage = () => {
  const query = useSurveyStore((state) => state.query);
  const setQuery = useSurveyStore((state) => state.setQuery);
  const runSearch = useSurveyStore((state) => state.runSearch);
  const results = useSurveyStore((state) => state.results);
  const status = useSurveyStore((state) => state.status);
  const error = useSurveyStore((state) => state.error);
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [status, results.length]);

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Scrollable chat area */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        {status === 'idle' && <WelcomeState />}

        {status !== 'idle' && (
          <div className="flex flex-col gap-5 max-w-3xl mx-auto">
            {(status === 'success' || status === 'error') && <UserBubble text={query} />}
            {status === 'loading' && <ThinkingBubble />}
            {status === 'success' && (
              <AssistantResponse results={results} count={results.length} query={query} />
            )}
            {status === 'error' && <ErrorBubble error={error} />}
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Fixed bottom input bar */}
      <div className="shrink-0 border-t border-[#52551f] bg-[#6b6e30]/60 backdrop-blur-sm px-4 py-4">
        <div className="max-w-3xl mx-auto flex flex-col gap-2">
          <SearchHistory />
          <SearchBar
            value={query}
            onChange={setQuery}
            onSubmit={() => runSearch()}
            loading={status === 'loading'}
            error={null}
          />
        </div>
      </div>
    </div>
  );
};

export default SurveyPage;
