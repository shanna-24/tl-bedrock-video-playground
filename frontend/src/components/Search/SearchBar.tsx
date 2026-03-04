/**
 * SearchBar Component
 * 
 * Natural language search input with loading state and image upload support.
 * Allows users to search videos using text, images, or both (multimodal search).
 * Includes modality filtering to search visual, audio, and/or transcription embeddings.
 * Supports search scope selection (entire index or single video).
 * 
 * Validates: Requirements 3.1, Multimodal Search Requirements 1.1, 1.2, 5.4, 5.5, 5.6
 */

import { useState, useRef, useEffect, type FormEvent, type ChangeEvent } from 'react';
import type { Video } from '../../types';

interface SearchBarProps {
  onSearch: (query: string, topK?: number, imageFile?: File, modalities?: string[], transcriptionMode?: string, videoId?: string) => void;
  isSearching?: boolean;
  placeholder?: string;
  videos?: Video[];
}

export default function SearchBar({ 
  onSearch, 
  isSearching = false,
  placeholder = "Search videos with natural language (e.g., 'people talking about technology')",
  videos = []
}: SearchBarProps) {
  const [query, setQuery] = useState('');
  const [topK, setTopK] = useState(5);
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [selectedModalities, setSelectedModalities] = useState<Set<string>>(
    new Set(['visual', 'audio', 'transcription', 'lexical'])
  );
  const [scope, setScope] = useState<'index' | 'video'>('index');
  const [selectedVideoId, setSelectedVideoId] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Set default video when videos change
  useEffect(() => {
    if (videos.length > 0 && !selectedVideoId) {
      setSelectedVideoId(videos[0].id);
    }
  }, [videos, selectedVideoId]);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    // Allow search if either query or image is provided, and at least one modality is selected
    if ((query.trim() || imageFile) && !isSearching && selectedModalities.size > 0) {
      // Determine transcription_mode based on button selections
      const hasTranscription = selectedModalities.has('transcription');
      const hasLexical = selectedModalities.has('lexical');
      
      let transcriptionMode: string | undefined;
      if (hasTranscription && hasLexical) {
        transcriptionMode = 'both';
      } else if (hasTranscription) {
        transcriptionMode = 'semantic';
      } else if (hasLexical) {
        transcriptionMode = 'lexical';
      }
      
      // Filter modalities for API (exclude 'lexical' as it's handled by transcription_mode)
      let modalities = Array.from(selectedModalities).filter(m => m !== 'lexical');
      
      // If lexical is selected but transcription isn't, add transcription to enable lexical search
      if (hasLexical && !hasTranscription) {
        modalities.push('transcription');
      }
      
      // Determine video ID based on scope
      const videoId = scope === 'video' ? selectedVideoId : undefined;
      
      onSearch(query.trim() || '', topK, imageFile || undefined, modalities, transcriptionMode, videoId);
    }
  };

  const handleScopeChange = (newScope: 'index' | 'video') => {
    setScope(newScope);
    if (newScope === 'video' && videos.length > 0 && !selectedVideoId) {
      setSelectedVideoId(videos[0].id);
    }
  };

  const toggleModality = (modality: string) => {
    setSelectedModalities(prev => {
      const newSet = new Set(prev);
      if (newSet.has(modality)) {
        newSet.delete(modality);
      } else {
        newSet.add(modality);
      }
      return newSet;
    });
  };

  const handleClear = () => {
    setQuery('');
  };

  const handleImageSelect = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      // Validate file type
      const validTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp'];
      if (!validTypes.includes(file.type)) {
        alert('Please select a valid image file (JPEG, PNG, or WebP)');
        return;
      }

      // Validate file size (10MB max)
      const maxSize = 10 * 1024 * 1024; // 10MB
      if (file.size > maxSize) {
        alert('Image size must be less than 10MB');
        return;
      }

      setImageFile(file);
      
      // Create preview
      const reader = new FileReader();
      reader.onloadend = () => {
        setImagePreview(reader.result as string);
      };
      reader.readAsDataURL(file);
    }
  };

  const handleRemoveImage = () => {
    setImageFile(null);
    setImagePreview(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleImageButtonClick = () => {
    fileInputRef.current?.click();
  };

  return (
    <form onSubmit={handleSubmit} className="w-full space-y-3">
      <div className="relative">
        <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
          <svg
            className="h-5 w-5 text-gray-500"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
            />
          </svg>
        </div>

        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={placeholder}
          disabled={isSearching}
          className="w-full pl-12 pr-4 py-4 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded-lg
                   text-gray-900 dark:text-gray-100 placeholder-gray-500 dark:placeholder-gray-400
                   focus:outline-none focus:ring-2 focus:ring-indigo-500 dark:focus:ring-lime-500 focus:border-transparent
                   disabled:opacity-50 disabled:cursor-not-allowed
                   transition-all duration-200"
        />

        {query && !isSearching && (
          <button
            type="button"
            onClick={handleClear}
            className="absolute inset-y-0 right-0 pr-4 flex items-center text-gray-500 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100 transition-colors"
            title="Clear"
          >
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        )}
      </div>

      {/* Image upload section with Results dropdown */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <input
              ref={fileInputRef}
              type="file"
              accept="image/jpeg,image/jpg,image/png,image/webp"
              onChange={handleImageSelect}
              disabled={isSearching}
              className="hidden"
            />
            <button
              type="button"
              onClick={handleImageButtonClick}
              disabled={isSearching}
              className="frost-hover px-4 py-2 bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg
                       text-gray-700 dark:text-gray-200 text-sm font-medium
                       hover:border-gray-300 dark:hover:border-gray-500
                       focus:outline-none focus:ring-2 focus:ring-indigo-500 dark:focus:ring-lime-500 focus:border-transparent
                       disabled:opacity-50 disabled:cursor-not-allowed
                       transition-all duration-200
                       flex items-center space-x-2"
            >
              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
              <span>{imageFile ? 'Change Image' : 'Add Image'}</span>
            </button>
            
            {imageFile && (
              <span className="text-sm text-gray-600 dark:text-gray-300">
                {imageFile.name} ({(imageFile.size / 1024).toFixed(1)} KB)
              </span>
            )}

            {/* Modality filter buttons (icon-only) */}
            <div className="flex items-center space-x-1 ml-2 border-l border-gray-200 dark:border-gray-600 pl-4">
              <button
                type="button"
                onClick={() => toggleModality('visual')}
                disabled={isSearching}
                title="Visual"
                className={`px-6 py-2 rounded-lg transition-all duration-200
                          ${selectedModalities.has('visual')
                            ? 'bg-indigo-500 dark:bg-lime-500 text-white'
                            : 'frost-hover bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300'
                          }
                          disabled:opacity-50 disabled:cursor-not-allowed`}
              >
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
              </button>
              
              <button
                type="button"
                onClick={() => toggleModality('audio')}
                disabled={isSearching}
                title="Audio"
                className={`px-6 py-2 rounded-lg transition-all duration-200
                          ${selectedModalities.has('audio')
                            ? 'bg-indigo-500 dark:bg-lime-500 text-white'
                            : 'frost-hover bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300'
                          }
                          disabled:opacity-50 disabled:cursor-not-allowed`}
              >
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
                </svg>
              </button>
              
              <button
                type="button"
                onClick={() => toggleModality('transcription')}
                disabled={isSearching}
                title="Transcription (semantic)"
                className={`px-6 py-2 rounded-lg transition-all duration-200
                          ${selectedModalities.has('transcription')
                            ? 'bg-indigo-500 dark:bg-lime-500 text-white'
                            : 'frost-hover bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300'
                          }
                          disabled:opacity-50 disabled:cursor-not-allowed`}
              >
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </button>
              
              <button
                type="button"
                onClick={() => toggleModality('lexical')}
                disabled={isSearching}
                title="Transcription (lexical - exact match)"
                className={`px-6 py-2 rounded-lg transition-all duration-200
                          ${selectedModalities.has('lexical')
                            ? 'bg-indigo-500 dark:bg-lime-500 text-white'
                            : 'frost-hover bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300'
                          }
                          disabled:opacity-50 disabled:cursor-not-allowed`}
              >
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5h12M9 3v2m1.048 9.5A18.022 18.022 0 016.412 9m6.088 9h7M11 21l5-10 5 10M12.751 5C11.783 10.77 8.07 15.61 3 18.129" />
                </svg>
              </button>
            </div>
          </div>

          {/* Results limit selector */}
          <div className="flex items-center space-x-3">
            <label htmlFor="topK" className="text-sm text-gray-600 dark:text-gray-300 font-medium">
              Results:
            </label>
            <select
              id="topK"
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
              disabled={isSearching}
              className="px-3 py-2 bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg
                       text-gray-900 dark:text-gray-100 text-sm
                       focus:outline-none focus:ring-2 focus:ring-indigo-500 dark:focus:ring-lime-500 focus:border-transparent
                       disabled:opacity-50 disabled:cursor-not-allowed
                       transition-all duration-200"
            >
              <option value={5}>5</option>
              <option value={10}>10</option>
              <option value={20}>20</option>
            </select>
          </div>
        </div>

        {/* Image preview */}
        {imagePreview && (
          <div className="flex justify-start">
            <div className="relative">
              <img
                src={imagePreview}
                alt="Search image preview"
                className="h-24 w-auto rounded-lg border border-gray-200 dark:border-gray-600 object-cover"
              />
              <button
                type="button"
                onClick={handleRemoveImage}
                disabled={isSearching}
                className="absolute -top-2 -right-2 p-1 bg-red-500 dark:bg-red-600 text-white rounded-full
                         hover:bg-red-600 dark:hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-300 dark:focus:ring-red-400
                         disabled:opacity-50 disabled:cursor-not-allowed
                         transition-all duration-200"
                title="Remove image"
              >
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Search Scope selector */}
      <div>
        <label className="block text-sm font-medium text-gray-600 dark:text-gray-300 mb-3">
          Search Scope
        </label>
        <div className="space-y-3">
          {/* Index scope */}
          <label
            className={`
              frost-hover flex items-start p-4 rounded-lg border-2 cursor-pointer transition-all duration-200
              ${scope === 'index'
                ? 'border-indigo-500 dark:border-lime-500 bg-indigo-500/10 dark:bg-lime-500/20'
                : 'border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700/50 hover:border-gray-300 dark:hover:border-gray-500'
              }
              ${isSearching ? 'opacity-50 cursor-not-allowed' : ''}
            `}
          >
            <input
              type="radio"
              name="search-scope"
              value="index"
              checked={scope === 'index'}
              onChange={() => handleScopeChange('index')}
              disabled={isSearching}
              className="mt-1 h-4 w-4 text-indigo-500 dark:text-indigo-400 focus:ring-indigo-500 dark:focus:ring-indigo-400 focus:ring-offset-0"
            />
            <div className="ml-3 flex-1">
              <div className="flex items-center space-x-2">
                <svg
                  className="h-5 w-5 text-green-400"
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
                <span className="font-medium text-gray-900 dark:text-gray-100">Entire Index</span>
              </div>
              <p className="text-sm text-gray-500 dark:text-gray-300 mt-1">
                Search all videos in this index
              </p>
            </div>
          </label>

          {/* Video scope */}
          <label
            className={`
              frost-hover flex items-start p-4 rounded-lg border-2 cursor-pointer transition-all duration-200
              ${scope === 'video'
                ? 'border-indigo-500 dark:border-lime-500 bg-indigo-500/10 dark:bg-lime-500/20'
                : 'border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700/50 hover:border-gray-300 dark:hover:border-gray-500'
              }
              ${isSearching || videos.length === 0 ? 'opacity-50 cursor-not-allowed' : ''}
            `}
          >
            <input
              type="radio"
              name="search-scope"
              value="video"
              checked={scope === 'video'}
              onChange={() => handleScopeChange('video')}
              disabled={isSearching || videos.length === 0}
              className="mt-1 h-4 w-4 text-lime-500 focus:ring-indigo-500 focus:ring-offset-0"
            />
            <div className="ml-3 flex-1">
              <div className="flex items-center space-x-2">
                <svg
                  className="h-5 w-5 text-gray-600 dark:text-gray-300"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M7 4v16M17 4v16M3 8h4m10 0h4M3 12h18M3 16h4m10 0h4M4 20h16a1 1 0 001-1V5a1 1 0 00-1-1H4a1 1 0 00-1 1v14a1 1 0 001 1z"
                  />
                </svg>
                <span className="font-medium text-gray-900 dark:text-gray-100">Single Video</span>
              </div>
              <p className="text-sm text-gray-500 dark:text-gray-300 mt-1">
                Search a specific video from this index
              </p>

              {/* Video selector */}
              {scope === 'video' && videos.length > 0 && (
                <select
                  value={selectedVideoId}
                  onChange={(e) => setSelectedVideoId(e.target.value)}
                  disabled={isSearching}
                  className="mt-3 w-full px-3 py-2 bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg
                           text-gray-900 dark:text-gray-100 text-sm
                           focus:outline-none focus:ring-2 focus:ring-indigo-500 dark:focus:ring-lime-500 focus:border-transparent
                           disabled:opacity-50 disabled:cursor-not-allowed"
                  onClick={(e) => e.stopPropagation()}
                >
                  {videos.map((video) => (
                    <option key={video.id} value={video.id} className="bg-white dark:bg-gray-800">
                      {video.filename}
                    </option>
                  ))}
                </select>
              )}

              {videos.length === 0 && (
                <p className="text-xs text-gray-500 dark:text-gray-300 mt-2">
                  No videos available. Upload videos to use this option.
                </p>
              )}
            </div>
          </label>
        </div>
      </div>

      {/* Modality validation message */}
      {selectedModalities.size === 0 && (
        <p className="text-xs text-red-500 dark:text-red-400">
          Select at least one modality to search
        </p>
      )}

      <button
        type="submit"
        disabled={(!query.trim() && !imageFile) || isSearching || selectedModalities.size === 0}
        className="w-full px-6 py-3 rounded-lg font-semibold text-white
                 bg-indigo-500 dark:bg-lime-500
                 hover:bg-indigo-600 dark:hover:bg-lime-600
                 focus:outline-none focus:ring-2 focus:ring-indigo-400 dark:focus:ring-lime-400
                 disabled:opacity-50 disabled:cursor-not-allowed
                 transform transition-all duration-200
                 hover:scale-[1.02] active:scale-[0.98]
                 shadow-lg"
      >
        {isSearching ? (
          <span className="flex items-center justify-center space-x-2">
            <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>
            <span>Searching...</span>
          </span>
        ) : (
          'Search'
        )}
      </button>

      {/* Search tips */}
      <div className="text-xs text-gray-500 dark:text-gray-300 space-y-1">
        <p>
          Try queries like: "person speaking", "outdoor scenes", "text on screen", or "music playing"
        </p>
        <p>
          Upload an image to search for visually similar content, or combine text and image for multimodal search
        </p>
      </div>
    </form>
  );
}
