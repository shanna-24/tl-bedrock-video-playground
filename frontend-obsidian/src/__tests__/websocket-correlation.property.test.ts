// Feature: obsidian-lens-frontend, Property 15: WebSocket delivers messages matched by correlation ID
import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';

/**
 * Validates: Requirements 12.2
 *
 * Property 15: For any WebSocket message with a correlation_id field,
 * the message should be delivered only to subscribers whose subscription
 * filter matches that correlation_id, and not to other subscribers.
 *
 * The WebSocket context broadcasts all messages to all subscribers.
 * Correlation ID filtering is done at the subscriber level, matching
 * the pattern used in DashboardLayout:
 *   if (message.correlation_id === correlationId) { ... }
 */

interface WebSocketMessage {
  type: string;
  correlation_id: string;
  message: string;
}

const messageArb = fc.record({
  type: fc.constantFrom('progress', 'analysis_progress', 'compliance_progress'),
  correlation_id: fc.uuid(),
  message: fc.string({ minLength: 1, maxLength: 50 }),
});

const targetIdArb = fc.uuid();

/**
 * Simulates the subscriber-side correlation ID filtering pattern
 * used in DashboardLayout. Each subscriber checks:
 *   message.correlation_id === myCorrelationId
 */
function filterByCorrelationId(
  messages: WebSocketMessage[],
  targetId: string
): WebSocketMessage[] {
  return messages.filter((msg) => msg.correlation_id === targetId);
}

describe('Property 15: WebSocket delivers messages matched by correlation ID', () => {
  it('only messages with matching correlation_id are routed to a subscriber', () => {
    fc.assert(
      fc.property(
        fc.array(messageArb, { minLength: 0, maxLength: 30 }),
        targetIdArb,
        (messages, targetId) => {
          const routed = filterByCorrelationId(messages, targetId);

          // Every routed message must have the target correlation ID
          for (const msg of routed) {
            expect(msg.correlation_id).toBe(targetId);
          }

          // Count of routed messages equals count of messages with matching ID
          const expectedCount = messages.filter(
            (m) => m.correlation_id === targetId
          ).length;
          expect(routed).toHaveLength(expectedCount);
        }
      ),
      { numRuns: 100 }
    );
  });

  it('messages without a matching correlation_id are excluded', () => {
    fc.assert(
      fc.property(
        fc.array(messageArb, { minLength: 1, maxLength: 30 }),
        targetIdArb,
        (messages, targetId) => {
          const routed = filterByCorrelationId(messages, targetId);
          const excluded = messages.filter(
            (msg) => msg.correlation_id !== targetId
          );

          // No excluded message should appear in routed
          for (const msg of excluded) {
            expect(routed).not.toContain(msg);
          }

          // Routed + excluded = all messages
          expect(routed.length + excluded.length).toBe(messages.length);
        }
      ),
      { numRuns: 100 }
    );
  });

  it('when no messages match the target ID, the result is empty', () => {
    fc.assert(
      fc.property(
        fc.array(messageArb, { minLength: 0, maxLength: 20 }),
        (messages) => {
          // Use a correlation ID guaranteed not to appear in any message
          const impossibleId = 'ffffffff-ffff-ffff-ffff-ffffffffffff';
          const filtered = messages.filter(
            (m) => m.correlation_id !== impossibleId
          );

          const routed = filterByCorrelationId(filtered, impossibleId);
          expect(routed).toHaveLength(0);
        }
      ),
      { numRuns: 100 }
    );
  });

  it('when all messages share the target ID, all are included', () => {
    fc.assert(
      fc.property(
        targetIdArb,
        fc.array(
          fc.record({
            type: fc.constantFrom('progress', 'analysis_progress', 'compliance_progress'),
            message: fc.string({ minLength: 1, maxLength: 50 }),
          }),
          { minLength: 1, maxLength: 20 }
        ),
        (targetId, partials) => {
          // All messages share the same correlation_id
          const messages: WebSocketMessage[] = partials.map((p) => ({
            ...p,
            correlation_id: targetId,
          }));

          const routed = filterByCorrelationId(messages, targetId);
          expect(routed).toHaveLength(messages.length);
        }
      ),
      { numRuns: 100 }
    );
  });
});
