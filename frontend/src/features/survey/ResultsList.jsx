import { Icon } from '@iconify/react';
import PaperCard from './PaperCard';

const ResultsList = ({ results, status, error }) => {
  if (status === 'loading') {
    return (
      <div className="flex items-center justify-center gap-2 text-gray-500 py-12">
        <Icon icon="mdi:loading" className="w-5 h-5 animate-spin" />
        <span>Searching the literature…</span>
      </div>
    );
  }

  if (status === 'error') {
    return (
      <div className="flex items-center gap-2 text-red-600 py-6">
        <Icon icon="mdi:alert-circle" className="w-5 h-5" />
        <span>{error ?? 'Something went wrong.'}</span>
      </div>
    );
  }

  if (!results.length) {
    return (
      <div className="flex flex-col items-center gap-2 text-gray-400 py-12 text-center">
        <Icon icon="mdi:book-search" className="w-10 h-10" />
        <p>No results yet. Try running a search above.</p>
      </div>
    );
  }

  return (
    <ul className="flex flex-col gap-3">
      {results.map((paper, index) => (
        <PaperCard key={paper.id} paper={paper} index={index} />
      ))}
    </ul>
  );
};

export default ResultsList;
