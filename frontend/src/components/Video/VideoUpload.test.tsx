/**
 * VideoUpload Component Tests
 * 
 * Tests for video upload functionality including drag-and-drop,
 * file validation, and progress tracking.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import VideoUpload from './VideoUpload';
import * as api from '../../services/api';

// Mock the API
vi.mock('../../services/api', () => ({
  videoApi: {
    uploadVideo: vi.fn(),
  },
}));

describe('VideoUpload', () => {
  const mockIndexId = 'test-index-123';
  const mockOnUploadComplete = vi.fn();
  const mockOnUploadError = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders upload area with instructions', () => {
    render(<VideoUpload indexId={mockIndexId} />);
    
    expect(screen.getByText(/drag and drop a video file here/i)).toBeInTheDocument();
    expect(screen.getByText(/or click to browse/i)).toBeInTheDocument();
    expect(screen.getByText(/supported formats: mp4, mov, avi, mkv/i)).toBeInTheDocument();
  });

  it('validates file format', async () => {
    render(
      <VideoUpload
        indexId={mockIndexId}
        onUploadError={mockOnUploadError}
      />
    );

    const file = new File(['test'], 'test.txt', { type: 'text/plain' });
    const input = screen.getByRole('textbox', { hidden: true }) as HTMLInputElement;
    
    Object.defineProperty(input, 'files', {
      value: [file],
      writable: false,
    });

    fireEvent.change(input);

    await waitFor(() => {
      expect(mockOnUploadError).toHaveBeenCalledWith(
        expect.stringContaining('Unsupported file format')
      );
    });
  });

  it('shows selected file information', async () => {
    render(<VideoUpload indexId={mockIndexId} />);

    const file = new File(['test'], 'test-video.mp4', { type: 'video/mp4' });
    const input = screen.getByRole('textbox', { hidden: true }) as HTMLInputElement;
    
    Object.defineProperty(input, 'files', {
      value: [file],
      writable: false,
    });

    fireEvent.change(input);

    await waitFor(() => {
      expect(screen.getByText('test-video.mp4')).toBeInTheDocument();
      expect(screen.getByText(/upload/i)).toBeInTheDocument();
      expect(screen.getByText(/cancel/i)).toBeInTheDocument();
    });
  });

  it('calls onUploadComplete after successful upload', async () => {
    const mockVideo = {
      id: 'video-123',
      index_id: mockIndexId,
      filename: 'test-video.mp4',
      s3_uri: 's3://bucket/video',
      duration: 120,
      uploaded_at: new Date().toISOString(),
      embedding_ids: [],
      metadata: {},
    };

    vi.mocked(api.videoApi.uploadVideo).mockResolvedValue(mockVideo);

    render(
      <VideoUpload
        indexId={mockIndexId}
        onUploadComplete={mockOnUploadComplete}
      />
    );

    const file = new File(['test'], 'test-video.mp4', { type: 'video/mp4' });
    const input = screen.getByRole('textbox', { hidden: true }) as HTMLInputElement;
    
    Object.defineProperty(input, 'files', {
      value: [file],
      writable: false,
    });

    fireEvent.change(input);

    await waitFor(() => {
      expect(screen.getByText('test-video.mp4')).toBeInTheDocument();
    });

    const uploadButton = screen.getByText(/^upload$/i);
    fireEvent.click(uploadButton);

    await waitFor(() => {
      expect(mockOnUploadComplete).toHaveBeenCalled();
    });
  });
});
