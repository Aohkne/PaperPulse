import { forwardRef } from 'react';
import { cn } from '@/shared/utils/cn';

/**
 * Reusable text input.
 *
 * @param {object} props
 * @param {string} [props.label] - Optional label rendered above the input.
 * @param {string} [props.error] - Error message; turns the border red when present.
 * @param {string} [props.className] - Extra utility classes.
 * @param {React.InputHTMLAttributes<HTMLInputElement>} props - All other native input props.
 */
const Input = forwardRef(({ label, error, className, id, ...rest }, ref) => {
  const inputId = id ?? `input-${Math.random().toString(36).slice(2, 8)}`;

  return (
    <div className="flex flex-col gap-1">
      {label && (
        <label htmlFor={inputId} className="text-sm font-medium text-gray-700">
          {label}
        </label>
      )}
      <input
        id={inputId}
        ref={ref}
        className={cn(
          'px-3 py-2 text-sm rounded-lg border bg-white text-gray-900 placeholder-gray-400',
          'focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent',
          'transition-colors',
          error ? 'border-red-500' : 'border-gray-300',
          className
        )}
        {...rest}
      />
      {error && <span className="text-xs text-red-600">{error}</span>}
    </div>
  );
});

Input.displayName = 'Input';

export default Input;
