import React, { createContext, useContext, useState, ReactNode } from 'react';

export interface UserPreferences {
  phoneNumber?: string;
  name?: string;
  birthday?: string;
  preferences: string[];
  hungerLevel: string;
  drinks: string[];
  restrictions: string[];
}

interface PreferencesContextType {
  preferences: UserPreferences | null;
  updatePreferences: (prefs: Partial<UserPreferences>) => void;
}

const PreferencesContext = createContext<PreferencesContextType | undefined>(undefined);

export function PreferencesProvider({ children }: { children: ReactNode }) {
  const [preferences, setPreferences] = useState<UserPreferences | null>(null);

  const updatePreferences = (prefs: Partial<UserPreferences>) => {
    setPreferences(prev => prev ? { ...prev, ...prefs } : {
      preferences: [],
      hungerLevel: '',
      drinks: [],
      restrictions: [],
      ...prefs,
    });
  };

  return (
    <PreferencesContext.Provider value={{ preferences, updatePreferences }}>
      {children}
    </PreferencesContext.Provider>
  );
}

export function usePreferences() {
  const context = useContext(PreferencesContext);
  if (!context) {
    throw new Error('usePreferences must be used within PreferencesProvider');
  }
  return context;
}