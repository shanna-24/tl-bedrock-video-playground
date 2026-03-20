import { describe, it, expect, afterEach } from 'vitest';
import { render, cleanup } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import Sidebar from '../Sidebar';

afterEach(cleanup);

describe('Sidebar', () => {
  it('renders the Indexes header and Active Collections subtitle', () => {
    const { getByText } = render(<Sidebar><div /></Sidebar>);
    expect(getByText('Indexes')).toBeInTheDocument();
    expect(getByText('Active Collections')).toBeInTheDocument();
  });

  it('renders children in the scrollable area', () => {
    const { getByTestId } = render(
      <Sidebar>
        <div data-testid="child-content">Index items here</div>
      </Sidebar>
    );
    expect(getByTestId('child-content')).toBeInTheDocument();
  });

  it('renders Settings and Support links at the bottom', () => {
    const { getByText } = render(<Sidebar><div /></Sidebar>);
    expect(getByText('Settings')).toBeInTheDocument();
    expect(getByText('Support')).toBeInTheDocument();
  });

  it('applies fixed positioning classes', () => {
    const { container } = render(<Sidebar><div /></Sidebar>);
    const aside = container.querySelector('aside');
    expect(aside).toHaveClass('fixed', 'left-0', 'top-16', 'w-64', 'h-[calc(100vh-64px)]');
  });

  it('applies surface-container-low background', () => {
    const { container } = render(<Sidebar><div /></Sidebar>);
    const aside = container.querySelector('aside');
    expect(aside).toHaveClass('bg-surface-container-low');
  });

  it('has a scrollable children area with custom-scrollbar', () => {
    const { container, getByTestId } = render(
      <Sidebar>
        <div data-testid="child">test</div>
      </Sidebar>
    );
    const scrollArea = container.querySelector('.overflow-y-auto.custom-scrollbar');
    expect(scrollArea).toBeInTheDocument();
    expect(scrollArea).toContainElement(getByTestId('child'));
  });
});
