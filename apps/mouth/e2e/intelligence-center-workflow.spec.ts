import { test, expect } from '@playwright/test';

/**
 * E2E Test: Intelligence Center - Complete Button Workflow & Coherence
 *
 * Tests che ogni bottone conduca allo step logico corretto:
 * 1. Navigation tabs (Visa Oracle, News Room, System Pulse)
 * 2. Refresh/Sync buttons
 * 3. Preview buttons (View Content / Hide Preview)
 * 4. Approve & Reject buttons with confirmations
 * 5. Retry button in error states
 * 6. External links
 *
 * Verifica: No bugs, no nonsense, logical flow
 */

test.describe('Intelligence Center - Complete Workflow', () => {
  test.beforeEach(async ({ page }) => {
    // Mock API responses for consistent testing
    await page.route('/api/intel/staging/pending*', async (route) => {
      const url = new URL(route.request().url());
      const type = url.searchParams.get('type');

      if (type === 'visa') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            items: [
              {
                id: 'visa-test-1',
                type: 'visa',
                title: 'Test Visa Regulation',
                status: 'pending',
                detected_at: new Date().toISOString(),
                source: 'https://imigrasi.go.id/test',
                detection_type: 'NEW',
              },
            ],
            count: 1,
          }),
        });
      } else if (type === 'news') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            items: [
              {
                id: 'news-test-1',
                type: 'news',
                title: 'Test News Article',
                status: 'pending',
                detected_at: new Date().toISOString(),
                source: 'Jakarta Post',
                detection_type: 'NEW',
                is_critical: true,
              },
            ],
            count: 1,
          }),
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ items: [], count: 0 }),
        });
      }
    });

    await page.route('/api/intel/staging/preview/*/*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'test-1',
          type: 'visa',
          title: 'Test Item',
          status: 'pending',
          detected_at: new Date().toISOString(),
          source: 'https://test.com',
          detection_type: 'NEW',
          content: 'This is the full content preview for testing.',
        }),
      });
    });

    await page.route('/api/intel/metrics', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          agent_status: 'active',
          last_run: new Date().toISOString(),
          items_processed_today: 15,
          avg_response_time_ms: 2500,
          qdrant_health: 'healthy',
          next_scheduled_run: new Date(Date.now() + 7200000).toISOString(),
          uptime_percentage: 99.8,
        }),
      });
    });

    // Navigate to Intelligence Center
    await page.goto('/intelligence/visa-oracle');
  });

  test('Tab Navigation: All tabs lead to correct pages and highlight correctly', async ({ page }) => {
    // Test 1: Verify we're on Visa Oracle
    await expect(page).toHaveURL(/\/intelligence\/visa-oracle/);

    // Verify Visa Oracle tab is highlighted (active)
    const visaTab = page.getByRole('link', { name: /Visa Oracle/i });
    await expect(visaTab).toHaveClass(/bg-\[var\(--accent\)\]\/10/);

    // Test 2: Click News Room tab
    const newsTab = page.getByRole('link', { name: /News Room/i });
    await newsTab.click();
    await expect(page).toHaveURL(/\/intelligence\/news-room/);

    // Verify News Room tab is now highlighted
    await expect(newsTab).toHaveClass(/bg-\[var\(--accent\)\]\/10/);

    // Verify Visa Oracle tab is NOT highlighted
    await expect(visaTab).not.toHaveClass(/bg-\[var\(--accent\)\]\/10/);

    // Test 3: Click System Pulse tab
    const pulseTab = page.getByRole('link', { name: /System Pulse/i });
    await pulseTab.click();
    await expect(page).toHaveURL(/\/intelligence\/system-pulse/);

    // Verify System Pulse tab is now highlighted
    await expect(pulseTab).toHaveClass(/bg-\[var\(--accent\)\]\/10/);

    // Test 4: Navigate back to Visa Oracle
    await visaTab.click();
    await expect(page).toHaveURL(/\/intelligence\/visa-oracle/);
    await expect(visaTab).toHaveClass(/bg-\[var\(--accent\)\]\/10/);
  });

  test('Visa Oracle: Refresh button reloads data', async ({ page }) => {
    // Wait for initial load
    await expect(page.getByText('Test Visa Regulation')).toBeVisible();

    let requestCount = 0;
    await page.route('/api/intel/staging/pending*', async (route) => {
      requestCount++;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          items: [
            {
              id: `visa-refresh-${requestCount}`,
              type: 'visa',
              title: `Visa Item ${requestCount}`,
              status: 'pending',
              detected_at: new Date().toISOString(),
              source: 'https://test.com',
              detection_type: 'NEW',
            },
          ],
          count: 1,
        }),
      });
    });

    // Click Refresh button
    const refreshButton = page.getByRole('button', { name: /Refresh/i });
    await refreshButton.click();

    // Verify new data loaded
    await expect(page.getByText(/Visa Item 2/i)).toBeVisible({ timeout: 5000 });
  });

  test('Visa Oracle: View Content button opens preview, Hide Preview closes it', async ({ page }) => {
    // Wait for item to load
    await expect(page.getByText('Test Visa Regulation')).toBeVisible();

    // Test 1: Click "View Content" button
    const viewButton = page.getByRole('button', { name: /View Content/i }).first();
    await viewButton.click();

    // Verify preview opens
    await expect(page.getByText('Content Preview')).toBeVisible();
    await expect(page.getByText('This is the full content preview for testing.')).toBeVisible();

    // Test 2: Click "Hide Preview" button
    const hideButton = page.getByRole('button', { name: /Hide Preview/i });
    await hideButton.click();

    // Verify preview closes
    await expect(page.getByText('Content Preview')).not.toBeVisible();
  });

  test('Visa Oracle: Approve button shows confirmation, then removes item on confirm', async ({ page }) => {
    await expect(page.getByText('Test Visa Regulation')).toBeVisible();

    // Mock the approve endpoint
    await page.route('/api/intel/staging/approve/*/*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          message: 'Item approved and ingested',
          id: 'visa-test-1',
        }),
      });
    });

    // Setup confirmation dialog handler
    page.once('dialog', async (dialog) => {
      expect(dialog.message()).toContain('This will ingest the content into the Knowledge Base');
      await dialog.accept();
    });

    // Click Approve button
    const approveButton = page.getByRole('button', { name: /Approve & Ingest/i }).first();
    await approveButton.click();

    // Verify item is removed after approval
    await expect(page.getByText('Test Visa Regulation')).not.toBeVisible({ timeout: 5000 });

    // Verify empty state shows
    await expect(page.getByText('All Caught Up!')).toBeVisible();
  });

  test('Visa Oracle: Reject button shows confirmation, then removes item on confirm', async ({ page }) => {
    await expect(page.getByText('Test Visa Regulation')).toBeVisible();

    // Mock the reject endpoint
    await page.route('/api/intel/staging/reject/*/*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          message: 'Item rejected and archived',
          id: 'visa-test-1',
        }),
      });
    });

    // Setup confirmation dialog handler
    page.once('dialog', async (dialog) => {
      expect(dialog.message()).toContain('Are you sure you want to reject this update?');
      await dialog.accept();
    });

    // Click Reject button
    const rejectButton = page.getByRole('button', { name: /Reject/i }).first();
    await rejectButton.click();

    // Verify item is removed after rejection
    await expect(page.getByText('Test Visa Regulation')).not.toBeVisible({ timeout: 5000 });
  });

  test('Visa Oracle: Cancel on confirmation dialog keeps item', async ({ page }) => {
    await expect(page.getByText('Test Visa Regulation')).toBeVisible();

    // Setup confirmation dialog handler - CANCEL this time
    page.once('dialog', async (dialog) => {
      await dialog.dismiss();
    });

    // Click Approve button
    const approveButton = page.getByRole('button', { name: /Approve & Ingest/i }).first();
    await approveButton.click();

    // Verify item is STILL visible after cancelling
    await expect(page.getByText('Test Visa Regulation')).toBeVisible();
  });

  test('News Room: Sync Sources button reloads news items', async ({ page }) => {
    // Navigate to News Room
    await page.getByRole('link', { name: /News Room/i }).click();
    await expect(page).toHaveURL(/\/intelligence\/news-room/);

    // Wait for initial load
    await expect(page.getByText('Test News Article')).toBeVisible();

    let newsRequestCount = 0;
    await page.route('/api/intel/staging/pending*', async (route) => {
      const url = new URL(route.request().url());
      const type = url.searchParams.get('type');

      if (type === 'news') {
        newsRequestCount++;
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            items: [
              {
                id: `news-sync-${newsRequestCount}`,
                type: 'news',
                title: `News Article ${newsRequestCount}`,
                status: 'pending',
                detected_at: new Date().toISOString(),
                source: 'Test Source',
                detection_type: 'NEW',
              },
            ],
            count: 1,
          }),
        });
      }
    });

    // Click Sync Sources button
    const syncButton = page.getByRole('button', { name: /Sync Sources/i });
    await syncButton.click();

    // Verify new data loaded
    await expect(page.getByText(/News Article 2/i)).toBeVisible({ timeout: 5000 });
  });

  test('News Room: External source links open in new tab', async ({ page }) => {
    // Navigate to News Room
    await page.getByRole('link', { name: /News Room/i }).click();
    await expect(page.getByText('Test News Article')).toBeVisible();

    // Find external link (has target="_blank")
    const externalLinks = page.locator('a[target="_blank"]');
    await expect(externalLinks.first()).toHaveAttribute('target', '_blank');
    await expect(externalLinks.first()).toHaveAttribute('rel', 'noreferrer');
  });

  test('System Pulse: Refresh button reloads metrics', async ({ page }) => {
    // Navigate to System Pulse
    await page.getByRole('link', { name: /System Pulse/i }).click();
    await expect(page).toHaveURL(/\/intelligence\/system-pulse/);

    // Wait for metrics to load
    await expect(page.getByText('ACTIVE')).toBeVisible();
    await expect(page.getByText('99.8%')).toBeVisible();

    let metricsRequestCount = 0;
    await page.route('/api/intel/metrics', async (route) => {
      metricsRequestCount++;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          agent_status: 'active',
          last_run: new Date().toISOString(),
          items_processed_today: 15 + metricsRequestCount,
          avg_response_time_ms: 2500,
          qdrant_health: 'healthy',
          next_scheduled_run: new Date(Date.now() + 7200000).toISOString(),
          uptime_percentage: 99.8,
        }),
      });
    });

    // Click Refresh button
    const refreshButton = page.getByRole('button', { name: /Refresh/i });
    await refreshButton.click();

    // Verify updated metrics
    await expect(page.getByText('16')).toBeVisible({ timeout: 5000 });
  });

  test('System Pulse: Error state shows Retry button, retry reloads metrics', async ({ page }) => {
    // Navigate to System Pulse
    await page.getByRole('link', { name: /System Pulse/i }).click();

    // Mock metrics endpoint to fail first, then succeed
    let requestCount = 0;
    await page.route('/api/intel/metrics', async (route) => {
      requestCount++;
      if (requestCount === 1) {
        // First request fails
        await route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({ error: 'Internal Server Error' }),
        });
      } else {
        // Retry succeeds
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            agent_status: 'active',
            last_run: new Date().toISOString(),
            items_processed_today: 20,
            avg_response_time_ms: 2500,
            qdrant_health: 'healthy',
            next_scheduled_run: new Date(Date.now() + 7200000).toISOString(),
            uptime_percentage: 99.9,
          }),
        });
      }
    });

    // Verify error state shows
    await expect(page.getByText('Metrics Unavailable')).toBeVisible();

    // Verify Retry button is present
    const retryButton = page.getByRole('button', { name: /Retry/i });
    await expect(retryButton).toBeVisible();

    // Click Retry button
    await retryButton.click();

    // Verify metrics now load successfully
    await expect(page.getByText('ACTIVE')).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('99.9%')).toBeVisible();
  });

  test('All pages: Header always shows "Agent Active" indicator', async ({ page }) => {
    // Verify on Visa Oracle
    await expect(page.getByText('Agent Active')).toBeVisible();

    // Navigate to News Room
    await page.getByRole('link', { name: /News Room/i }).click();
    await expect(page.getByText('Agent Active')).toBeVisible();

    // Navigate to System Pulse
    await page.getByRole('link', { name: /System Pulse/i }).click();
    await expect(page.getByText('Agent Active')).toBeVisible();
  });

  test('Complete User Journey: Navigate through all tabs, interact with all buttons', async ({ page }) => {
    // Start at Visa Oracle
    await expect(page).toHaveURL(/\/intelligence\/visa-oracle/);
    await expect(page.getByText('Test Visa Regulation')).toBeVisible();

    // Test preview flow
    await page.getByRole('button', { name: /View Content/i }).first().click();
    await expect(page.getByText('Content Preview')).toBeVisible();
    await page.getByRole('button', { name: /Hide Preview/i }).click();
    await expect(page.getByText('Content Preview')).not.toBeVisible();

    // Navigate to News Room
    await page.getByRole('link', { name: /News Room/i }).click();
    await expect(page.getByText('Test News Article')).toBeVisible();
    await expect(page.getByText('CRITICAL')).toBeVisible();

    // Test Sync Sources button
    await page.getByRole('button', { name: /Sync Sources/i }).click();

    // Navigate to System Pulse
    await page.getByRole('link', { name: /System Pulse/i }).click();
    await expect(page.getByText('ACTIVE')).toBeVisible();
    await expect(page.getByText('Agent Configuration')).toBeVisible();

    // Test Refresh button
    await page.getByRole('button', { name: /Refresh/i }).click();

    // Navigate back to Visa Oracle
    await page.getByRole('link', { name: /Visa Oracle/i }).click();
    await expect(page.getByText('Test Visa Regulation')).toBeVisible();

    // Complete workflow test passed
  });
});
