/**
 * useWebSocket Hook
 * 
 * Manages WebSocket connection for real-time notifications
 */

import { useEffect, useRef, useState } from 'react';
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

interface UseWebSocketOptions {
  onThumbnailReady?: (data: ThumbnailReadyMessage) => void;
  onMessage?: (message: WebSocketMessage) => void;
}

export function useWebSocket(options: UseWebSocketOptions = {}) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const optionsRef = useRef(options);
  const [backendUrl, setBackendUrl] = useState<string | null>(null);
  
  // Update options ref without triggering reconnection
  useEffect(() => {
    optionsRef.current = options;
  }, [options]);

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

    // Get WebSocket URL from backend URL
    const wsUrl = backendUrl.replace(/^http/, 'ws') + '/ws/notifications';

    const connect = () => {
      // Don't create new connection if one already exists
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        return;
      }

      try {
        const ws = new WebSocket(wsUrl);
        
        ws.onopen = () => {
          console.log('WebSocket connected');
        };

        ws.onmessage = (event) => {
          try {
            const message: WebSocketMessage = JSON.parse(event.data);
            
            // Handle thumbnail ready messages
            if (message.type === 'thumbnail_ready' && optionsRef.current.onThumbnailReady) {
              optionsRef.current.onThumbnailReady(message as ThumbnailReadyMessage);
            }
            
            // Call generic message handler
            if (optionsRef.current.onMessage) {
              optionsRef.current.onMessage(message);
            }
          } catch (error) {
            console.error('Failed to parse WebSocket message:', error);
          }
        };

        ws.onerror = (error) => {
          console.error('WebSocket error:', error);
        };

        ws.onclose = () => {
          console.log('WebSocket disconnected, reconnecting in 3s...');
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

  return {
    isConnected: wsRef.current?.readyState === WebSocket.OPEN,
  };
}
