/**
 * SearchBar Component
 *
 * Large search input with modality toggles, scope selector, image upload,
 * and results count — styled with the Obsidian Lens design system.
 *
 * Validates: Requirements 8.1, 8.2, 8.3
 */

import { useState, useRef, useEffect, type FormEvent, type ChangeEvent } from 'react';
import type { Video } from '../../types';

interface SearchBarProps {
  onSearch: (query: string, topK?: number, imageFile?: File, modalities?: string[], transcriptionMode?: string, videoId?: string) => void;
  isSearching: boolean;
  videos: Video[];
}

export default function SearchBar({ onSearch, isSearching, videos }: SearchBarProps) {
  const [query, setQuery] = useState('');
  const [topK, setTopK] = useState(5);
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [imageError, setImageError] = useState<string | null>(null);
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
    if ((query.trim() || imageFile) && !isSearching && selectedModalities.size > 0) {
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

      let modalities = Array.from(selectedModalities).filter(m => m !== 'lexical');
      if (hasLexical && !hasTranscription) {
        modalities.push('transcription');
      }

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
    setImageError(null);
    if (file) {
      const validTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp'];
      if (!validTypes.includes(file.type)) {
        setImageError('Please select a valid image file (JPEG, PNG, or WebP)');
        return;
      }
      const maxSize = 10 * 1024 * 1024;
      if (file.size > maxSize) {
        setImageError('Image size must be less than 10MB');
        return;
      }
      setImageFile(file);
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
    setImageError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleImageButtonClick = () => {
    fileInputRef.current?.click();
  };

  const modalities: { key: string; icon: string; label: string }[] = [
    { key: 'visual', icon: 'videocam', label: 'Visual' },
    { key: 'audio', icon: 'volume_up', label: 'Audio' },
    { key: 'transcription', icon: 'description', label: 'Transcription' },
    { key: 'lexical', icon: 'translate', label: 'Lexical' },
  ];

  return (
    <form onSubmit={handleSubmit} className="w-full space-y-5">
      {/* Search input */}
      <div className="relative">
        <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
          <span className="material-symbols-outlined text-on-surface-variant text-2xl">search</span>
        </div>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search videos with natural language..."
          disabled={isSearching}
          className="w-full bg-surface-container-low rounded-xl py-6 pl-14 pr-12 text-2xl ghost-border
                     text-on-surface placeholder-on-surface-variant/50
                     focus:outline-none focus:ring-1 focus:ring-primary/30
                     disabled:opacity-50 disabled:cursor-not-allowed
                     transition-all duration-200"
        />
        {query && !isSearching && (
          <button
            type="button"
            onClick={handleClear}
            className="absolute inset-y-0 right-0 pr-4 flex items-center text-on-surface-variant hover:text-on-surface transition-colors"
            title="Clear"
          >
            <span className="material-symbols-outlined">close</span>
          </button>
        )}
      </div>

      {/* Image upload + Modality toggles + Results count row */}
      <div className="flex flex-wrap items-center gap-3">
        {/* Image upload button */}
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
          className="flex items-center gap-2 px-4 py-2 bg-surface-container-low text-on-surface-variant rounded-lg
                     hover:text-on-surface ghost-border
                     disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
        >
          <span className="material-symbols-outlined text-xl">image</span>
          <span className="text-sm font-medium">{imageFile ? 'Change Image' : 'Add Image'}</span>
        </button>

        {imageFile && (
          <span className="text-sm text-on-surface-variant">
            {imageFile.name} ({(imageFile.size / 1024).toFixed(1)} KB)
          </span>
        )}

        {/* Modality toggles pill */}
        <div className="flex items-center bg-surface-container-low rounded-full p-1 gap-1">
          {modalities.map(({ key, icon, label }) => (
            <button
              key={key}
              type="button"
              onClick={() => toggleModality(key)}
              disabled={isSearching}
              title={label}
              className={`flex items-center gap-1.5 px-4 py-2 rounded-full text-sm font-medium transition-all duration-200
                disabled:opacity-50 disabled:cursor-not-allowed
                ${selectedModalities.has(key)
                  ? 'bg-primary-container/20 text-primary'
                  : 'text-on-surface-variant hover:text-on-surface'
                }`}
            >
              <span className="material-symbols-outlined text-lg">{icon}</span>
              <span className="hidden sm:inline">{label}</span>
            </button>
          ))}
        </div>

        {/* Results count selector */}
        <div className="flex items-center gap-2 ml-auto">
          <label htmlFor="topK" className="text-sm text-on-surface-variant font-medium">
            Results:
          </label>
          <select
            id="topK"
            value={topK}
            onChange={(e) => setTopK(Number(e.target.value))}
            disabled={isSearching}
            className="px-3 py-2 bg-surface-container-low rounded-lg text-on-surface text-sm ghost-border
                       focus:outline-none focus:ring-1 focus:ring-primary/30
                       disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
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
              className="h-24 w-auto rounded-xl border border-outline-variant/10 object-cover"
            />
            <button
              type="button"
              onClick={handleRemoveImage}
              disabled={isSearching}
              className="absolute -top-2 -right-2 p-1 bg-error text-on-error rounded-full
                         hover:bg-error-dim focus:outline-none
                         disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
              title="Remove image"
            >
              <span className="material-symbols-outlined text-base">close</span>
            </button>
          </div>
        </div>
      )}

      {/* Image error */}
      {imageError && (
        <p className="text-sm text-error">{imageError}</p>
      )}

      {/* Search Scope selector */}
      <div>
        <label className="block text-sm font-medium text-on-surface-variant mb-3">
          Search Scope
        </label>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {/* Entire Index */}
          <label
            className={`flex items-start gap-3 p-4 rounded-xl cursor-pointer transition-all duration-200
              bg-surface-container-low border
              ${scope === 'index'
                ? 'border-primary/30 bg-primary-container/10'
                : 'border-outline-variant/10 hover:border-outline-variant/20'
              }
              ${isSearching ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            <input
              type="radio"
              name="search-scope"
              value="index"
              checked={scope === 'index'}
              onChange={() => handleScopeChange('index')}
              disabled={isSearching}
              className="mt-1 h-4 w-4 accent-primary"
            />
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-primary text-xl">inventory_2</span>
                <span className="font-medium text-on-surface">Entire Index</span>
              </div>
              <p className="text-sm text-on-surface-variant mt-1">
                Search all videos in this index
              </p>
            </div>
          </label>

          {/* Single Video */}
          <label
            className={`flex items-start gap-3 p-4 rounded-xl cursor-pointer transition-all duration-200
              bg-surface-container-low border
              ${scope === 'video'
                ? 'border-primary/30 bg-primary-container/10'
                : 'border-outline-variant/10 hover:border-outline-variant/20'
              }
              ${isSearching || videos.length === 0 ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            <input
              type="radio"
              name="search-scope"
              value="video"
              checked={scope === 'video'}
              onChange={() => handleScopeChange('video')}
              disabled={isSearching || videos.length === 0}
              className="mt-1 h-4 w-4 accent-primary"
            />
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-on-surface-variant text-xl">movie</span>
                <span className="font-medium text-on-surface">Single Video</span>
              </div>
              <p className="text-sm text-on-surface-variant mt-1">
                Search a specific video from this index
              </p>
              {scope === 'video' && videos.length > 0 && (
                <select
                  value={selectedVideoId}
                  onChange={(e) => setSelectedVideoId(e.target.value)}
                  disabled={isSearching}
                  className="mt-3 w-full px-3 py-2 bg-surface-container-high rounded-lg text-on-surface text-sm ghost-border
                             focus:outline-none focus:ring-1 focus:ring-primary/30
                             disabled:opacity-50 disabled:cursor-not-allowed"
                  onClick={(e) => e.stopPropagation()}
                >
                  {videos.map((video) => (
                    <option key={video.id} value={video.id}>
                      {video.filename}
                    </option>
                  ))}
                </select>
              )}
              {videos.length === 0 && (
                <p className="text-xs text-on-surface-variant mt-2">
                  No videos available. Upload videos to use this option.
                </p>
              )}
            </div>
          </label>
        </div>
      </div>

      {/* Modality validation message */}
      {selectedModalities.size === 0 && (
        <p className="text-sm text-error">
          Select at least one modality to search
        </p>
      )}

      {/* Search button */}
      <button
        type="submit"
        disabled={(!query.trim() && !imageFile) || isSearching || selectedModalities.size === 0}
        className="w-full px-6 py-4 rounded-xl font-semibold text-on-primary
                   bg-gradient-to-r from-primary to-primary-container
                   hover:brightness-110
                   focus:outline-none focus:ring-2 focus:ring-primary/40
                   disabled:opacity-50 disabled:cursor-not-allowed
                   transform transition-all duration-200
                   hover:scale-[1.01] active:scale-[0.99]
                   shadow-lg"
      >
        {isSearching ? (
          <span className="flex items-center justify-center gap-2">
            <span className="material-symbols-outlined animate-spin text-xl">progress_activity</span>
            <span>Searching...</span>
          </span>
        ) : (
          <span className="flex items-center justify-center gap-2">
            <span className="material-symbols-outlined text-xl">search</span>
            <span>Search</span>
          </span>
        )}
      </button>
    </form>
  );
}
