import { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth } from '../../hooks/useAuth';
import { useIndexes } from '../../hooks/useIndexes';
import { useSearch } from '../../hooks/useSearch';
import { useVideos } from '../../hooks/useVideos';
import { useWebSocketContext } from '../../contexts/WebSocketContext';
import { analysisApi, complianceApi } from '../../services/api';
import type { Video, VideoClip, AnalysisResult, ComplianceResult, ComplianceParams } from '../../types';

import TopNav from './TopNav';
import Sidebar from './Sidebar';
import TabNav from './TabNav';
import IndexList from '../Index/IndexList';
import VideoUpload from '../Video/VideoUpload';
import VideoGrid from '../Video/VideoGrid';
import VideoPlayerPopup from '../Video/VideoPlayerPopup';
import SearchBar from '../Search/SearchBar';
import SearchResults from '../Search/SearchResults';
import AnalysisForm from '../Analysis/AnalysisForm';
import AnalysisResults from '../Analysis/AnalysisResults';
import ComplianceForm from '../Compliance/ComplianceForm';
import ComplianceResults from '../Compliance/ComplianceResults';

type ActiveTab = 'videos' | 'search' | 'analysis' | 'compliance';

/**
 * DashboardLayout Component
 *
 * Main authenticated view composing TopNav, Sidebar, TabNav, and content area.
 * Manages all dashboard state: tabs, video playback, analysis, compliance, settings.
 *
 * Validates: Requirements 4.3, 4.5, 4.6, 6.4, 6.6
 */
export default function DashboardLayout() {
  const { logout } = useAuth();
  const { indexes, selectedIndex, selectIndex, refreshIndexes, maxIndexes } = useIndexes();
  const { searchResults, query, searchTime, isSearching, error: searchError, search, clearResults } = useSearch();
  const { videos, refreshVideos } = useVideos(selectedIndex?.id || null);
  const { subscribe, isConnected } = useWebSocketContext();

  // Tab state
  const [activeTab, setActiveTab] = useState<ActiveTab>('videos');
  const [visibleTabs, setVisibleTabs] = useState({
    search: true,
    analysis: true,
    compliance: true,
  });
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Video playback state
  const [selectedVideo, setSelectedVideo] = useState<Video | null>(null);
  const [selectedClip, setSelectedClip] = useState<VideoClip | null>(null);
  const [selectedClipVideo, setSelectedClipVideo] = useState<Video | null>(null);
  const [reelUrl, setReelUrl] = useState<string | null>(null);
  const [videoRefreshTrigger, setVideoRefreshTrigger] = useState(0);
  const [complianceStartTime, setComplianceStartTime] = useState<number | undefined>(undefined);

  // Analysis state
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [analysisProgress, setAnalysisProgress] = useState<string>('');

  // Compliance state
  const [complianceResult, setComplianceResult] = useState<ComplianceResult | null>(null);
  const [complianceVideoId, setComplianceVideoId] = useState<string | null>(null);
  const [isCheckingCompliance, setIsCheckingCompliance] = useState(false);
  const [complianceError, setComplianceError] = useState<string | null>(null);
  const [complianceProgress, setComplianceProgress] = useState<string>('');
  const [complianceParams, setComplianceParams] = useState<ComplianceParams | null>(null);

  // Refs for cancellation
  const analysisAbortControllerRef = useRef<AbortController | null>(null);
  const analysisCorrelationIdRef = useRef<string | null>(null);
  const complianceAbortControllerRef = useRef<AbortController | null>(null);
  const complianceCorrelationIdRef = useRef<string | null>(null);

  // Close sidebar on mobile when navigating
  const handleSidebarToggle = useCallback(() => {
    setSidebarOpen(prev => !prev);
  }, []);

  const handleCloseSidebar = useCallback(() => {
    setSidebarOpen(false);
  }, []);

  // Cancel ongoing analysis
  const cancelOngoingAnalysis = useCallback(async () => {
    if (analysisAbortControllerRef.current) {
      analysisAbortControllerRef.current.abort();
      analysisAbortControllerRef.current = null;
    }
    if (analysisCorrelationIdRef.current) {
      try {
        await analysisApi.cancelAnalysis(analysisCorrelationIdRef.current);
      } catch (error) {
        console.debug('Analysis cancellation:', error);
      }
      analysisCorrelationIdRef.current = null;
    }
    setIsAnalyzing(false);
    setAnalysisProgress('');
  }, []);

  // Cancel ongoing compliance check
  const cancelOngoingCompliance = useCallback(async () => {
    if (complianceAbortControllerRef.current) {
      complianceAbortControllerRef.current.abort();
      complianceAbortControllerRef.current = null;
    }
    complianceCorrelationIdRef.current = null;
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

  // Clear all state when index changes or is deleted
  useEffect(() => {
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

  // Switch to Videos tab if current tab becomes hidden
  useEffect(() => {
    if (activeTab !== 'videos' && !visibleTabs[activeTab as keyof typeof visibleTabs]) {
      setActiveTab('videos');
    }
  }, [visibleTabs, activeTab]);

  // Clear video playback state on tab switch
  useEffect(() => {
    setSelectedVideo(null);
    setSelectedClip(null);
    setSelectedClipVideo(null);
    setReelUrl(null);
  }, [activeTab]);

  // Reset search results when leaving search tab
  useEffect(() => {
    if (activeTab !== 'search') {
      clearResults();
    }
  }, [activeTab, clearResults]);

  // Cancel analysis and clear results when leaving analysis tab
  useEffect(() => {
    if (activeTab !== 'analysis') {
      cancelOngoingAnalysis();
      setAnalysisResult(null);
      setAnalysisError(null);
      setAnalysisProgress('');
    }
  }, [activeTab, cancelOngoingAnalysis]);

  // Cancel compliance and clear results when leaving compliance tab
  useEffect(() => {
    if (activeTab !== 'compliance') {
      cancelOngoingCompliance();
      setComplianceResult(null);
      setComplianceVideoId(null);
      setComplianceError(null);
      setComplianceProgress('');
    }
  }, [activeTab, cancelOngoingCompliance]);

  // --- Handlers ---

  const handleLogout = async () => {
    try {
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
    setVideoRefreshTrigger(prev => prev + 1);
    refreshVideos();
    refreshIndexes();
    if (selectedVideo) {
      setSelectedVideo(null);
    }
  };

  const handleClipSelect = (clip: VideoClip) => {
    setSelectedClip(clip);
    setSelectedVideo(null);
    setReelUrl(null);
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
  };

  const handleAnalyze = async (queryText: string, scope: 'index' | 'video', scopeId: string, verbosity: 'concise' | 'balanced' | 'extended', useJockey?: boolean) => {
    await cancelOngoingAnalysis();

    setIsAnalyzing(true);
    setAnalysisError(null);
    setAnalysisResult(null);
    setAnalysisProgress('');

    const correlationId = crypto.randomUUID();
    analysisCorrelationIdRef.current = correlationId;

    const abortController = new AbortController();
    analysisAbortControllerRef.current = abortController;

    const unsubscribe = subscribe((message) => {
      if (message.type === 'analysis_progress' && message.correlation_id === correlationId) {
        setAnalysisProgress(message.message);
      }
    });

    if (!isConnected) {
      for (let i = 0; i < 50; i++) {
        await new Promise(resolve => setTimeout(resolve, 100));
        if (isConnected) break;
      }
    }
    await new Promise(resolve => setTimeout(resolve, 100));

    try {
      let result: AnalysisResult;
      if (scope === 'index') {
        result = await analysisApi.analyzeIndex(scopeId, queryText, verbosity, correlationId, abortController.signal);
      } else {
        result = await analysisApi.analyzeVideo(scopeId, queryText, verbosity, useJockey || false, correlationId, abortController.signal);
      }
      setAnalysisProgress('');
      setAnalysisResult(result);
    } catch (err: any) {
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
    await cancelOngoingCompliance();

    setIsCheckingCompliance(true);
    setComplianceError(null);
    setComplianceResult(null);
    setComplianceVideoId(videoId);
    setComplianceProgress('');

    const correlationId = crypto.randomUUID();
    complianceCorrelationIdRef.current = correlationId;

    const abortController = new AbortController();
    complianceAbortControllerRef.current = abortController;

    const unsubscribe = subscribe((message) => {
      if (message.type === 'analysis_progress' && message.correlation_id === correlationId) {
        setComplianceProgress(message.message);
      }
    });

    if (!isConnected) {
      for (let i = 0; i < 50; i++) {
        await new Promise(resolve => setTimeout(resolve, 100));
        if (isConnected) break;
      }
    }
    await new Promise(resolve => setTimeout(resolve, 100));

    try {
      const response = await complianceApi.checkCompliance(videoId, correlationId, abortController.signal);
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

  // --- Render ---

  return (
    <div className="min-h-screen bg-background text-on-surface">
      {/* Fixed TopNav */}
      <TopNav
        onLogout={handleLogout}
        onMenuToggle={handleSidebarToggle}
        visibleTabs={visibleTabs}
        onVisibleTabsChange={setVisibleTabs}
        showSettings={!!selectedIndex}
      />

      {/* Sidebar - responsive: overlay on mobile, fixed on lg+ */}
      <Sidebar isOpen={sidebarOpen} onClose={handleCloseSidebar}>
        <IndexList
          selectedIndexId={selectedIndex?.id}
          onIndexSelect={(index) => {
            selectIndex(index);
            handleCloseSidebar();
          }}
          indexes={indexes}
          maxIndexes={maxIndexes}
          onRefresh={refreshIndexes}
        />
      </Sidebar>

      {/* Main content area - full width on mobile, offset for sidebar on lg+ */}
      <main className="lg:ml-64 mt-16 min-h-[calc(100vh-64px)]">
        {!selectedIndex ? (
          /* No index selected prompt */
          <div className="flex items-center justify-center h-[calc(100vh-64px)]">
            <div className="bg-surface-container-high rounded-xl p-12 text-center max-w-md">
              <span className="material-symbols-outlined text-5xl text-on-surface-variant mb-4 block">
                inventory_2
              </span>
              <h3 className="text-xl font-semibold text-on-surface mb-2">No Index Selected</h3>
              <p className="text-on-surface-variant">
                Create or select an index from the sidebar to start managing videos
              </p>
            </div>
          </div>
        ) : (
          <>
            {/* TabNav */}
            <TabNav
              activeTab={activeTab}
              onTabChange={setActiveTab}
              hasVideos={videos.length > 0}
              visibleTabs={visibleTabs}
            />

            {/* Scrollable content area */}
            <div className="p-6">
              {/* Videos Tab */}
              {activeTab === 'videos' && (
                <div className="space-y-6">
                  <VideoUpload
                    indexId={selectedIndex.id}
                    onUploadComplete={handleVideoUploadComplete}
                  />
                  <VideoGrid
                    indexId={selectedIndex.id}
                    onVideoSelect={handleVideoSelect}
                    onVideoDeleted={handleVideoDeleted}
                    selectedVideoId={selectedVideo?.id}
                    refreshTrigger={videoRefreshTrigger}
                  />
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
                    <div className="bg-error/10 border border-error/30 rounded-lg p-4">
                      <p className="text-error">{searchError}</p>
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
                      <p className="text-on-surface-variant">No results found for "{query}"</p>
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
                        <div className="bg-error/10 border border-error/30 rounded-lg p-4">
                          <p className="text-error">{analysisError}</p>
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
                        <div className="bg-error/10 border border-error/30 rounded-lg p-4">
                          <p className="text-error">{complianceError}</p>
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
      </main>
    </div>
  );
}
