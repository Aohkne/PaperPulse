import { useEffect, useRef, useState } from 'react';
import { Icon } from '@iconify/react';
import { useSurveyStore } from '@/shared/store/useSurveyStore';

const SearchHistory = () => {
  const history = useSurveyStore((state) => state.history);
  const runSearch = useSurveyStore((state) => state.runSearch);
  const setQuery = useSurveyStore((state) => state.setQuery);
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  if (!history.length) return null;

  const handleSelect = (q) => {
    setQuery(q);
    runSearch(q);
    setOpen(false);
  };

  return (
    <div className="relative self-start" ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-800 px-2 py-1 rounded-lg hover:bg-gray-100 transition-colors"
      >
        <Icon icon="mdi:history" className="w-4 h-4" />
        Recent searches
        <Icon icon={open ? 'mdi:chevron-up' : 'mdi:chevron-down'} className="w-3.5 h-3.5" />
      </button>

      {open && (
        <div className="absolute top-full left-0 mt-1 w-80 bg-white border border-gray-200 rounded-xl shadow-lg z-10 overflow-hidden">
          <p className="px-3 py-2 text-xs font-medium text-gray-400 uppercase tracking-wide border-b border-gray-100">
            Recent
          </p>
          <ul>
            {history.map((q, i) => (
              <li key={i}>
                <button
                  onClick={() => handleSelect(q)}
                  className="w-full text-left px-3 py-2.5 text-sm text-gray-700 hover:bg-brand-50 hover:text-brand-700 flex items-center gap-2.5 transition-colors"
                >
                  <Icon icon="mdi:magnify" className="w-4 h-4 text-gray-400 shrink-0" />
                  <span className="truncate">{q}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

export default SearchHistory;
