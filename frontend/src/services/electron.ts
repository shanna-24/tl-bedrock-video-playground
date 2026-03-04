// Electron integration service
// Detects if running in Electron and provides access to Electron APIs

interface ElectronAPI {
  getBackendUrl: () => Promise<string>;
  getAppVersion: () => Promise<string>;
  getConfigPath: () => Promise<string>;
  platform: string;
}

declare global {
  interface Window {
    electron?: ElectronAPI;
  }
}

export const isElectron = (): boolean => {
  return typeof window !== 'undefined' && window.electron !== undefined;
};

export const getBackendUrl = async (): Promise<string> => {
  if (isElectron() && window.electron) {
    return await window.electron.getBackendUrl();
  }
  // Fallback to environment variable or default
  return import.meta.env.VITE_API_URL || 'http://localhost:8000';
};

export const getAppVersion = async (): Promise<string> => {
  if (isElectron() && window.electron) {
    return await window.electron.getAppVersion();
  }
  return 'web';
};

export const getConfigPath = async (): Promise<string | null> => {
  if (isElectron() && window.electron) {
    return await window.electron.getConfigPath();
  }
  return null;
};

export const getPlatform = (): string => {
  if (isElectron() && window.electron) {
    return window.electron.platform;
  }
  return 'web';
};
