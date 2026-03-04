/**
 * WebSocket Context
 * 
 * Provides a singleton WebSocket connection for the entire app
 */

import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { getBackendUrl } from '../services/electron';

interface ThumbnailReadyMessage {
  type: 'thumbnail_ready';
  video_id: string;
  timecode: number;
  thumbnail_url: string;
  timestamp: string;
}

interface WebSocketMessage {
  type: string;
  [key: string]: any;
}

type MessageHandler = (message: WebSocketMessage) => void;

interface WebSocketContextValue {
  isConnected: boolean;
  subscribe: (handler: MessageHandler) => () => void;
}

const WebSocketContext = createContext<WebSocketContextValue | null>(null);

export function WebSocketProvider({ children }: { children: ReactNode }) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const handlersRef = useRef<Set<MessageHandler>>(new Set());
  const [isConnected, setIsConnected] = useState(false);
  const [backendUrl, setBackendUrl] = useState<string | null>(null);

  // Get backend URL (handles both Electron and web)
  useEffect(() => {
    getBackendUrl().then(url => {
      setBackendUrl(url);
    });
  }, []);

  useEffect(() => {
    // Wait for backend URL to be resolved
    if (!backendUrl) {
      return;
    }

    const wsUrl = backendUrl.replace(/^http/, 'ws') + '/ws/notifications';

    const connect = () => {
      // Don't create new connection if one already exists
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        return;
      }

      try {
        const ws = new WebSocket(wsUrl);
        
        ws.onopen = () => {
          console.log('WebSocket connected to:', wsUrl);
          setIsConnected(true);
        };

        ws.onmessage = (event) => {
          try {
            const message: WebSocketMessage = JSON.parse(event.data);
            
            // Notify all subscribers
            handlersRef.current.forEach(handler => {
              try {
                handler(message);
              } catch (error) {
                console.error('Error in WebSocket message handler:', error);
              }
            });
          } catch (error) {
            console.error('Failed to parse WebSocket message:', error);
          }
        };

        ws.onerror = (error) => {
          console.error('WebSocket error:', error);
        };

        ws.onclose = () => {
          console.log('WebSocket disconnected, reconnecting in 3s...');
          setIsConnected(false);
          wsRef.current = null;
          
          // Reconnect after 3 seconds
          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, 3000);
        };

        wsRef.current = ws;
      } catch (error) {
        console.error('Failed to create WebSocket:', error);
      }
    };

    connect();

    return () => {
      // Cleanup on unmount
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [backendUrl]); // Reconnect when backend URL changes

  const subscribe = (handler: MessageHandler) => {
    handlersRef.current.add(handler);
    
    // Return unsubscribe function
    return () => {
      handlersRef.current.delete(handler);
    };
  };

  return (
    <WebSocketContext.Provider value={{ isConnected, subscribe }}>
      {children}
    </WebSocketContext.Provider>
  );
}

export function useWebSocketContext() {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error('useWebSocketContext must be used within WebSocketProvider');
  }
  return context;
}

export function useThumbnailUpdates(onThumbnailReady: (data: ThumbnailReadyMessage) => void) {
  const { subscribe } = useWebSocketContext();

  useEffect(() => {
    const unsubscribe = subscribe((message) => {
      if (message.type === 'thumbnail_ready') {
        onThumbnailReady(message as ThumbnailReadyMessage);
      }
    });

    return unsubscribe;
  }, [subscribe, onThumbnailReady]);
}
