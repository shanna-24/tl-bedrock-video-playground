/**
 * VideoUpload Component
 * 
 * Provides drag-and-drop video upload functionality with progress tracking.
 * Validates file format and size before upload.
 * 
 * Validates: Requirements 1.4
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
    // Check file format
    if (!SUPPORTED_FORMATS.includes(file.type)) {
      return 'Unsupported file format. Please upload MP4, MOV, AVI, or MKV files.';
    }

    // Check file size
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

      // Upload complete
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
          relative border-2 border-dashed rounded-lg p-8 text-center
          transition-all duration-200
          ${isDragging 
            ? 'border-indigo-500 dark:border-lime-500 bg-indigo-500/10 dark:bg-lime-500/20' 
            : 'border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700/50 hover:border-gray-400 dark:hover:border-gray-500 hover:bg-gray-50 dark:hover:bg-gray-700/70'
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
            <div className="mb-4">
              <svg
                className="mx-auto h-12 w-12 text-gray-500 dark:text-gray-300"
                stroke="currentColor"
                fill="none"
                viewBox="0 0 48 48"
                aria-hidden="true"
              >
                <path
                  d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02"
                  strokeWidth={2}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </div>
            <p className="text-lg text-gray-900 dark:text-gray-100 mb-2">
              Drag and drop a video file here
            </p>
            <p className="text-sm text-gray-500 dark:text-gray-300 mb-4">
              or click to browse
            </p>
            <p className="text-xs text-gray-500 dark:text-gray-300">
              Supported formats: MP4, MOV, AVI, MKV (max 5GB)
            </p>
          </>
        )}

        {selectedFile && !isUploading && (
          <div className="space-y-4">
            <div className="flex items-center justify-center space-x-2">
              <svg
                className="h-8 w-8 text-green-500 dark:text-green-400"
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
              <div className="text-left">
                <p className="text-gray-900 dark:text-gray-100 font-medium">{selectedFile.name}</p>
                <p className="text-sm text-gray-500 dark:text-gray-400">{formatFileSize(selectedFile.size)}</p>
              </div>
            </div>
            <div className="flex space-x-3 justify-center">
              <button
                onClick={handleUpload}
                className="px-6 py-2 rounded-lg font-semibold text-white
                         bg-indigo-500 dark:bg-lime-500
                         hover:bg-indigo-600 dark:hover:bg-lime-600
                         focus:outline-none focus:ring-2 focus:ring-indigo-400 dark:focus:ring-lime-400
                         transform transition-all duration-200
                         hover:scale-[1.02] active:scale-[0.98]
                         shadow-lg"
              >
                Upload
              </button>
              <button
                onClick={handleCancel}
                className="px-6 py-2 rounded-lg font-semibold
                         text-gray-700 dark:text-gray-200
                         bg-gray-200 dark:bg-gray-600
                         hover:bg-gray-300 dark:hover:bg-gray-500
                         focus:outline-none focus:ring-2 focus:ring-gray-300 dark:focus:ring-gray-400
                         transition-all duration-200"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {isUploading && (
          <div className="space-y-4">
            <p className="text-gray-900 dark:text-gray-100 font-medium">Uploading {selectedFile?.name}...</p>
            <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-3 overflow-hidden">
              <div
                className="h-full bg-indigo-500 dark:bg-lime-500 transition-all duration-300"
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
            <p className="text-sm text-gray-500 dark:text-gray-400">{uploadProgress}%</p>
          </div>
        )}
      </div>

      {/* Error message */}
      {error && (
        <div className="mt-4 p-4 bg-red-500/10 border border-red-500/50 rounded-lg">
          <p className="text-red-400 text-sm">{error}</p>
        </div>
      )}
    </div>
  );
}
