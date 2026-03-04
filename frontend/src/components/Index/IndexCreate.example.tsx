/**
 * IndexCreate Component Usage Example
 * 
 * This example demonstrates how to use the IndexCreate component
 * in different scenarios.
 */

import { useState } from 'react';
import IndexCreate from './IndexCreate';
import type { Index } from '../../types';

/**
 * Example 1: Basic usage with callbacks
 */
export function BasicIndexCreateExample() {
  const [indexes, setIndexes] = useState<Index[]>([]);
  const [error, setError] = useState<string | null>(null);

  const handleIndexCreated = (newIndex: Index) => {
    console.log('New index created:', newIndex);
    setIndexes([...indexes, newIndex]);
    setError(null);
  };

  const handleError = (errorMessage: string) => {
    console.error('Error creating index:', errorMessage);
    setError(errorMessage);
  };

  return (
    <div className="p-6 bg-gray-900 min-h-screen">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Create Video Index</h1>
      
      {error && (
        <div className="mb-4 bg-red-500/20 border border-red-500/50 rounded-lg p-3">
          <p className="text-red-200 text-sm">{error}</p>
        </div>
      )}

      <IndexCreate
        currentIndexCount={indexes.length}
        maxIndexes={3}
        onIndexCreated={handleIndexCreated}
        onError={handleError}
      />

      {/* Display created indexes */}
      {indexes.length > 0 && (
        <div className="mt-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-3">Created Indexes</h2>
          <div className="space-y-2">
            {indexes.map((index) => (
              <div
                key={index.id}
                className="bg-white rounded-lg p-3 border border-white/10"
              >
                <p className="text-gray-900 font-medium">{index.name}</p>
                <p className="text-gray-500 text-sm">ID: {index.id}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * Example 2: Integrated with parent component state
 */
export function IntegratedIndexCreateExample() {
  const [currentCount, setCurrentCount] = useState(2);
  const maxIndexes = 3;

  const handleIndexCreated = (newIndex: Index) => {
    console.log('Index created:', newIndex);
    setCurrentCount(currentCount + 1);
    // In a real app, you would also update your indexes list
  };

  return (
    <div className="p-6 bg-gray-900 min-h-screen">
      <div className="mb-4">
        <p className="text-gray-900">
          Current indexes: {currentCount} / {maxIndexes}
        </p>
      </div>

      <IndexCreate
        currentIndexCount={currentCount}
        maxIndexes={maxIndexes}
        onIndexCreated={handleIndexCreated}
      />
    </div>
  );
}

/**
 * Example 3: At max limit
 */
export function MaxLimitIndexCreateExample() {
  return (
    <div className="p-6 bg-gray-900 min-h-screen">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Index Limit Reached</h1>
      
      <IndexCreate
        currentIndexCount={3}
        maxIndexes={3}
      />
    </div>
  );
}

/**
 * Example 4: Minimal usage (no callbacks)
 */
export function MinimalIndexCreateExample() {
  return (
    <div className="p-6 bg-gray-900 min-h-screen">
      <IndexCreate
        currentIndexCount={0}
        maxIndexes={3}
      />
    </div>
  );
}
