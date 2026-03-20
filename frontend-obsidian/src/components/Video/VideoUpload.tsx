/**
 * VideoUpload Component
 *
 * Provides drag-and-drop video upload functionality with progress tracking.
 * Validates file format and size before upload.
 * Restyled with Obsidian Lens design tokens.
 *
 * Validates: Requirements 7.1, 7.2
 */

import { useState, useRef, type DragEvent, type ChangeEvent } from 'react';
import { videoApi } from '../../services/api';

interface VideoUploadProps {
  indexId: string;
  onUploadComplete?: () => void;
  onUploadError?: (error: string) => void;
}

const SUPPORTED_FORMATS = ['video/mp4', 'video/quicktime', 'video/x-msvideo', 'video/x-matroska'];
const MAX_FILE_SIZE = 5 * 1024 * 1024 * 1024; // 5GB in bytes

export default function VideoUpload({ indexId, onUploadComplete, onUploadError }: VideoUploadProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const validateFile = (file: File): string | null => {
    if (!SUPPORTED_FORMATS.includes(file.type)) {
      return 'Unsupported file format. Please upload MP4, MOV, AVI, or MKV files.';
    }
    if (file.size > MAX_FILE_SIZE) {
      return 'File too large. Maximum size is 5GB.';
    }
    return null;
  };

  const handleFileSelect = (file: File) => {
    const validationError = validateFile(file);
    if (validationError) {
      setError(validationError);
      if (onUploadError) {
        onUploadError(validationError);
      }
      return;
    }
    setSelectedFile(file);
    setError(null);
  };

  const handleDragEnter = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const files = e.dataTransfer.files;
    if (files.length > 0) {
      handleFileSelect(files[0]);
    }
  };

  const handleFileInputChange = (e: ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      handleFileSelect(files[0]);
    }
  };

  const handleBrowseClick = () => {
    fileInputRef.current?.click();
  };

  const handleUpload = async () => {
    if (!selectedFile) return;

    setIsUploading(true);
    setUploadProgress(0);
    setError(null);

    try {
      await videoApi.uploadVideo(indexId, selectedFile, (progress) => {
        setUploadProgress(progress);
      });

      setSelectedFile(null);
      setUploadProgress(0);
      if (onUploadComplete) {
        onUploadComplete();
      }
    } catch (err: any) {
      const errorMessage = err.detail || err.message || 'Upload failed';
      setError(errorMessage);
      if (onUploadError) {
        onUploadError(errorMessage);
      }
    } finally {
      setIsUploading(false);
    }
  };

  const handleCancel = () => {
    setSelectedFile(null);
    setError(null);
    setUploadProgress(0);
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(2)} KB`;
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
  };

  return (
    <div className="w-full">
      {/* Drag and drop area */}
      <div
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        className={`
          relative border-2 border-dashed rounded-xl p-8 text-center
          transition-all duration-200
          ${isDragging
            ? 'border-primary/40 bg-primary/5'
            : 'border-outline-variant/40 bg-surface-container-low/50 hover:border-primary/40'
          }
          ${isUploading ? 'pointer-events-none opacity-50' : 'cursor-pointer'}
        `}
        onClick={!isUploading && !selectedFile ? handleBrowseClick : undefined}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept="video/mp4,video/quicktime,video/x-msvideo,video/x-matroska"
          onChange={handleFileInputChange}
          className="hidden"
        />

        {!selectedFile && !isUploading && (
          <>
            <div className="mb-4 flex justify-center">
              <div className="bg-surface-container-high rounded-full p-3">
                <span className="material-symbols-outlined text-4xl text-on-surface-variant">
                  cloud_upload
                </span>
              </div>
            </div>
            <p className="text-lg text-on-surface mb-2">
              Drag and drop a video file here
            </p>
            <p className="text-sm text-on-surface-variant mb-4">
              or click to browse
            </p>
            <p className="text-xs text-on-surface-variant">
              Supported formats: MP4, MOV, AVI, MKV (max 5GB)
            </p>
          </>
        )}

        {selectedFile && !isUploading && (
          <div className="space-y-4">
            <div className="flex items-center justify-center space-x-3">
              <span className="material-symbols-outlined text-3xl text-primary">
                movie
              </span>
              <div className="text-left">
                <p className="text-on-surface font-medium">{selectedFile.name}</p>
                <p className="text-sm text-on-surface-variant">{formatFileSize(selectedFile.size)}</p>
              </div>
            </div>
            <div className="flex space-x-3 justify-center">
              <button
                onClick={handleUpload}
                className="px-6 py-2 rounded-xl font-semibold
                         bg-gradient-to-r from-primary to-primary-container text-on-primary
                         hover:opacity-90
                         focus:outline-none focus:ring-2 focus:ring-primary/40
                         transform transition-all duration-200
                         hover:scale-[1.02] active:scale-[0.98]
                         shadow-lg"
              >
                Upload
              </button>
              <button
                onClick={handleCancel}
                className="px-6 py-2 rounded-xl font-semibold
                         bg-surface-container-highest text-on-surface
                         hover:bg-surface-bright
                         focus:outline-none focus:ring-2 focus:ring-outline-variant/40
                         transition-all duration-200"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {isUploading && (
          <div className="space-y-4">
            <p className="text-on-surface font-medium">Uploading {selectedFile?.name}...</p>
            <div className="w-full bg-surface-container-highest rounded-full h-3 overflow-hidden">
              <div
                className="h-full bg-primary transition-all duration-300 rounded-full"
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
            <p className="text-sm text-on-surface-variant">{uploadProgress}%</p>
          </div>
        )}
      </div>

      {/* Error message */}
      {error && (
        <div className="mt-4 p-4 bg-error/10 border border-error/30 rounded-xl">
          <p className="text-error text-sm">{error}</p>
        </div>
      )}
    </div>
  );
}