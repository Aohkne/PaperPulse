import { Icon } from '@iconify/react';
import { cn } from '@/shared/utils/cn';

/**
 * Reusable button component.
 *
 * @param {object} props
 * @param {'primary'|'secondary'|'ghost'} [props.variant='primary']
 * @param {'sm'|'md'|'lg'} [props.size='md']
 * @param {boolean} [props.loading=false] - Shows a spinner and disables the button.
 * @param {boolean} [props.disabled=false]
 * @param {string} [props.icon] - Iconify name (e.g. "mdi:magnify") shown before the label.
 * @param {React.ReactNode} props.children
 * @param {string} [props.className] - Extra utility classes (merged via `cn`).
 * @param {React.ButtonHTMLAttributes<HTMLButtonElement>} props - All other native button props.
 */
const Button = ({
  variant = 'primary',
  size = 'md',
  loading = false,
  disabled = false,
  icon,
  children,
  className,
  type = 'button',
  ...rest
}) => {
  const base =
    'inline-flex items-center justify-center gap-2 font-medium rounded-lg transition-colors ' +
    'focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-brand-500 ' +
    'disabled:opacity-50 disabled:cursor-not-allowed';

  const variants = {
    primary: 'bg-brand-600 text-white hover:bg-brand-700',
    secondary: 'bg-gray-200 text-gray-900 hover:bg-gray-300',
    ghost: 'bg-transparent text-gray-700 hover:bg-gray-100',
  };

  const sizes = {
    sm: 'px-3 py-1.5 text-sm',
    md: 'px-4 py-2 text-sm',
    lg: 'px-5 py-2.5 text-base',
  };

  return (
    <button
      type={type}
      disabled={disabled || loading}
      className={cn(base, variants[variant], sizes[size], className)}
      {...rest}
    >
      {loading ? (
        <Icon icon="mdi:loading" className="w-4 h-4 animate-spin" />
      ) : icon ? (
        <Icon icon={icon} className="w-4 h-4" />
      ) : null}
      {children}
    </button>
  );
};

export default Button;
