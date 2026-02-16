import { createContext, useContext, useState, useCallback, useEffect } from 'react';
import type { ReactNode } from 'react';

const DEV_MODE_KEY = 'bgc_agent_dev_mode';

interface DevModeContextType {
  devMode: boolean;
  toggleDevMode: () => void;
  setDevMode: (enabled: boolean) => void;
  expandedNodes: string[];
  toggleNodeExpanded: (nodeId: string) => void;
  setExpandedNodes: (nodes: string[]) => void;
}

const DevModeContext = createContext<DevModeContextType | null>(null);

export const useDevMode = () => {
  const context = useContext(DevModeContext);
  if (!context) {
    throw new Error('useDevMode must be used within a DevModeProvider');
  }
  return context;
};

interface DevModeProviderProps {
  children: ReactNode;
}

export const DevModeProvider = ({ children }: DevModeProviderProps) => {
  const [devMode, setDevModeState] = useState<boolean>(() => {
    // Initialize from localStorage
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem(DEV_MODE_KEY);
      return stored === 'true';
    }
    return false;
  });

  const [expandedNodes, setExpandedNodes] = useState<string[]>([]);

  // Persist dev mode to localStorage
  useEffect(() => {
    localStorage.setItem(DEV_MODE_KEY, String(devMode));
  }, [devMode]);

  const toggleDevMode = useCallback(() => {
    setDevModeState((prev) => !prev);
  }, []);

  const setDevMode = useCallback((enabled: boolean) => {
    setDevModeState(enabled);
  }, []);

  const toggleNodeExpanded = useCallback((nodeId: string) => {
    setExpandedNodes((prev) => {
      if (prev.includes(nodeId)) {
        return prev.filter((id) => id !== nodeId);
      }
      return [...prev, nodeId];
    });
  }, []);

  const value: DevModeContextType = {
    devMode,
    toggleDevMode,
    setDevMode,
    expandedNodes,
    toggleNodeExpanded,
    setExpandedNodes,
  };

  return (
    <DevModeContext.Provider value={value}>{children}</DevModeContext.Provider>
  );
};
