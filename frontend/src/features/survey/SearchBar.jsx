import Input from '@/shared/components/ui/Input';
import Button from '@/shared/components/ui/Button';

/**
 * Search bar for the literature survey.
 *
 * Pure presentational component — receives everything it needs via props
 * and delegates all state mutations to the parent (which talks to the store).
 *
 * @param {object} props
 * @param {string} props.value - Current query text.
 * @param {(value: string) => void} props.onChange - Called on every keystroke.
 * @param {() => void} props.onSubmit - Called when the user submits the form.
 * @param {boolean} props.loading - Disables the submit button while a search is running.
 * @param {string} [props.error] - Optional error message shown under the input.
 */
const SearchBar = ({ value, onChange, onSubmit, loading, error }) => {
  const handleSubmit = (event) => {
    event.preventDefault();
    onSubmit();
  };

  return (
    <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row gap-3 w-full">
      <div className="flex-1">
        <Input
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder="e.g. transformer-based literature review assistants"
          error={error}
          aria-label="Research question"
        />
      </div>
      <Button type="submit" icon="mdi:magnify" loading={loading} className="sm:self-start">
        Search
      </Button>
    </form>
  );
};

export default SearchBar;
