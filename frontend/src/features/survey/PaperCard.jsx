import { useState } from 'react';
import { Icon } from '@iconify/react';
import { cn } from '@/shared/utils/cn';
import Button from '@/shared/components/ui/Button';

const buildBibTeX = (paper) => {
  const firstAuthor =
    paper.authors[0]?.split(',')[0]?.toLowerCase().replace(/\s/g, '') ?? 'unknown';
  const key = `${firstAuthor}${paper.year}`;
  const authorStr = paper.authors.join(' and ');
  const doiLine = paper.doi ? `,\n  doi = {${paper.doi}}` : '';
  return `@article{${key},\n  title = {${paper.title}},\n  author = {${authorStr}},\n  year = {${paper.year}}${doiLine}\n}`;
};

const PaperCard = ({ paper, index }) => {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(buildBibTeX(paper));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleOpenSource = () => {
    const url = paper.doi ? `https://doi.org/${paper.doi}` : paper.url;
    window.open(url, '_blank', 'noopener,noreferrer');
  };

  return (
    <li className="bg-white border border-gray-200 rounded-xl shadow-sm hover:border-brand-500 transition-colors">
      <div className="p-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <h3 className="text-base font-semibold text-gray-900 leading-snug">
              {index + 1}. {paper.title}
            </h3>
            <p className="text-sm text-gray-500 mt-1">
              {paper.authors.join(', ')} · {paper.year}
              {paper.venue && (
                <span>
                  {' '}
                  · <em>{paper.venue}</em>
                </span>
              )}
            </p>
          </div>

          <span className="flex items-center gap-1 text-xs bg-brand-50 text-brand-600 border border-brand-100 px-2 py-1 rounded-full whitespace-nowrap shrink-0">
            <Icon icon="mdi:format-quote-close" className="w-3.5 h-3.5" />
            {paper.citations}
          </span>
        </div>

        <div className="mt-3">
          <p className={cn('text-sm text-gray-700 leading-relaxed', !expanded && 'line-clamp-2')}>
            {paper.abstract}
          </p>
          <button
            onClick={() => setExpanded(!expanded)}
            className="mt-1 flex items-center gap-0.5 text-xs text-brand-600 hover:text-brand-700"
          >
            <Icon icon={expanded ? 'mdi:chevron-up' : 'mdi:chevron-down'} className="w-4 h-4" />
            {expanded ? 'Show less' : 'Show more'}
          </button>
        </div>
      </div>

      <div className="flex items-center gap-1 px-4 py-2 border-t border-gray-100 bg-gray-50 rounded-b-xl">
        <Button
          variant="ghost"
          size="sm"
          icon={copied ? 'mdi:check' : 'mdi:content-copy'}
          onClick={handleCopy}
          className={copied ? 'text-green-600' : ''}
        >
          {copied ? 'Copied!' : 'Copy BibTeX'}
        </Button>
        {(paper.doi || paper.url) && (
          <Button variant="ghost" size="sm" icon="mdi:open-in-new" onClick={handleOpenSource}>
            View paper
          </Button>
        )}
      </div>
    </li>
  );
};

export default PaperCard;
