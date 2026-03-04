/**
 * SearchBar Component Tests
 * 
 * Tests for search input and submission functionality.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import SearchBar from './SearchBar';

describe('SearchBar', () => {
  it('renders search input with placeholder', () => {
    const mockOnSearch = vi.fn();
    render(<SearchBar onSearch={mockOnSearch} />);
    
    const input = screen.getByPlaceholderText(/search videos with natural language/i);
    expect(input).toBeInTheDocument();
  });

  it('calls onSearch with query when form is submitted', () => {
    const mockOnSearch = vi.fn();
    render(<SearchBar onSearch={mockOnSearch} />);
    
    const input = screen.getByPlaceholderText(/search videos with natural language/i);
    const searchButton = screen.getByRole('button', { name: /search/i });

    fireEvent.change(input, { target: { value: 'people talking' } });
    fireEvent.click(searchButton);

    // Should be called with query, topK, imageFile, modalities, transcriptionMode, and videoId
    expect(mockOnSearch).toHaveBeenCalledWith(
      'people talking',
      5,
      undefined,
      ['visual', 'audio', 'transcription'],
      'both',
      undefined
    );
  });

  it('trims whitespace from query', () => {
    const mockOnSearch = vi.fn();
    render(<SearchBar onSearch={mockOnSearch} />);
    
    const input = screen.getByPlaceholderText(/search videos with natural language/i);
    const searchButton = screen.getByRole('button', { name: /search/i });

    fireEvent.change(input, { target: { value: '  people talking  ' } });
    fireEvent.click(searchButton);

    expect(mockOnSearch).toHaveBeenCalledWith(
      'people talking',
      5,
      undefined,
      ['visual', 'audio', 'transcription'],
      'both',
      undefined
    );
  });

  it('does not call onSearch with empty query', () => {
    const mockOnSearch = vi.fn();
    render(<SearchBar onSearch={mockOnSearch} />);
    
    const searchButton = screen.getByRole('button', { name: /search/i });
    fireEvent.click(searchButton);

    expect(mockOnSearch).not.toHaveBeenCalled();
  });

  it('shows loading state when searching', () => {
    const mockOnSearch = vi.fn();
    render(<SearchBar onSearch={mockOnSearch} isSearching={true} />);
    
    expect(screen.getByText(/searching\.\.\./i)).toBeInTheDocument();
  });

  it('disables input and button when searching', () => {
    const mockOnSearch = vi.fn();
    render(<SearchBar onSearch={mockOnSearch} isSearching={true} />);
    
    const input = screen.getByPlaceholderText(/search videos with natural language/i);
    const searchButton = screen.getByRole('button', { name: /searching\.\.\./i });

    expect(input).toBeDisabled();
    expect(searchButton).toBeDisabled();
  });

  it('shows clear button when query is entered', () => {
    const mockOnSearch = vi.fn();
    render(<SearchBar onSearch={mockOnSearch} />);
    
    const input = screen.getByPlaceholderText(/search videos with natural language/i);
    fireEvent.change(input, { target: { value: 'test query' } });

    const clearButton = screen.getByTitle('Clear');
    expect(clearButton).toBeInTheDocument();
  });

  it('clears query when clear button is clicked', () => {
    const mockOnSearch = vi.fn();
    render(<SearchBar onSearch={mockOnSearch} />);
    
    const input = screen.getByPlaceholderText(/search videos with natural language/i) as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'test query' } });

    const clearButton = screen.getByTitle('Clear');
    fireEvent.click(clearButton);

    expect(input.value).toBe('');
  });

  it('renders modality toggle buttons', () => {
    const mockOnSearch = vi.fn();
    render(<SearchBar onSearch={mockOnSearch} />);
    
    expect(screen.getByRole('button', { name: /visual/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /audio/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /transcription/i })).toBeInTheDocument();
  });

  it('toggles modality when button is clicked', () => {
    const mockOnSearch = vi.fn();
    render(<SearchBar onSearch={mockOnSearch} />);
    
    const visualButton = screen.getByRole('button', { name: /visual/i });
    
    // Click to deselect visual
    fireEvent.click(visualButton);
    
    // Now search should only include audio and transcription
    const input = screen.getByPlaceholderText(/search videos with natural language/i);
    const searchButton = screen.getByRole('button', { name: /search/i });
    
    fireEvent.change(input, { target: { value: 'test' } });
    fireEvent.click(searchButton);
    
    // Check that visual is not in the modalities array (4th argument)
    expect(mockOnSearch).toHaveBeenCalled();
    const callArgs = mockOnSearch.mock.calls[0];
    expect(callArgs[3]).toContain('audio');
    expect(callArgs[3]).toContain('transcription');
    expect(callArgs[3]).not.toContain('visual');
  });

  it('disables search button when no modalities selected', () => {
    const mockOnSearch = vi.fn();
    render(<SearchBar onSearch={mockOnSearch} />);
    
    // Deselect all modalities (including lexical)
    fireEvent.click(screen.getByRole('button', { name: /visual/i }));
    fireEvent.click(screen.getByRole('button', { name: /audio/i }));
    fireEvent.click(screen.getByRole('button', { name: /transcription/i }));
    fireEvent.click(screen.getByRole('button', { name: /lexical/i }));
    
    // Enter a query
    const input = screen.getByPlaceholderText(/search videos with natural language/i);
    fireEvent.change(input, { target: { value: 'test' } });
    
    // Search button should be disabled
    const searchButton = screen.getByRole('button', { name: /search/i });
    expect(searchButton).toBeDisabled();
    
    // Warning message should appear
    expect(screen.getByText(/select at least one modality/i)).toBeInTheDocument();
  });
});
