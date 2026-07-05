import { Icon } from '@iconify/react';
import Button from '@/shared/components/ui/Button';

const ResultsHeader = ({ count, query, onClear }) => {
  if (!count) return null;

  return (
    <div className="flex items-center justify-between gap-4 px-4 py-3 bg-brand-50 border border-brand-100 rounded-xl">
      <div className="flex items-center gap-2 text-sm text-brand-700 min-w-0">
        <Icon icon="mdi:check-circle" className="w-4 h-4 text-brand-500 shrink-0" />
        <span className="truncate">
          Found <strong>{count}</strong> paper{count !== 1 ? 's' : ''} for: <em>"{query}"</em>
        </span>
      </div>
      <Button variant="ghost" size="sm" icon="mdi:close" onClick={onClear}>
        Clear
      </Button>
    </div>
  );
};

export default ResultsHeader;
