/**
 * VideoList Component Tests
 * 
 * Tests for video list display and selection functionality.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import VideoList from './VideoList';
import * as api from '../../services/api';

// Mock the API
vi.mock('../../services/api', () => ({
  videoApi: {
    listVideos: vi.fn(),
  },
}));

describe('VideoList', () => {
  const mockIndexId = 'test-index-123';
  const mockVideos = [
    {
      id: 'video-1',
      index_id: mockIndexId,
      filename: 'video1.mp4',
      s3_uri: 's3://bucket/video1',
      duration: 120,
      uploaded_at: '2024-01-01T00:00:00Z',
      embedding_ids: [],
      metadata: {},
    },
    {
      id: 'video-2',
      index_id: mockIndexId,
      filename: 'video2.mp4',
      s3_uri: 's3://bucket/video2',
      duration: 180,
      uploaded_at: '2024-01-02T00:00:00Z',
      embedding_ids: [],
      metadata: {},
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('displays loading state', () => {
    vi.mocked(api.videoApi.listVideos).mockImplementation(
      () => new Promise(() => {}) // Never resolves
    );

    render(<VideoList indexId={mockIndexId} />);
    
    expect(screen.getByRole('status', { hidden: true })).toBeInTheDocument();
  });

  it('displays videos after loading', async () => {
    vi.mocked(api.videoApi.listVideos).mockResolvedValue({
      videos: mockVideos,
      total: 2,
    });

    render(<VideoList indexId={mockIndexId} />);

    await waitFor(() => {
      expect(screen.getByText('video1.mp4')).toBeInTheDocument();
      expect(screen.getByText('video2.mp4')).toBeInTheDocument();
    });

    expect(screen.getByText(/videos \(2\)/i)).toBeInTheDocument();
  });

  it('displays empty state when no videos', async () => {
    vi.mocked(api.videoApi.listVideos).mockResolvedValue({
      videos: [],
      total: 0,
    });

    render(<VideoList indexId={mockIndexId} />);

    await waitFor(() => {
      expect(screen.getByText(/no videos in this index/i)).toBeInTheDocument();
    });
  });

  it('calls onVideoSelect when video is clicked', async () => {
    const mockOnVideoSelect = vi.fn();
    
    vi.mocked(api.videoApi.listVideos).mockResolvedValue({
      videos: mockVideos,
      total: 2,
    });

    render(
      <VideoList
        indexId={mockIndexId}
        onVideoSelect={mockOnVideoSelect}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('video1.mp4')).toBeInTheDocument();
    });

    const videoCard = screen.getByText('video1.mp4').closest('div');
    if (videoCard) {
      fireEvent.click(videoCard);
    }

    expect(mockOnVideoSelect).toHaveBeenCalledWith(mockVideos[0]);
  });

  it('highlights selected video', async () => {
    vi.mocked(api.videoApi.listVideos).mockResolvedValue({
      videos: mockVideos,
      total: 2,
    });

    render(
      <VideoList
        indexId={mockIndexId}
        selectedVideoId="video-1"
      />
    );

    await waitFor(() => {
      const videoCard = screen.getByText('video1.mp4').closest('div');
      expect(videoCard).toHaveClass('border-indigo-500');
    });
  });

  it('displays error message on API failure', async () => {
    vi.mocked(api.videoApi.listVideos).mockRejectedValue({
      detail: 'Failed to load videos',
    });

    render(<VideoList indexId={mockIndexId} />);

    await waitFor(() => {
      expect(screen.getByText(/failed to load videos/i)).toBeInTheDocument();
    });
  });
});
