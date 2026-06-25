import { clsx } from 'clsx';

/**
 * Concatenate Tailwind class names conditionally.
 * Thin wrapper around `clsx` so callers have a single import path.
 *
 * @param  {...any} inputs - Anything `clsx` accepts (strings, arrays, objects).
 * @returns {string} The merged className string.
 *
 * @example
 *   cn('p-2', isActive && 'bg-brand-500', { 'opacity-50': disabled })
 */
export const cn = (...inputs) => clsx(inputs);
