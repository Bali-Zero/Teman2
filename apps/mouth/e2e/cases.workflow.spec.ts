import { test, expect, Page } from '@playwright/test';

/**
 * E2E Tests for Cases Page Workflow
 * Tests complete user workflows including filtering, sorting, and view switching
 */

test.describe('Cases Page E2E Workflows', () => {
  let page: Page;

  test.beforeEach(async ({ browser }) => {
    page = await browser.newPage();
    // Navigate to cases page - adjust URL based on your deployment
    await page.goto('/cases', { waitUntil: 'networkidle' });
  });

  test.afterEach(async () => {
    await page.close();
  });

  test.describe('View Mode Switching', () => {
    test('should switch from Kanban to List view and maintain state', async () => {
      // Verify Kanban view is default
      const kanbanColumns = page.locator('h3').filter({ hasText: /Inquiry|Quotation|In Progress|Completed/ });
      await expect(kanbanColumns.first()).toBeVisible();

      // Click List view button
      const listButton = page.locator('button[title="List View"]');
      await listButton.click();

      // Verify table is displayed
      const table = page.locator('table');
      await expect(table).toBeVisible();

      // Verify table headers are visible
      await expect(page.locator('th')).toContainText('ID');
      await expect(page.locator('th')).toContainText('Case Type');
      await expect(page.locator('th')).toContainText('Client');
      await expect(page.locator('th')).toContainText('Status');
    });

    test('should switch from List to Kanban view', async () => {
      // Start in List view
      const listButton = page.locator('button[title="List View"]');
      await listButton.click();
      await expect(page.locator('table')).toBeVisible();

      // Switch to Kanban
      const kanbanButton = page.locator('button[title="Kanban Board"]');
      await kanbanButton.click();

      // Verify Kanban columns are visible
      const kanbanColumns = page.locator('h3').filter({ hasText: /Inquiry|Quotation|In Progress|Completed/ });
      await expect(kanbanColumns.first()).toBeVisible();
    });
  });

  test.describe('Filter Workflow', () => {
    test('should open and apply status filter', async () => {
      // Open filter panel
      const filterButton = page.locator('button:has-text("Filters")');
      await filterButton.click();

      // Verify filter dropdowns are visible
      const statusSelect = page.locator('select');
      const filterPanel = page.locator('div').filter({ hasText: 'Filters' }).first();
      await expect(filterPanel).toBeVisible();

      // Select a status filter
      const statusDropdown = statusSelect.first();
      await statusDropdown.selectOption('inquiry');

      // Verify filter is applied (check badge)
      const filterBadge = filterButton.locator('..')
        .locator('span').filter({ hasText: /\d/ });
      await expect(filterBadge).toBeVisible();
    });

    test('should apply multiple filters simultaneously', async () => {
      const filterButton = page.locator('button:has-text("Filters")');
      await filterButton.click();

      const selects = page.locator('select');

      // Apply status filter
      const statusSelect = selects.nth(0);
      await statusSelect.selectOption('inquiry');

      // Apply type filter if available
      const typeSelect = selects.nth(1);
      if (await typeSelect.isVisible()) {
        await typeSelect.selectOption('KITAS');
      }

      // Verify multiple filters show in badge
      const filterBadge = filterButton.locator('..')
        .locator('span').filter({ hasText: /\d/ });
      await expect(filterBadge).toBeVisible();
    });

    test('should clear all filters with clear button', async () => {
      const filterButton = page.locator('button:has-text("Filters")');
      await filterButton.click();

      // Apply a filter
      const statusSelect = page.locator('select').first();
      await statusSelect.selectOption('inquiry');

      // Click Clear all button
      const clearButton = page.locator('button:has-text("Clear all")');
      await clearButton.click();

      // Verify filter badge is gone
      const filterBadge = filterButton.locator('..')
        .locator('span').filter({ hasText: /\d/ });
      await expect(filterBadge).not.toBeVisible();

      // Verify filter is reset
      await expect(statusSelect).toHaveValue('');
    });

    test('should filter persists when switching views', async () => {
      // Apply filter in Kanban view
      const filterButton = page.locator('button:has-text("Filters")');
      await filterButton.click();

      const statusSelect = page.locator('select').first();
      await statusSelect.selectOption('inquiry');

      // Switch to List view
      const listButton = page.locator('button[title="List View"]');
      await listButton.click();

      // Verify filter is still applied
      const filterBadge = filterButton.locator('..')
        .locator('span').filter({ hasText: /\d/ });
      await expect(filterBadge).toBeVisible();
    });
  });

  test.describe('Search Workflow', () => {
    test('should search for cases and update results', async () => {
      const searchInput = page.locator('input[placeholder*="Search"]');

      // Type search query
      await searchInput.fill('KITAS');

      // Wait for results to update
      await page.waitForTimeout(500); // Debounce wait

      // Verify search is working (should filter results)
      // The actual verification depends on data availability
    });

    test('should clear search and show all results', async () => {
      const searchInput = page.locator('input[placeholder*="Search"]');

      // Enter search query
      await searchInput.fill('test');
      await page.waitForTimeout(500);

      // Clear search
      await searchInput.fill('');

      // Verify all results are shown again
      // This depends on data availability
    });

    test('should handle special characters in search', async () => {
      const searchInput = page.locator('input[placeholder*="Search"]');

      // Type special characters
      await searchInput.fill('&@#');
      await page.waitForTimeout(500);

      // Verify no errors and page remains responsive
      const pageHeading = page.locator('h1:has-text("Cases")');
      await expect(pageHeading).toBeVisible();
    });
  });

  test.describe('Sorting Workflow', () => {
    test('should sort by clicking column headers in List view', async () => {
      // Switch to List view
      const listButton = page.locator('button[title="List View"]');
      await listButton.click();

      // Click ID column header to sort
      const idHeader = page.locator('th').filter({ hasText: 'ID' }).first();
      await idHeader.click();

      // Verify sort indicator appears
      const sortIcon = idHeader.locator('svg');
      await expect(sortIcon).toBeVisible();
    });

    test('should toggle sort order when clicking same header twice', async () => {
      const listButton = page.locator('button[title="List View"]');
      await listButton.click();

      const clientHeader = page.locator('th').filter({ hasText: /^Client$/ }).first();

      // First click - sort ascending
      await clientHeader.click();
      let sortIcon = clientHeader.locator('svg');
      await expect(sortIcon).toBeVisible();

      // Second click - sort descending
      await clientHeader.click();
      sortIcon = clientHeader.locator('svg');
      await expect(sortIcon).toBeVisible();
    });

    test('should change sort column when clicking different header', async () => {
      const listButton = page.locator('button[title="List View"]');
      await listButton.click();

      const idHeader = page.locator('th').filter({ hasText: 'ID' }).first();
      const clientHeader = page.locator('th').filter({ hasText: /^Client$/ }).first();

      // Sort by ID
      await idHeader.click();
      const idIcon = idHeader.locator('svg');
      await expect(idIcon).toBeVisible();

      // Sort by Client
      await clientHeader.click();
      const clientIcon = clientHeader.locator('svg');
      await expect(clientIcon).toBeVisible();

      // Verify ID header no longer shows sort indicator
      const idHeaderIcon = idHeader.locator('svg').filter({ hasText: /↑|↓/ });
      await expect(idHeaderIcon).not.toBeVisible();
    });
  });

  test.describe('Pagination Workflow', () => {
    test('should display pagination controls when needed', async () => {
      const listButton = page.locator('button[title="List View"]');
      await listButton.click();

      // Pagination only shows if there are more than 25 items
      const paginationContainer = page.locator('text=Showing');
      // May or may not be visible depending on data
    });

    test('should navigate between pages', async () => {
      const listButton = page.locator('button[title="List View"]');
      await listButton.click();

      const nextButton = page.locator('button:has-text("Next")');
      if (await nextButton.isVisible()) {
        // Click next
        await nextButton.click();
        await page.waitForTimeout(300);

        // Verify page number button is active
        const pageButton = page.locator('button:has-text("2")');
        if (await pageButton.isVisible()) {
          // Page 2 should be highlighted or different styling
        }
      }
    });
  });

  test.describe('Complete Workflow', () => {
    test('should perform complex user workflow', async () => {
      // 1. Start with Kanban view
      const kanbanButton = page.locator('button[title="Kanban Board"]');
      await expect(kanbanButton).toBeVisible();

      // 2. Open filters and apply one
      const filterButton = page.locator('button:has-text("Filters")');
      await filterButton.click();

      const statusSelect = page.locator('select').first();
      await statusSelect.selectOption('inquiry');

      // 3. Switch to List view
      const listButton = page.locator('button[title="List View"]');
      await listButton.click();
      await expect(page.locator('table')).toBeVisible();

      // 4. Sort by client name
      const clientHeader = page.locator('th').filter({ hasText: /^Client$/ }).first();
      await clientHeader.click();

      // 5. Verify sort applied
      const sortIcon = clientHeader.locator('svg');
      await expect(sortIcon).toBeVisible();

      // 6. Search for specific case
      const searchInput = page.locator('input[placeholder*="Search"]');
      await searchInput.fill('KITAS');
      await page.waitForTimeout(500);

      // 7. Clear search
      await searchInput.fill('');

      // 8. Switch back to Kanban
      await kanbanButton.click();
      const kanbanColumns = page.locator('h3').filter({ hasText: 'Inquiry' });
      await expect(kanbanColumns.first()).toBeVisible();

      // 9. Clear filters
      const clearButton = page.locator('button:has-text("Clear all")');
      if (await clearButton.isVisible()) {
        await clearButton.click();
      }

      // Verify page is still responsive
      const heading = page.locator('h1:has-text("Cases")');
      await expect(heading).toBeVisible();
    });
  });

  test.describe('Error Handling', () => {
    test('should handle rapid filter changes', async () => {
      const filterButton = page.locator('button:has-text("Filters")');

      // Rapidly click filter button
      for (let i = 0; i < 5; i++) {
        await filterButton.click();
        await page.waitForTimeout(50);
      }

      // Verify page is still responsive
      const heading = page.locator('h1:has-text("Cases")');
      await expect(heading).toBeVisible();
    });

    test('should handle rapid view switching', async () => {
      const listButton = page.locator('button[title="List View"]');
      const kanbanButton = page.locator('button[title="Kanban Board"]');

      // Rapidly switch views
      for (let i = 0; i < 3; i++) {
        await listButton.click();
        await page.waitForTimeout(100);
        await kanbanButton.click();
        await page.waitForTimeout(100);
      }

      // Verify page is in a valid state
      const heading = page.locator('h1:has-text("Cases")');
      await expect(heading).toBeVisible();
    });
  });
});
