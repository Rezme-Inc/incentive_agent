import { createContext, useContext, useState, useCallback } from 'react';
import type { ReactNode } from 'react';
import type { WizardState } from '../services/types';

const INITIAL_STATE: WizardState = {
  address: '',
  sessionId: null,
  selectedPrograms: [],
};

interface WizardContextType {
  state: WizardState;
  setAddress: (address: string) => void;
  setSessionId: (sessionId: string | null) => void;
  setSelectedPrograms: (programIds: string[]) => void;
  addSelectedProgram: (programId: string) => void;
  removeSelectedProgram: (programId: string) => void;
  resetWizard: () => void;
  canProceed: () => boolean;
}

const WizardContext = createContext<WizardContextType | null>(null);

export const useWizard = () => {
  const context = useContext(WizardContext);
  if (!context) {
    throw new Error('useWizard must be used within a WizardProvider');
  }
  return context;
};

interface WizardProviderProps {
  children: ReactNode;
}

export const WizardProvider = ({ children }: WizardProviderProps) => {
  const [state, setState] = useState<WizardState>(INITIAL_STATE);

  const setAddress = useCallback((address: string) => {
    setState((prev) => ({ ...prev, address }));
  }, []);

  const setSessionId = useCallback((sessionId: string | null) => {
    setState((prev) => ({ ...prev, sessionId }));
  }, []);

  const setSelectedPrograms = useCallback((programIds: string[]) => {
    setState((prev) => ({ ...prev, selectedPrograms: programIds }));
  }, []);

  const addSelectedProgram = useCallback((programId: string) => {
    setState((prev) => ({
      ...prev,
      selectedPrograms: [...prev.selectedPrograms, programId],
    }));
  }, []);

  const removeSelectedProgram = useCallback((programId: string) => {
    setState((prev) => ({
      ...prev,
      selectedPrograms: prev.selectedPrograms.filter((id) => id !== programId),
    }));
  }, []);

  const resetWizard = useCallback(() => {
    setState(INITIAL_STATE);
  }, []);

  const canProceed = useCallback((): boolean => {
    return state.address.trim().length > 0;
  }, [state.address]);

  const value: WizardContextType = {
    state,
    setAddress,
    setSessionId,
    setSelectedPrograms,
    addSelectedProgram,
    removeSelectedProgram,
    resetWizard,
    canProceed,
  };

  return (
    <WizardContext.Provider value={value}>{children}</WizardContext.Provider>
  );
};
