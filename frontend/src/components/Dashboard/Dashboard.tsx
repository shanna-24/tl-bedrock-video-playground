import logoBlack from '../../assets/twelvelabs-logo-black.png';
import logoWhite from '../../assets/twelvelabs-logo-white.png';

/**
 * Dashboard Component
 * 
 * Main dashboard view for authenticated users.
 * Integrates index management, video upload, search, and analysis features.
 * 
 * Validates: Requirements 5.1, 8.3, 8.4
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth } from '../../hooks/useAuth';
import { useIndexes } from '../../hooks/useIndexes';
import { useSearch } from '../../hooks/useSearch';
import { useVideos } from '../../hooks/useVideos';
import { useWebSocketContext } from '../../contexts/WebSocketContext';
import { analysisApi, complianceApi } from '../../services/api';
import IndexList from '../Index/IndexList';
import VideoUpload from '../Video/VideoUpload';
import VideoList from '../Video/VideoList';
import VideoPlayerPopup from '../Video/VideoPlayerPopup';
import SearchBar from '../Search/SearchBar';
import SearchResults from '../Search/SearchResults';
import AnalysisForm from '../Analysis/AnalysisForm';
import AnalysisResults from '../Analysis/AnalysisResults';
import ComplianceForm from '../Compliance/ComplianceForm';
import ComplianceResults from '../Compliance/ComplianceResults';
import ThemeToggle from '../ThemeToggle/ThemeToggle';
import type { Video, VideoClip, AnalysisResult, ComplianceResult, ComplianceParams } from '../../types';

type ActiveTab = 'videos' | 'search' | 'analysis' | 'compliance';

export default function Dashboard() {
  const { logout } = useAuth();
  const { indexes, selectedIndex, selectIndex, refreshIndexes, maxIndexes } = useIndexes();
  const { searchResults, query, searchTime, isSearching, error: searchError, search, clearResults } = useSearch();
  const { videos, refreshVideos } = useVideos(selectedIndex?.id || null);
  const { subscribe, isConnected } = useWebSocketContext();
  
  const [activeTab, setActiveTab] = useState<ActiveTab>('videos');
  const [selectedVideo, setSelectedVideo] = useState<Video | null>(null);
  const [selectedClip, setSelectedClip] = useState<VideoClip | null>(null);
  const [selectedClipVideo, setSelectedClipVideo] = useState<Video | null>(null);
  const [reelUrl, setReelUrl] = useState<string | null>(null);
  const [videoRefreshTrigger, setVideoRefreshTrigger] = useState(0);
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [analysisProgress, setAnalysisProgress] = useState<string>('');
  const [complianceStartTime, setComplianceStartTime] = useState<number | undefined>(undefined);
  
  // Compliance state
  const [complianceResult, setComplianceResult] = useState<ComplianceResult | null>(null);
  const [complianceVideoId, setComplianceVideoId] = useState<string | null>(null);
  const [isCheckingCompliance, setIsCheckingCompliance] = useState(false);
  const [complianceError, setComplianceError] = useState<string | null>(null);
  const [complianceProgress, setComplianceProgress] = useState<string>('');
  const [complianceParams, setComplianceParams] = useState<ComplianceParams | null>(null);
  
  // Settings state
  const [showSettings, setShowSettings] = useState(false);
  const [visibleTabs, setVisibleTabs] = useState({
    search: true,
    analysis: true,
    compliance: true,
  });
  const settingsRef = useRef<HTMLDivElement>(null);
  
  // Refs for tracking and cancelling ongoing analysis
  const analysisAbortControllerRef = useRef<AbortController | null>(null);
  const analysisCorrelationIdRef = useRef<string | null>(null);
  
  // Refs for tracking and cancelling ongoing compliance check
  const complianceAbortControllerRef = useRef<AbortController | null>(null);
  const complianceCorrelationIdRef = useRef<string | null>(null);

  // Function to cancel any ongoing analysis
  const cancelOngoingAnalysis = useCallback(async () => {
    // Abort the fetch request
    if (analysisAbortControllerRef.current) {
      analysisAbortControllerRef.current.abort();
      analysisAbortControllerRef.current = null;
    }
    
    // Cancel on the backend
    if (analysisCorrelationIdRef.current) {
      try {
        await analysisApi.cancelAnalysis(analysisCorrelationIdRef.current);
      } catch (error) {
        // Ignore errors when cancelling - the analysis may have already completed
        console.debug('Analysis cancellation:', error);
      }
      analysisCorrelationIdRef.current = null;
    }
    
    // Reset analysis state
    setIsAnalyzing(false);
    setAnalysisProgress('');
  }, []);

  // Function to cancel any ongoing compliance check
  const cancelOngoingCompliance = useCallback(async () => {
    // Abort the fetch request
    if (complianceAbortControllerRef.current) {
      complianceAbortControllerRef.current.abort();
      complianceAbortControllerRef.current = null;
    }
    complianceCorrelationIdRef.current = null;
    
    // Reset compliance state
    setIsCheckingCompliance(false);
    setComplianceProgress('');
  }, []);

  // Load compliance params on mount
  useEffect(() => {
    const loadComplianceParams = async () => {
      try {
        const params = await complianceApi.getParams();
        setComplianceParams(params);
      } catch (error) {
        console.error('Failed to load compliance params:', error);
      }
    };
    loadComplianceParams();
  }, []);

  // Clear selected video/clip and search results when index changes or is deleted
  useEffect(() => {
    // Cancel any ongoing analysis when index changes
    cancelOngoingAnalysis();
    cancelOngoingCompliance();
    
    setSelectedVideo(null);
    setSelectedClip(null);
    setSelectedClipVideo(null);
    setReelUrl(null);
    clearResults();
    setAnalysisResult(null);
    setAnalysisError(null);
    setComplianceResult(null);
    setComplianceVideoId(null);
    setComplianceError(null);
    setActiveTab('videos');
  }, [selectedIndex?.id, cancelOngoingAnalysis, cancelOngoingCompliance]);

  // Switch to Videos tab if no videos and user is on Search or Analysis
  useEffect(() => {
    if (videos.length === 0 && (activeTab === 'search' || activeTab === 'analysis')) {
      setActiveTab('videos');
    }
  }, [videos.length, activeTab]);

  // Close settings popup when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (settingsRef.current && !settingsRef.current.contains(event.target as Node)) {
        setShowSettings(false);
      }
    };
    if (showSettings) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [showSettings]);

  // Switch to videos tab if current tab becomes hidden
  useEffect(() => {
    if (activeTab !== 'videos' && !visibleTabs[activeTab as keyof typeof visibleTabs]) {
      setActiveTab('videos');
    }
  }, [visibleTabs, activeTab]);

  // Hide video playback when switching tabs
  useEffect(() => {
    setSelectedVideo(null);
    setSelectedClip(null);
    setSelectedClipVideo(null);
    setReelUrl(null);
  }, [activeTab]);

  // Reset search results when leaving the search tab
  useEffect(() => {
    if (activeTab !== 'search') {
      clearResults();
    }
  }, [activeTab, clearResults]);

  // Reset analysis results when leaving the analysis tab
  useEffect(() => {
    if (activeTab !== 'analysis') {
      // Cancel any ongoing analysis when navigating away from analysis tab
      cancelOngoingAnalysis();
      setAnalysisResult(null);
      setAnalysisError(null);
      setAnalysisProgress('');
    }
  }, [activeTab, cancelOngoingAnalysis]);

  // Reset compliance results when leaving the compliance tab
  useEffect(() => {
    if (activeTab !== 'compliance') {
      // Cancel any ongoing compliance check when navigating away
      cancelOngoingCompliance();
      setComplianceResult(null);
      setComplianceVideoId(null);
      setComplianceError(null);
      setComplianceProgress('');
    }
  }, [activeTab, cancelOngoingCompliance]);

  const handleLogout = async () => {
    try {
      // Cancel any ongoing analysis before logging out
      await cancelOngoingAnalysis();
      await cancelOngoingCompliance();
      await logout();
    } catch (error) {
      console.error('Logout error:', error);
    }
  };

  const handleVideoUploadComplete = () => {
    setVideoRefreshTrigger(prev => prev + 1);
    refreshVideos();
    refreshIndexes();
  };

  const handleVideoSelect = (video: Video) => {
    setSelectedVideo(video);
    setSelectedClip(null);
    setComplianceStartTime(undefined);
  };

  const handleVideoDeleted = () => {
    // Refresh both videos and indexes after deletion
    setVideoRefreshTrigger(prev => prev + 1);
    refreshVideos();
    refreshIndexes();
    
    // Clear selected video if it was deleted
    if (selectedVideo) {
      setSelectedVideo(null);
    }
  };

  const handleClipSelect = (clip: VideoClip) => {
    setSelectedClip(clip);
    setSelectedVideo(null);
    setReelUrl(null);
    
    // Find video details from the loaded videos list
    const video = videos.find(v => v.id === clip.video_id);
    setSelectedClipVideo(video || null);
  };

  const handleSearch = async (searchQuery: string, topK?: number, imageFile?: File, modalities?: string[], transcriptionMode?: string, videoId?: string) => {
    if (!selectedIndex) return;
    await search(selectedIndex.id, searchQuery, topK, imageFile, modalities, transcriptionMode, videoId);
  };

  const handleReelGenerated = (url: string) => {
    setReelUrl(url);
    setSelectedVideo(null);
    setSelectedClip(null);
    setSelectedClipVideo(null);
    // Don't trigger playback - user must click "Play Video Reel" button
  };

  const handleAnalyze = async (query: string, scope: 'index' | 'video', scopeId: string, verbosity: 'concise' | 'balanced' | 'extended', useJockey?: boolean) => {
    // Cancel any previous ongoing analysis
    await cancelOngoingAnalysis();
    
    setIsAnalyzing(true);
    setAnalysisError(null);
    setAnalysisResult(null);
    setAnalysisProgress('');

    // Generate correlation ID for progress tracking
    const correlationId = crypto.randomUUID();
    analysisCorrelationIdRef.current = correlationId;
    
    // Create AbortController for this analysis
    const abortController = new AbortController();
    analysisAbortControllerRef.current = abortController;
    
    // Subscribe to WebSocket progress messages
    const unsubscribe = subscribe((message) => {
      if (message.type === 'analysis_progress' && message.correlation_id === correlationId) {
        setAnalysisProgress(message.message);
      }
    });

    // Wait for WebSocket to be connected before starting analysis
    if (!isConnected) {
      // Wait up to 5 seconds for connection
      for (let i = 0; i < 50; i++) {
        await new Promise(resolve => setTimeout(resolve, 100));
        if (isConnected) break;
      }
    }
    
    // Additional small delay to ensure subscription is registered
    await new Promise(resolve => setTimeout(resolve, 100));

    try {
      let result: AnalysisResult;
      
      if (scope === 'index') {
        result = await analysisApi.analyzeIndex(scopeId, query, verbosity, correlationId, abortController.signal);
      } else {
        result = await analysisApi.analyzeVideo(scopeId, query, verbosity, useJockey || false, correlationId, abortController.signal);
      }
      setAnalysisProgress('');
      setAnalysisResult(result);
    } catch (err: any) {
      // Don't show error if the request was aborted (user navigated away)
      if (err.name === 'AbortError') {
        console.debug('Analysis was cancelled');
        return;
      }
      const errorMessage = err.detail || err.message || 'Analysis failed';
      setAnalysisError(errorMessage);
      setAnalysisProgress('');
    } finally {
      setIsAnalyzing(false);
      unsubscribe();
      // Clear refs if this is still the current analysis
      if (analysisCorrelationIdRef.current === correlationId) {
        analysisCorrelationIdRef.current = null;
        analysisAbortControllerRef.current = null;
      }
    }
  };

  const handleClearAnalysis = () => {
    setAnalysisResult(null);
    setAnalysisError(null);
    setAnalysisProgress('');
  };

  const handleCheckCompliance = async (videoId: string) => {
    // Cancel any previous ongoing compliance check
    await cancelOngoingCompliance();
    
    setIsCheckingCompliance(true);
    setComplianceError(null);
    setComplianceResult(null);
    setComplianceVideoId(videoId);
    setComplianceProgress('');

    // Generate correlation ID for progress tracking
    const correlationId = crypto.randomUUID();
    complianceCorrelationIdRef.current = correlationId;
    
    // Create AbortController for this compliance check
    const abortController = new AbortController();
    complianceAbortControllerRef.current = abortController;
    
    // Subscribe to WebSocket progress messages
    const unsubscribe = subscribe((message) => {
      if (message.type === 'analysis_progress' && message.correlation_id === correlationId) {
        setComplianceProgress(message.message);
      }
    });

    // Wait for WebSocket to be connected before starting
    if (!isConnected) {
      for (let i = 0; i < 50; i++) {
        await new Promise(resolve => setTimeout(resolve, 100));
        if (isConnected) break;
      }
    }
    
    await new Promise(resolve => setTimeout(resolve, 100));

    try {
      const response = await complianceApi.checkCompliance(
        videoId,
        correlationId,
        abortController.signal
      );
      setComplianceProgress('');
      setComplianceResult(response.result);
    } catch (err: any) {
      if (err.name === 'AbortError') {
        console.debug('Compliance check was cancelled');
        return;
      }
      const errorMessage = err.detail || err.message || 'Compliance check failed';
      setComplianceError(errorMessage);
      setComplianceProgress('');
    } finally {
      setIsCheckingCompliance(false);
      unsubscribe();
      if (complianceCorrelationIdRef.current === correlationId) {
        complianceCorrelationIdRef.current = null;
        complianceAbortControllerRef.current = null;
      }
    }
  };

  const handleClearCompliance = () => {
    setComplianceResult(null);
    setComplianceVideoId(null);
    setComplianceError(null);
    setComplianceProgress('');
  };

  const handlePlayVideoFromCompliance = (video: Video, startTime?: number) => {
    setSelectedVideo(video);
    setSelectedClip(null);
    setComplianceStartTime(startTime);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-indigo-50 dark:from-slate-900 dark:via-slate-900 dark:to-slate-800 p-4 md:p-8 transition-colors">
      <div className="max-w-7xl mx-auto">
        {/* Header - Minimal & Clean */}
        <div className="bg-white/95 dark:bg-slate-800/95 backdrop-blur-lg rounded-2xl shadow-2xl p-6 md:p-8 border border-gray-200 dark:border-gray-700 mb-6 relative z-20">
          <div className="flex flex-col md:flex-row md:justify-between md:items-center gap-4">
            <div className="flex items-center gap-3">
              {/* TwelveLabs logo - blue for light mode, white for dark mode */}
              <img 
                src={logoBlack} 
                alt="TwelveLabs" 
                className="h-12 w-auto dark:hidden"
              />
              <img 
                src={logoWhite} 
                alt="TwelveLabs" 
                className="h-12 w-auto hidden dark:block"
              />
              
              {/* Title with subtle gradient */}
              <h1 className="text-3xl md:text-4xl font-bold bg-gradient-to-r from-gray-900 via-primary to-gray-900 dark:from-gray-100 dark:via-tl-lime dark:to-gray-100 bg-clip-text text-transparent">
                TwelveLabs on AWS Bedrock
              </h1>
            </div>
            
            {/* Theme toggle and sign out button */}
            <div className="flex items-center gap-3">
              <ThemeToggle />
              
              {/* Settings button */}
              <div className="relative" ref={settingsRef}>
                <button
                  onClick={() => setShowSettings(!showSettings)}
                  className="p-2 rounded-lg text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                  aria-label="Settings"
                >
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                </button>
                
                {/* Settings popup */}
                {showSettings && (
                  <div className="absolute right-0 mt-2 w-56 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 py-2 z-[100]">
                    <div className="px-4 py-2 border-b border-gray-200 dark:border-gray-700">
                      <span className="text-sm font-semibold text-gray-900 dark:text-gray-100">Visible Tabs</span>
                    </div>
                    <label className="flex items-center px-4 py-2 hover:bg-gray-50 dark:hover:bg-gray-700 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={visibleTabs.search}
                        onChange={(e) => setVisibleTabs(prev => ({ ...prev, search: e.target.checked }))}
                        className="w-4 h-4 rounded focus:ring-indigo-500 dark:focus:ring-lime-500 accent-indigo-500 dark:accent-lime-500"
                      />
                      <span className="ml-3 text-sm text-gray-700 dark:text-gray-300">Search</span>
                    </label>
                    <label className="flex items-center px-4 py-2 hover:bg-gray-50 dark:hover:bg-gray-700 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={visibleTabs.analysis}
                        onChange={(e) => setVisibleTabs(prev => ({ ...prev, analysis: e.target.checked }))}
                        className="w-4 h-4 rounded focus:ring-indigo-500 dark:focus:ring-lime-500 accent-indigo-500 dark:accent-lime-500"
                      />
                      <span className="ml-3 text-sm text-gray-700 dark:text-gray-300">Analysis</span>
                    </label>
                    <label className="flex items-center px-4 py-2 hover:bg-gray-50 dark:hover:bg-gray-700 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={visibleTabs.compliance}
                        onChange={(e) => setVisibleTabs(prev => ({ ...prev, compliance: e.target.checked }))}
                        className="w-4 h-4 rounded focus:ring-indigo-500 dark:focus:ring-lime-500 accent-indigo-500 dark:accent-lime-500"
                      />
                      <span className="ml-3 text-sm text-gray-700 dark:text-gray-300">Compliance</span>
                    </label>
                  </div>
                )}
              </div>
              
              <button
                onClick={handleLogout}
                className="group flex items-center gap-2 px-6 py-3 rounded-xl font-semibold
                         text-gray-700 bg-gray-100 dark:text-gray-200 dark:bg-gray-700
                         hover:text-white hover:bg-gradient-to-r hover:from-primary hover:to-primary-dark dark:hover:from-tl-lime dark:hover:to-tl-lime-dark
                         focus:outline-none focus:ring-2 focus:ring-indigo-400 dark:focus:ring-lime-400 focus:ring-offset-2
                         transform transition-all duration-200
                         hover:scale-[1.02] hover:shadow-lg
                         active:scale-[0.98]
                         border border-gray-200 dark:border-gray-600 hover:border-transparent"
              >
                <svg
                  className="w-5 h-5 transition-transform duration-200 group-hover:translate-x-0.5"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
                  />
                </svg>
                Sign Out
              </button>
            </div>
          </div>
        </div>

        {/* Asymmetric 1/4 + 3/4 layout for better content focus */}
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Left sidebar - Index Management (narrower 1/4) */}
          <div className="lg:col-span-1 space-y-6">
            <div className="bg-white/95 dark:bg-slate-800/95 backdrop-blur-lg rounded-2xl shadow-2xl p-6 border border-gray-200 dark:border-gray-700">
              <IndexList
                selectedIndexId={selectedIndex?.id}
                onIndexSelect={selectIndex}
                indexes={indexes}
                maxIndexes={maxIndexes}
                onRefresh={refreshIndexes}
              />
            </div>
          </div>

          {/* Main content area (wider 3/4) */}
          <div className="lg:col-span-3 space-y-6">
            {!selectedIndex ? (
              <div className="bg-white/95 dark:bg-slate-800/95 backdrop-blur-lg rounded-2xl shadow-2xl p-12 border border-gray-200 dark:border-gray-700 text-center">
                <svg
                  className="mx-auto h-16 w-16 text-gray-500 dark:text-gray-300 mb-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
                  />
                </svg>
                <h3 className="text-xl font-semibold text-gray-900 dark:text-gray-100 mb-2">No Index Selected</h3>
                <p className="text-gray-500 dark:text-gray-300">
                  Create or select an index to start managing videos
                </p>
              </div>
            ) : (
              <>
                {/* Tabs */}
                <div className="bg-white/95 dark:bg-slate-800/95 backdrop-blur-lg rounded-2xl shadow-2xl border border-gray-200 dark:border-gray-700 overflow-hidden">
                  <div className="flex border-b border-gray-200 dark:border-gray-700">
                    <button
                      onClick={() => setActiveTab('videos')}
                      className={`flex-1 px-6 py-4 font-semibold transition-all duration-200 relative ${
                        activeTab === 'videos'
                          ? 'bg-indigo-500/10 dark:bg-lime-500/20 text-indigo-500 dark:text-lime-400'
                          : 'text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100 hover:bg-white dark:hover:bg-gray-700/50'
                      }`}
                    >
                      Videos
                      <span className={`absolute bottom-0 left-0 w-full h-0.5 bg-indigo-500 dark:bg-lime-500 transition-transform duration-200 origin-left ${activeTab === 'videos' ? 'scale-x-100' : 'scale-x-0'}`} />
                    </button>
                    {visibleTabs.search && (
                      <button
                        onClick={() => videos.length > 0 && setActiveTab('search')}
                        disabled={videos.length === 0}
                        className={`flex-1 px-6 py-4 font-semibold transition-all duration-200 relative ${
                          activeTab === 'search'
                            ? 'bg-indigo-500/10 dark:bg-lime-500/20 text-indigo-500 dark:text-lime-400'
                            : videos.length === 0
                            ? 'text-gray-400 dark:text-gray-600 cursor-not-allowed opacity-50'
                            : 'text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100 hover:bg-white dark:hover:bg-gray-700/50'
                        }`}
                        title={videos.length === 0 ? 'Upload videos to enable search' : ''}
                      >
                        Search
                        <span className={`absolute bottom-0 left-0 w-full h-0.5 bg-indigo-500 dark:bg-lime-500 transition-transform duration-200 origin-left ${activeTab === 'search' ? 'scale-x-100' : 'scale-x-0'}`} />
                      </button>
                    )}
                    {visibleTabs.analysis && (
                      <button
                        onClick={() => videos.length > 0 && setActiveTab('analysis')}
                        disabled={videos.length === 0}
                        className={`flex-1 px-6 py-4 font-semibold transition-all duration-200 relative ${
                          activeTab === 'analysis'
                            ? 'bg-indigo-500/10 dark:bg-lime-500/20 text-indigo-500 dark:text-lime-400'
                            : videos.length === 0
                            ? 'text-gray-400 dark:text-gray-600 cursor-not-allowed opacity-50'
                            : 'text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100 hover:bg-white dark:hover:bg-gray-700/50'
                        }`}
                        title={videos.length === 0 ? 'Upload videos to enable analysis' : ''}
                      >
                        Analysis
                        <span className={`absolute bottom-0 left-0 w-full h-0.5 bg-indigo-500 dark:bg-lime-500 transition-transform duration-200 origin-left ${activeTab === 'analysis' ? 'scale-x-100' : 'scale-x-0'}`} />
                      </button>
                    )}
                    {visibleTabs.compliance && (
                      <button
                        onClick={() => videos.length > 0 && setActiveTab('compliance')}
                        disabled={videos.length === 0}
                        className={`flex-1 px-6 py-4 font-semibold transition-all duration-200 relative ${
                          activeTab === 'compliance'
                            ? 'bg-indigo-500/10 dark:bg-lime-500/20 text-indigo-500 dark:text-lime-400'
                            : videos.length === 0
                            ? 'text-gray-400 dark:text-gray-600 cursor-not-allowed opacity-50'
                            : 'text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100 hover:bg-white dark:hover:bg-gray-700/50'
                        }`}
                        title={videos.length === 0 ? 'Upload videos to enable compliance' : ''}
                      >
                        Compliance
                        <span className={`absolute bottom-0 left-0 w-full h-0.5 bg-indigo-500 dark:bg-lime-500 transition-transform duration-200 origin-left ${activeTab === 'compliance' ? 'scale-x-100' : 'scale-x-0'}`} />
                      </button>
                    )}
                  </div>

                  <div className="p-6 dark:bg-slate-800/50">
                    {/* Videos Tab */}
                    {activeTab === 'videos' && (
                      <div className="space-y-6">
                        <div>
                          <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">Upload Video</h3>
                          <VideoUpload
                            indexId={selectedIndex.id}
                            onUploadComplete={handleVideoUploadComplete}
                          />
                        </div>
                        <div>
                          <VideoList
                            indexId={selectedIndex.id}
                            onVideoSelect={handleVideoSelect}
                            onVideoDeleted={handleVideoDeleted}
                            selectedVideoId={selectedVideo?.id}
                            refreshTrigger={videoRefreshTrigger}
                          />
                        </div>
                      </div>
                    )}

                    {/* Search Tab */}
                    {activeTab === 'search' && (
                      <div className="space-y-6">
                        <SearchBar
                          onSearch={handleSearch}
                          isSearching={isSearching}
                          videos={videos}
                        />
                        {searchError && (
                          <div className="p-4 bg-red-500/10 border border-red-500/50 rounded-lg">
                            <p className="text-red-400">{searchError}</p>
                          </div>
                        )}
                        {searchResults.length > 0 && (
                          <SearchResults
                            results={searchResults}
                            query={query}
                            searchTime={searchTime}
                            onClipSelect={handleClipSelect}
                            selectedClip={selectedClip}
                            onReelGenerated={handleReelGenerated}
                          />
                        )}
                        {!isSearching && searchResults.length === 0 && !searchError && query && (
                          <div className="text-center py-12">
                            <p className="text-gray-500">No results found for "{query}"</p>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Analysis Tab */}
                    {activeTab === 'analysis' && (
                      <div className="space-y-6">
                        {!analysisResult ? (
                          <>
                            <AnalysisForm
                              indexId={selectedIndex.id}
                              videos={videos}
                              onAnalyze={handleAnalyze}
                              isAnalyzing={isAnalyzing}
                              progressMessage={analysisProgress}
                            />
                            {analysisError && (
                              <div className="p-4 bg-red-500/10 border border-red-500/50 rounded-lg">
                                <p className="text-red-400">{analysisError}</p>
                              </div>
                            )}
                          </>
                        ) : (
                          <AnalysisResults
                            result={analysisResult}
                            onClear={handleClearAnalysis}
                          />
                        )}
                      </div>
                    )}

                    {/* Compliance Tab */}
                    {activeTab === 'compliance' && (
                      <div className="space-y-6">
                        {!complianceResult ? (
                          <>
                            <ComplianceForm
                              indexId={selectedIndex.id}
                              videos={videos}
                              onCheck={handleCheckCompliance}
                              isChecking={isCheckingCompliance}
                              progressMessage={complianceProgress}
                              complianceParams={complianceParams}
                            />
                            {complianceError && (
                              <div className="p-4 bg-red-500/10 border border-red-500/50 rounded-lg">
                                <p className="text-red-400">{complianceError}</p>
                              </div>
                            )}
                          </>
                        ) : (
                          <ComplianceResults
                            result={complianceResult}
                            video={videos.find(v => v.id === complianceVideoId) || videos[0]}
                            onClear={handleClearCompliance}
                            onPlayVideo={handlePlayVideoFromCompliance}
                          />
                        )}
                      </div>
                    )}
                  </div>
                </div>

                {/* Video Player Popup */}
                <VideoPlayerPopup
                  isOpen={!!(selectedVideo || selectedClip || reelUrl)}
                  onClose={() => {
                    setSelectedVideo(null);
                    setSelectedClip(null);
                    setSelectedClipVideo(null);
                    setReelUrl(null);
                    setComplianceStartTime(undefined);
                  }}
                  title={
                    reelUrl
                      ? 'Video Reel Playback'
                      : selectedVideo 
                        ? selectedVideo.filename 
                        : selectedClipVideo 
                          ? selectedClipVideo.filename 
                          : 'Clip Playback'
                  }
                  videoId={!reelUrl && selectedVideo ? selectedVideo.id : undefined}
                  videoUrl={reelUrl || (selectedClip ? selectedClip.video_stream_url : undefined)}
                  startTime={selectedClip?.start_timecode ?? complianceStartTime}
                  endTime={selectedClip?.end_timecode}
                  autoPlay={true}
                />
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
