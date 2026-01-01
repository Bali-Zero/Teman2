import useSWR from 'swr';

// Base fetcher function - simple wrapper around fetch
const fetcher = async (url: string) => {
  const res = await fetch(url);
  if (!res.ok) {
    const error = new Error('An error occurred while fetching the data.');
    // info property attaches extra info to error object
    // @ts-expect-error - Custom property on Error object
    error.info = await res.json();
    // @ts-expect-error - Custom property on Error object
    error.status = res.status;
    throw error;
  }
  return res.json();
};

// Generic hook for data fetching
// Usage: const { data, isLoading, error } = useData('/api/user/profile');
export function useData<T>(url: string | null) {
  const { data, error, isLoading, mutate } = useSWR<T>(url, fetcher, {
    // SWR Configuration for "Snappy UX"
    revalidateOnFocus: false, // Don't revalidate when window gets focus (distracting)
    revalidateOnReconnect: true,
    dedupingInterval: 5000, // Dedup requests within 5s
    keepPreviousData: true, // Keep old data while loading new data
  });

  return {
    data,
    isLoading,
    isError: error,
    mutate,
  };
}
