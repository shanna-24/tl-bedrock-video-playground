/**
 * SearchResults Component Tests
 * 
 * Tests for search results display and clip selection.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import SearchResults from './SearchResults';
import type { VideoClip } from '../../types';

describe('SearchResults', () => {
  const mockClips: VideoClip[] = [
    {
      video_id: 'video-1',
      start_timecode: 10,
      end_timecode: 20,
      relevance_score: 0.95,
      screenshot_url: 'https://example.com/screenshot1.jpg',
      video_stream_url: 'https://example.com/video1',
      metadata: {},
    },
    {
      video_id: 'video-2',
      start_timecode: 30,
      end_timecode: 45,
      relevance_score: 0.75,
      screenshot_url: 'https://example.com/screenshot2.jpg',
      video_stream_url: 'https://example.com/video2',
      metadata: {},
    },
  ];

  it('displays search results header with count', () => {
    render(
      <SearchResults
        results={mockClips}
        query="people talking"
        searchTime={1.5}
      />
    );

    expect(screen.getByText(/search results/i)).toBeInTheDocument();
    expect(screen.getByText(/found 2 clips for "people talking"/i)).toBeInTheDocument();
    expect(screen.getByText(/in 1\.50s/i)).toBeInTheDocument();
  });

  it('displays empty state when no results', () => {
    render(
      <SearchResults
        results={[]}
        query="test query"
      />
    );

    expect(screen.getByText(/no results found/i)).toBeInTheDocument();
  });

  it('displays clip timecodes', () => {
    render(
      <SearchResults
        results={mockClips}
        query="test"
      />
    );

    expect(screen.getByText('0:10')).toBeInTheDocument();
    expect(screen.getByText('0:20')).toBeInTheDocument();
    expect(screen.getByText('0:30')).toBeInTheDocument();
    expect(screen.getByText('0:45')).toBeInTheDocument();
  });

  it('displays relevance scores', () => {
    render(
      <SearchResults
        results={mockClips}
        query="test"
      />
    );

    expect(screen.getByText('95%')).toBeInTheDocument();
    expect(screen.getByText('75%')).toBeInTheDocument();
  });

  it('calls onClipSelect when clip is clicked', () => {
    const mockOnClipSelect = vi.fn();
    
    render(
      <SearchResults
        results={mockClips}
        query="test"
        onClipSelect={mockOnClipSelect}
      />
    );

    const firstClip = screen.getByText('0:10').closest('div');
    if (firstClip) {
      fireEvent.click(firstClip);
    }

    expect(mockOnClipSelect).toHaveBeenCalledWith(mockClips[0]);
  });

  it('displays screenshots when available', () => {
    render(
      <SearchResults
        results={mockClips}
        query="test"
      />
    );

    const images = screen.getAllByRole('img');
    expect(images).toHaveLength(2);
    expect(images[0]).toHaveAttribute('src', mockClips[0].screenshot_url);
  });
});
