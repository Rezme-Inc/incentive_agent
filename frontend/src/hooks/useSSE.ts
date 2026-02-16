import { useEffect, useState, useRef } from 'react';
import { getDiscoveryStatus } from '../services/api';
import type { DiscoveryStatus } from '../services/types';

interface UseSSEOptions {
  sessionId: string | null;
  enabled?: boolean;
}

interface UseSSEResult {
  status: DiscoveryStatus | null;
  graphData: { nodes: any[]; edges: any[] };
  runningNode: string | null;
  isConnected: boolean;
  error: Error | null;
}

const POLL_INTERVAL = 2000; // Poll every 2 seconds

export function useSSE({
  sessionId,
  enabled = true,
}: UseSSEOptions): UseSSEResult {
  const [status, setStatus] = useState<DiscoveryStatus | null>(null);
  const [graphData, setGraphData] = useState<{ nodes: any[]; edges: any[] }>({ nodes: [], edges: [] });
  const [runningNode, setRunningNode] = useState<string | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const intervalRef = useRef<number | null>(null);
  const isCompletedRef = useRef<boolean>(false);
  const errorCountRef = useRef<number>(0);
  const MAX_CONSECUTIVE_ERRORS = 3;

  useEffect(() => {
    if (!sessionId || !enabled) {
      return;
    }

    // Reset completion ref for new session
    isCompletedRef.current = false;

    const pollStatus = async () => {
      try {
        const currentStatus = await getDiscoveryStatus(sessionId);
        setStatus(currentStatus);
        setIsConnected(true);
        setError(null);
        errorCountRef.current = 0; // Reset on success

        // Update running node based on current step
        if (currentStatus.status === 'started' || currentStatus.status === 'routing' || currentStatus.status === 'discovering') {
          setRunningNode('government_discovery');
        } else if (currentStatus.status === 'searching') {
          // Determine which search is running
          const searchProgress = currentStatus.search_progress;
          const runningSearches = Object.entries(searchProgress).filter(
            ([_, progress]) => progress === 'running'
          );
          if (runningSearches.length > 0) {
            setRunningNode(runningSearches[0][0]);
          }
        } else if (currentStatus.status === 'merging') {
          setRunningNode('merge');
        } else {
          setRunningNode(null);
        }

        // Update graph data for visualization
        const nodes: any[] = [];
        const edges: any[] = [];

        // Add government discovery node
        // Status progression: started/routing → discovering → searching/merging/completed
        const govDiscoveryStatus = (() => {
          const s = currentStatus.status;
          if (s === 'started' || s === 'routing') return 'running';
          if (s === 'discovering') return 'running';
          if (s === 'failed') return 'failed';
          return 'completed'; // searching, merging, completed
        })();
        nodes.push({
          id: 'gov_discovery',
          type: 'agent',
          name: 'Government Discovery',
          status: govDiscoveryStatus,
        });

        // Add search nodes
        const searchLevels = ['city', 'county', 'state', 'federal'] as const;
        searchLevels.forEach((level) => {
          const progress = currentStatus.search_progress[level];
          nodes.push({
            id: `${level}_search`,
            type: 'agent',
            name: `${level.charAt(0).toUpperCase() + level.slice(1)} Search`,
            status: progress === 'completed' ? 'completed' : progress === 'running' ? 'running' : 'pending',
          });
          edges.push({
            id: `gov_to_${level}`,
            source: 'gov_discovery',
            target: `${level}_search`,
          });
        });

        // Add merge node - always show it, starting as pending
        const mergeStatus = currentStatus.status === 'merging' 
          ? 'running' 
          : currentStatus.status === 'completed' 
          ? 'completed' 
          : 'pending';
        
        nodes.push({
          id: 'merge',
          type: 'agent',
          name: 'Merge & Deduplicate',
          status: mergeStatus,
        });
        
        searchLevels.forEach((level) => {
          edges.push({
            id: `${level}_to_merge`,
            source: `${level}_search`,
            target: 'merge',
          });
        });

        setGraphData({ nodes, edges });

        // Stop polling if completed or failed
        if (currentStatus.status === 'completed' || currentStatus.status === 'failed') {
          isCompletedRef.current = true;
          setIsConnected(false);
          if (intervalRef.current) {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
          }
        }
      } catch (err) {
        errorCountRef.current += 1;
        console.error(`Failed to poll status (attempt ${errorCountRef.current}/${MAX_CONSECUTIVE_ERRORS}):`, err);
        setError(err instanceof Error ? err : new Error('Failed to fetch status'));
        setIsConnected(false);

        // Stop polling after too many consecutive errors (e.g., stale session 404s)
        if (errorCountRef.current >= MAX_CONSECUTIVE_ERRORS) {
          console.warn('Stopping poll — too many consecutive errors (session likely expired)');
          if (intervalRef.current) {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
          }
        }
      }
    };

    // Initial poll
    pollStatus();

    // Set up polling interval
    if (!isCompletedRef.current) {
      intervalRef.current = window.setInterval(pollStatus, POLL_INTERVAL);
    }

    // Cleanup function
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [sessionId, enabled]);

  return { status, graphData, runningNode, isConnected, error };
}
