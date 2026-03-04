/**
 * IndexCreate Component Tests
 * 
 * Tests for the IndexCreate component including rendering, validation,
 * and API integration.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import IndexCreate from './IndexCreate';
import { indexApi } from '../../services/api';
import type { Index } from '../../types';

// Mock the API module
vi.mock('../../services/api', () => ({
  indexApi: {
    createIndex: vi.fn(),
  },
}));

describe('IndexCreate', () => {
  const mockIndex: Index = {
    id: 'index-1',
    name: 'Test Index',
    created_at: '2024-01-01T00:00:00Z',
    video_count: 0,
    s3_vectors_collection_id: 'collection-1',
    metadata: {},
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('should render create form when under index limit', () => {
      render(
        <IndexCreate
          currentIndexCount={1}
          maxIndexes={3}
        />
      );

      expect(screen.getByPlaceholderText(/Enter index name/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Create Index/i })).toBeInTheDocument();
    });

    it('should render max limit message when at index limit', () => {
      render(
        <IndexCreate
          currentIndexCount={3}
          maxIndexes={3}
        />
      );

      expect(screen.queryByPlaceholderText(/Enter index name/i)).not.toBeInTheDocument();
      expect(screen.getByText(/Maximum number of indexes \(3\) reached/i)).toBeInTheDocument();
    });

    it('should render max limit message when over index limit', () => {
      render(
        <IndexCreate
          currentIndexCount={5}
          maxIndexes={3}
        />
      );

      expect(screen.queryByPlaceholderText(/Enter index name/i)).not.toBeInTheDocument();
      expect(screen.getByText(/Maximum number of indexes \(3\) reached/i)).toBeInTheDocument();
    });
  });

  describe('Index Creation', () => {
    it('should create index with valid name', async () => {
      const user = userEvent.setup();
      const onIndexCreated = vi.fn();

      vi.mocked(indexApi.createIndex).mockResolvedValue(mockIndex);

      render(
        <IndexCreate
          currentIndexCount={0}
          maxIndexes={3}
          onIndexCreated={onIndexCreated}
        />
      );

      const input = screen.getByPlaceholderText(/Enter index name/i);
      const createButton = screen.getByRole('button', { name: /Create Index/i });

      await user.type(input, 'Test Index');
      await user.click(createButton);

      await waitFor(() => {
        expect(indexApi.createIndex).toHaveBeenCalledWith('Test Index');
        expect(onIndexCreated).toHaveBeenCalledWith(mockIndex);
      });

      // Input should be cleared after creation
      expect(input).toHaveValue('');
    });

    it('should trim whitespace from index name', async () => {
      const user = userEvent.setup();
      const onIndexCreated = vi.fn();

      vi.mocked(indexApi.createIndex).mockResolvedValue(mockIndex);

      render(
        <IndexCreate
          currentIndexCount={0}
          maxIndexes={3}
          onIndexCreated={onIndexCreated}
        />
      );

      const input = screen.getByPlaceholderText(/Enter index name/i);
      const createButton = screen.getByRole('button', { name: /Create Index/i });

      await user.type(input, '  Test Index  ');
      await user.click(createButton);

      await waitFor(() => {
        expect(indexApi.createIndex).toHaveBeenCalledWith('Test Index');
      });
    });

    it('should show loading state during creation', async () => {
      const user = userEvent.setup();

      vi.mocked(indexApi.createIndex).mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve(mockIndex), 100))
      );

      render(
        <IndexCreate
          currentIndexCount={0}
          maxIndexes={3}
        />
      );

      const input = screen.getByPlaceholderText(/Enter index name/i);
      const createButton = screen.getByRole('button', { name: /Create Index/i });

      await user.type(input, 'Test Index');
      await user.click(createButton);

      // Should show loading state
      expect(screen.getByText(/Creating.../i)).toBeInTheDocument();
      expect(createButton).toBeDisabled();
      expect(input).toBeDisabled();

      // Wait for completion
      await waitFor(() => {
        expect(screen.queryByText(/Creating.../i)).not.toBeInTheDocument();
      });
    });

    it('should disable submit button when input is empty', () => {
      render(
        <IndexCreate
          currentIndexCount={0}
          maxIndexes={3}
        />
      );

      const createButton = screen.getByRole('button', { name: /Create Index/i });
      expect(createButton).toBeDisabled();
    });

    it('should disable submit button when input is only whitespace', async () => {
      const user = userEvent.setup();

      render(
        <IndexCreate
          currentIndexCount={0}
          maxIndexes={3}
        />
      );

      const input = screen.getByPlaceholderText(/Enter index name/i);
      const createButton = screen.getByRole('button', { name: /Create Index/i });

      await user.type(input, '   ');
      expect(createButton).toBeDisabled();
    });
  });

  describe('Validation', () => {
    it('should validate empty index name', async () => {
      const user = userEvent.setup();
      const onError = vi.fn();

      render(
        <IndexCreate
          currentIndexCount={0}
          maxIndexes={3}
          onError={onError}
        />
      );

      const input = screen.getByPlaceholderText(/Enter index name/i);
      const createButton = screen.getByRole('button', { name: /Create Index/i });

      // Type and then clear the input
      await user.type(input, 'test');
      await user.clear(input);
      
      // Try to submit with empty input (button should be disabled, but test the validation)
      // We need to trigger the form submission programmatically
      const form = createButton.closest('form');
      if (form) {
        form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      }

      await waitFor(() => {
        expect(screen.getByText(/Index name cannot be empty/i)).toBeInTheDocument();
        expect(onError).toHaveBeenCalledWith('Index name cannot be empty');
      });

      expect(indexApi.createIndex).not.toHaveBeenCalled();
    });

    it('should validate index name too short', async () => {
      const user = userEvent.setup();
      const onError = vi.fn();

      render(
        <IndexCreate
          currentIndexCount={0}
          maxIndexes={3}
          onError={onError}
        />
      );

      const input = screen.getByPlaceholderText(/Enter index name/i);
      const createButton = screen.getByRole('button', { name: /Create Index/i });

      await user.type(input, 'ab');
      await user.click(createButton);

      await waitFor(() => {
        expect(screen.getByText(/must be between 3 and 50 characters/i)).toBeInTheDocument();
        expect(onError).toHaveBeenCalledWith('Index name must be between 3 and 50 characters');
      });

      expect(indexApi.createIndex).not.toHaveBeenCalled();
    });

    it('should validate index name too long', async () => {
      const user = userEvent.setup();
      const onError = vi.fn();

      vi.mocked(indexApi.createIndex).mockResolvedValue(mockIndex);

      render(
        <IndexCreate
          currentIndexCount={0}
          maxIndexes={3}
          onError={onError}
        />
      );

      const input = screen.getByPlaceholderText(/Enter index name/i);
      const createButton = screen.getByRole('button', { name: /Create Index/i });

      // Note: The HTML maxlength attribute prevents typing more than 50 characters
      // So we test that the input is limited to 50 characters
      const longName = 'a'.repeat(51);
      await user.type(input, longName);
      
      // The input should only contain 50 characters due to maxlength attribute
      expect(input).toHaveValue('a'.repeat(50));
      
      // This should succeed since it's exactly 50 characters
      await user.click(createButton);

      await waitFor(() => {
        expect(indexApi.createIndex).toHaveBeenCalledWith('a'.repeat(50));
      });
    });

    it('should accept index name at minimum length (3 characters)', async () => {
      const user = userEvent.setup();
      const onIndexCreated = vi.fn();

      vi.mocked(indexApi.createIndex).mockResolvedValue(mockIndex);

      render(
        <IndexCreate
          currentIndexCount={0}
          maxIndexes={3}
          onIndexCreated={onIndexCreated}
        />
      );

      const input = screen.getByPlaceholderText(/Enter index name/i);
      const createButton = screen.getByRole('button', { name: /Create Index/i });

      await user.type(input, 'abc');
      await user.click(createButton);

      await waitFor(() => {
        expect(indexApi.createIndex).toHaveBeenCalledWith('abc');
        expect(onIndexCreated).toHaveBeenCalled();
      });
    });

    it('should accept index name at maximum length (50 characters)', async () => {
      const user = userEvent.setup();
      const onIndexCreated = vi.fn();

      vi.mocked(indexApi.createIndex).mockResolvedValue(mockIndex);

      render(
        <IndexCreate
          currentIndexCount={0}
          maxIndexes={3}
          onIndexCreated={onIndexCreated}
        />
      );

      const input = screen.getByPlaceholderText(/Enter index name/i);
      const createButton = screen.getByRole('button', { name: /Create Index/i });

      const maxLengthName = 'a'.repeat(50);
      await user.type(input, maxLengthName);
      await user.click(createButton);

      await waitFor(() => {
        expect(indexApi.createIndex).toHaveBeenCalledWith(maxLengthName);
        expect(onIndexCreated).toHaveBeenCalled();
      });
    });
  });

  describe('Error Handling', () => {
    it('should display error when API call fails', async () => {
      const user = userEvent.setup();
      const onError = vi.fn();

      vi.mocked(indexApi.createIndex).mockRejectedValue(
        new Error('Failed to create index')
      );

      render(
        <IndexCreate
          currentIndexCount={0}
          maxIndexes={3}
          onError={onError}
        />
      );

      const input = screen.getByPlaceholderText(/Enter index name/i);
      const createButton = screen.getByRole('button', { name: /Create Index/i });

      await user.type(input, 'Test Index');
      await user.click(createButton);

      await waitFor(() => {
        expect(screen.getByText(/Failed to create index/i)).toBeInTheDocument();
        expect(onError).toHaveBeenCalledWith('Failed to create index');
      });
    });

    it('should display error when API returns index limit error', async () => {
      const user = userEvent.setup();
      const onError = vi.fn();

      vi.mocked(indexApi.createIndex).mockRejectedValue(
        new Error('Maximum of 3 indexes allowed')
      );

      render(
        <IndexCreate
          currentIndexCount={2}
          maxIndexes={3}
          onError={onError}
        />
      );

      const input = screen.getByPlaceholderText(/Enter index name/i);
      const createButton = screen.getByRole('button', { name: /Create Index/i });

      await user.type(input, 'Test Index');
      await user.click(createButton);

      await waitFor(() => {
        expect(screen.getByText(/Maximum of 3 indexes allowed/i)).toBeInTheDocument();
        expect(onError).toHaveBeenCalledWith('Maximum of 3 indexes allowed');
      });
    });

    it('should clear previous error when submitting again', async () => {
      const user = userEvent.setup();

      // First call fails
      vi.mocked(indexApi.createIndex).mockRejectedValueOnce(
        new Error('Failed to create index')
      );

      render(
        <IndexCreate
          currentIndexCount={0}
          maxIndexes={3}
        />
      );

      const input = screen.getByPlaceholderText(/Enter index name/i);
      const createButton = screen.getByRole('button', { name: /Create Index/i });

      // First attempt - fails
      await user.type(input, 'Test Index');
      await user.click(createButton);

      await waitFor(() => {
        expect(screen.getByText(/Failed to create index/i)).toBeInTheDocument();
      });

      // Second attempt - succeeds
      vi.mocked(indexApi.createIndex).mockResolvedValue(mockIndex);
      
      await user.clear(input);
      await user.type(input, 'Test Index 2');
      await user.click(createButton);

      await waitFor(() => {
        expect(screen.queryByText(/Failed to create index/i)).not.toBeInTheDocument();
      });
    });

    it('should not call onIndexCreated when creation fails', async () => {
      const user = userEvent.setup();
      const onIndexCreated = vi.fn();

      vi.mocked(indexApi.createIndex).mockRejectedValue(
        new Error('Failed to create index')
      );

      render(
        <IndexCreate
          currentIndexCount={0}
          maxIndexes={3}
          onIndexCreated={onIndexCreated}
        />
      );

      const input = screen.getByPlaceholderText(/Enter index name/i);
      const createButton = screen.getByRole('button', { name: /Create Index/i });

      await user.type(input, 'Test Index');
      await user.click(createButton);

      await waitFor(() => {
        expect(screen.getByText(/Failed to create index/i)).toBeInTheDocument();
      });

      expect(onIndexCreated).not.toHaveBeenCalled();
    });
  });

  describe('Index Limit Validation', () => {
    it('should show max limit message when currentIndexCount equals maxIndexes', () => {
      render(
        <IndexCreate
          currentIndexCount={3}
          maxIndexes={3}
        />
      );

      expect(screen.getByText(/Maximum number of indexes \(3\) reached/i)).toBeInTheDocument();
      expect(screen.getByText(/Delete an index to create a new one/i)).toBeInTheDocument();
    });

    it('should show form when currentIndexCount is less than maxIndexes', () => {
      render(
        <IndexCreate
          currentIndexCount={2}
          maxIndexes={3}
        />
      );

      expect(screen.getByPlaceholderText(/Enter index name/i)).toBeInTheDocument();
      expect(screen.queryByText(/Maximum number of indexes/i)).not.toBeInTheDocument();
    });

    it('should handle different max index limits', () => {
      const { rerender } = render(
        <IndexCreate
          currentIndexCount={5}
          maxIndexes={5}
        />
      );

      expect(screen.getByText(/Maximum number of indexes \(5\) reached/i)).toBeInTheDocument();

      rerender(
        <IndexCreate
          currentIndexCount={9}
          maxIndexes={10}
        />
      );

      expect(screen.getByPlaceholderText(/Enter index name/i)).toBeInTheDocument();
      expect(screen.queryByText(/Maximum number of indexes/i)).not.toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('should have accessible form elements', () => {
      render(
        <IndexCreate
          currentIndexCount={0}
          maxIndexes={3}
        />
      );

      const input = screen.getByPlaceholderText(/Enter index name/i);
      expect(input).toHaveAttribute('aria-label', 'Index name');
      expect(input).toHaveAttribute('minLength', '3');
      expect(input).toHaveAttribute('maxLength', '50');
    });

    it('should have accessible button', () => {
      render(
        <IndexCreate
          currentIndexCount={0}
          maxIndexes={3}
        />
      );

      const button = screen.getByRole('button', { name: /Create Index/i });
      expect(button).toBeInTheDocument();
    });
  });
});
