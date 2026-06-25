/**
 * Fallback shown by <Suspense> while a lazy-loaded route chunk downloads
 * (main.jsx — optimize_Plan.html §1.1). Generic on purpose: it covers the
 * gap before React even knows which page is loading.
 */
const PageSkeleton = () => (
  <div className="flex h-full w-full flex-col gap-4 p-6 animate-pulse">
    <div className="h-8 w-1/3 rounded-md bg-neutral-200 dark:bg-neutral-800" />
    <div className="h-4 w-2/3 rounded-md bg-neutral-200 dark:bg-neutral-800" />
    <div className="mt-4 h-40 w-full rounded-lg bg-neutral-200 dark:bg-neutral-800" />
    <div className="h-4 w-1/2 rounded-md bg-neutral-200 dark:bg-neutral-800" />
    <div className="h-4 w-5/6 rounded-md bg-neutral-200 dark:bg-neutral-800" />
  </div>
);

export default PageSkeleton;
