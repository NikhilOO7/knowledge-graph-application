import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from './api';
import type { Bucket } from './types';

interface BucketContextValue {
  buckets: Bucket[];
  selectedBucketId: string | null;
  selectedBucket: Bucket | null;
  setSelectedBucketId: (id: string | null) => void;
  isLoading: boolean;
}

const BucketCtx = createContext<BucketContextValue | undefined>(undefined);

const STORAGE_KEY = 'kg.selectedBucketId';

export function BucketProvider({ children }: { children: ReactNode }) {
  const [selectedBucketId, setSelectedBucketIdState] = useState<string | null>(
    () => localStorage.getItem(STORAGE_KEY)
  );

  const { data, isLoading } = useQuery({
    queryKey: ['buckets'],
    queryFn: () => api.buckets.list(),
    refetchInterval: 5000,
  });

  const buckets = data?.buckets ?? [];

  const setSelectedBucketId = (id: string | null) => {
    setSelectedBucketIdState(id);
    if (id) localStorage.setItem(STORAGE_KEY, id);
    else localStorage.removeItem(STORAGE_KEY);
  };

  // Default selection to the first bucket once data loads; if the selected
  // bucket disappeared (e.g. deleted), fall back to the first one.
  useEffect(() => {
    if (buckets.length === 0) return;
    if (!selectedBucketId || !buckets.find((b) => b.id === selectedBucketId)) {
      setSelectedBucketId(buckets[0].id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [buckets.length]);

  const selectedBucket = buckets.find((b) => b.id === selectedBucketId) ?? null;

  return (
    <BucketCtx.Provider
      value={{ buckets, selectedBucketId, selectedBucket, setSelectedBucketId, isLoading }}
    >
      {children}
    </BucketCtx.Provider>
  );
}

export function useBucket() {
  const ctx = useContext(BucketCtx);
  if (!ctx) throw new Error('useBucket must be used within BucketProvider');
  return ctx;
}
