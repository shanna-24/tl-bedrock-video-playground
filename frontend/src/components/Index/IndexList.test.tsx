/**
 * IndexList Component Tests
 * 
 * Tests for the IndexList component including rendering, user interactions,
 * and API integration.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import IndexList from './IndexList';
import { indexApi } from '../../services/api';
import type { Index } from '../../types';

// Mock the API module
vi.mock('../../services/api', () => ({
  indexApi: {
    listIndexes: vi.fn(),
    createIndex: vi.fn(),
    deleteIndex: vi.fn(),
  },
}));

// Mock window.confirm
const originalConfirm = window.confirm;

describe('IndexList', () => {
  const mockIndexes: Index[] = [
    {
      id: 'index-1',
      name: 'Test Index 1',
      created_at: '2024-01-01T00:00:00Z',
      video_count: 5,
      s3_vectors_collection_id: 'collection-1',
      metadata: {},
    },
    {
      id: 'index-2',
      name: 'Test Index 2',
      created_at: '2024-01-02T00:00:00Z',
      video_count: 3,
      s3_vectors_collection_id: 'collection-2',
      metadata: {},
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    window.confirm = vi.fn(() => true);
  });

  afterEach(() => {
    window.confirm = originalConfirm;
  });

  it('should render loading state initially', () => {
    vi.mocked(indexApi.listIndexes).mockImplementation(
      () => new Promise(() => {}) // Never resolves
    );

    render(<IndexList />);
    
    expect(screen.getByRole('img', { hidden: true })).toBeInTheDocument(); // Loading spinner
  });

  it('should load and display indexes', async () => {
    vi.mocked(indexApi.listIndexes).mockResolvedValue({
      indexes: mockIndexes,
      total: 2,
      max_indexes: 3,
    });

    render(<IndexList />);

    await waitFor(() => {
      expect(screen.getByText('Test Index 1')).toBeInTheDocument();
      expect(screen.getByText('Test Index 2')).toBeInTheDocument();
    });

    expect(screen.getByText('2 of 3 indexes created')).toBeInTheDocument();
    expect(screen.getByText('5 videos')).toBeInTheDocument();
    expect(screen.getByText('3 videos')).toBeInTheDocument();
  });

  it('should display empty state when no indexes exist', async () => {
    vi.mocked(indexApi.listIndexes).mockResolvedValue({
      indexes: [],
      total: 0,
      max_indexes: 3,
    });

    render(<IndexList />);

    await waitFor(() => {
      expect(screen.getByText('No indexes yet')).toBeInTheDocument();
    });

    expect(screen.getByText('Create your first index to get started')).toBeInTheDocument();
  });

  it('should display error message when loading fails', async () => {
    vi.mocked(indexApi.listIndexes).mockRejectedValue(
      new Error('Failed to load indexes')
    );

    render(<IndexList />);

    await waitFor(() => {
      expect(screen.getByText('Failed to load indexes')).toBeInTheDocument();
    });
  });

  it('should create a new index', async () => {
    const user = userEvent.setup();
    
    // Start with only 1 index so form remains visible after creation
    vi.mocked(indexApi.listIndexes).mockResolvedValue({
      indexes: [mockIndexes[0]],
      total: 1,
      max_indexes: 3,
    });

    const newIndex: Index = {
      id: 'index-3',
      name: 'New Index',
      created_at: '2024-01-03T00:00:00Z',
      video_count: 0,
      s3_vectors_collection_id: 'collection-3',
      metadata: {},
    };

    vi.mocked(indexApi.createIndex).mockResolvedValue(newIndex);

    render(<IndexList />);

    await waitFor(() => {
      expect(screen.getByText('Test Index 1')).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText(/Enter index name/i);
    const createButton = screen.getByRole('button', { name: /Create Index/i });

    await user.type(input, 'New Index');
    await user.click(createButton);

    await waitFor(() => {
      expect(indexApi.createIndex).toHaveBeenCalledWith('New Index');
      expect(screen.getByText('New Index')).toBeInTheDocument();
    });

    // Input should be cleared after creation
    await waitFor(() => {
      expect(input).toHaveValue('');
    });
  });

  it('should validate index name length', async () => {
    const user = userEvent.setup();
    
    vi.mocked(indexApi.listIndexes).mockResolvedValue({
      indexes: [],
      total: 0,
      max_indexes: 3,
    });

    render(<IndexList />);

    await waitFor(() => {
      expect(screen.getByText('No indexes yet')).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText(/Enter index name/i);
    const createButton = screen.getByRole('button', { name: /Create Index/i });

    // Test too short
    await user.type(input, 'ab');
    await user.click(createButton);

    await waitFor(() => {
      expect(screen.getByText(/must be between 3 and 50 characters/i)).toBeInTheDocument();
    });

    expect(indexApi.createIndex).not.toHaveBeenCalled();
  });

  it('should disable create button when max indexes reached', async () => {
    vi.mocked(indexApi.listIndexes).mockResolvedValue({
      indexes: [mockIndexes[0], mockIndexes[1], { ...mockIndexes[0], id: 'index-3' }],
      total: 3,
      max_indexes: 3,
    });

    render(<IndexList />);

    await waitFor(() => {
      expect(screen.getByText('3 of 3 indexes created')).toBeInTheDocument();
    });

    expect(screen.queryByPlaceholderText(/Enter index name/i)).not.toBeInTheDocument();
    expect(screen.getByText(/Maximum number of indexes \(3\) reached/i)).toBeInTheDocument();
  });

  it('should delete an index', async () => {
    const user = userEvent.setup();
    
    vi.mocked(indexApi.listIndexes).mockResolvedValue({
      indexes: mockIndexes,
      total: 2,
      max_indexes: 3,
    });

    vi.mocked(indexApi.deleteIndex).mockResolvedValue({
      message: 'Index deleted successfully',
      deleted_id: 'index-1',
    });

    render(<IndexList />);

    await waitFor(() => {
      expect(screen.getByText('Test Index 1')).toBeInTheDocument();
    });

    const deleteButtons = screen.getAllByTitle('Delete index');
    await user.click(deleteButtons[0]);

    await waitFor(() => {
      expect(indexApi.deleteIndex).toHaveBeenCalledWith('index-1');
      expect(screen.queryByText('Test Index 1')).not.toBeInTheDocument();
    });

    expect(screen.getByText('Test Index 2')).toBeInTheDocument();
  });

  it('should not delete index if user cancels confirmation', async () => {
    const user = userEvent.setup();
    window.confirm = vi.fn(() => false);
    
    vi.mocked(indexApi.listIndexes).mockResolvedValue({
      indexes: mockIndexes,
      total: 2,
      max_indexes: 3,
    });

    render(<IndexList />);

    await waitFor(() => {
      expect(screen.getByText('Test Index 1')).toBeInTheDocument();
    });

    const deleteButtons = screen.getAllByTitle('Delete index');
    await user.click(deleteButtons[0]);

    expect(indexApi.deleteIndex).not.toHaveBeenCalled();
    expect(screen.getByText('Test Index 1')).toBeInTheDocument();
  });

  it('should call onIndexSelect when an index is clicked', async () => {
    const user = userEvent.setup();
    const onIndexSelect = vi.fn();
    
    vi.mocked(indexApi.listIndexes).mockResolvedValue({
      indexes: mockIndexes,
      total: 2,
      max_indexes: 3,
    });

    render(<IndexList onIndexSelect={onIndexSelect} />);

    await waitFor(() => {
      expect(screen.getByText('Test Index 1')).toBeInTheDocument();
    });

    await user.click(screen.getByText('Test Index 1'));

    expect(onIndexSelect).toHaveBeenCalledWith(mockIndexes[0]);
  });

  it('should highlight selected index', async () => {
    vi.mocked(indexApi.listIndexes).mockResolvedValue({
      indexes: mockIndexes,
      total: 2,
      max_indexes: 3,
    });

    render(<IndexList selectedIndexId="index-1" />);

    await waitFor(() => {
      expect(screen.getByText('Test Index 1')).toBeInTheDocument();
    });

    // Check that the selected index has the purple border
    const selectedIndexElement = screen.getByText('Test Index 1').closest('div[class*="border-gray-200"]');
    expect(selectedIndexElement).toBeInTheDocument();
  });

  it('should display index limit indicator dots', async () => {
    vi.mocked(indexApi.listIndexes).mockResolvedValue({
      indexes: mockIndexes,
      total: 2,
      max_indexes: 3,
    });

    render(<IndexList />);

    await waitFor(() => {
      expect(screen.getByText('Test Index 1')).toBeInTheDocument();
    });

    // Check for indicator dots (3 total, 2 filled)
    const dots = screen.getAllByTitle(/Index \d+/);
    expect(dots).toHaveLength(3);
  });

  it('should auto-select newly created index', async () => {
    const user = userEvent.setup();
    const onIndexSelect = vi.fn();
    
    vi.mocked(indexApi.listIndexes).mockResolvedValue({
      indexes: [],
      total: 0,
      max_indexes: 3,
    });

    const newIndex: Index = {
      id: 'index-1',
      name: 'New Index',
      created_at: '2024-01-01T00:00:00Z',
      video_count: 0,
      s3_vectors_collection_id: 'collection-1',
      metadata: {},
    };

    vi.mocked(indexApi.createIndex).mockResolvedValue(newIndex);

    render(<IndexList onIndexSelect={onIndexSelect} />);

    await waitFor(() => {
      expect(screen.getByText('No indexes yet')).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText(/Enter index name/i);
    const createButton = screen.getByRole('button', { name: /Create Index/i });

    await user.type(input, 'New Index');
    await user.click(createButton);

    await waitFor(() => {
      expect(onIndexSelect).toHaveBeenCalledWith(newIndex);
    });
  });
});
