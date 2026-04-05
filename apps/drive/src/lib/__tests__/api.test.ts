import { describe, it, expect, vi, beforeEach } from 'vitest';
import { driveApi } from '../api';

// Mock logger
vi.mock('@/lib/logger', () => ({
  logger: {
    error: vi.fn(),
    info: vi.fn(),
    debug: vi.fn(),
    warn: vi.fn(),
  },
}));

describe('driveApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (global.fetch as ReturnType<typeof vi.fn>).mockReset();
  });

  describe('getStatus', () => {
    it('returns connected status when API reports connected', async () => {
      (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            status: 'connected',
            files_accessible: true,
            root_folder_id: 'root-123',
          }),
      });

      const status = await driveApi.getStatus();
      expect(status.connected).toBe(true);
      expect(status.configured).toBe(true);
      expect(status.root_folder_id).toBe('root-123');
    });

    it('returns disconnected status when API reports disconnected', async () => {
      (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            status: 'disconnected',
            files_accessible: false,
          }),
      });

      const status = await driveApi.getStatus();
      expect(status.connected).toBe(false);
    });
  });

  describe('listFiles', () => {
    it('fetches files and transforms response', async () => {
      const mockResponse = {
        files: [
          {
            id: 'file-1',
            name: 'test.pdf',
            type: 'file',
            mimeType: 'application/pdf',
            size: 1024,
            modifiedTime: '2024-01-01T00:00:00Z',
          },
          {
            id: 'folder-1',
            name: 'Docs',
            type: 'folder',
            mimeType: 'application/vnd.google-apps.folder',
            size: 0,
          },
        ],
        next_page_token: null,
      };

      (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      const result = await driveApi.listFiles();
      expect(result.files).toHaveLength(2);
      expect(result.files[0].name).toBe('test.pdf');
      expect(result.files[0].is_folder).toBe(false);
      expect(result.files[1].is_folder).toBe(true);
      expect(result.next_page_token).toBeNull();
    });

    it('includes folder_id and page_size in query params', async () => {
      (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ files: [], next_page_token: null }),
      });

      await driveApi.listFiles({
        folder_id: 'abc123',
        page_size: 25,
      });

      const callUrl = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
      expect(callUrl).toContain('folder_id=abc123');
      expect(callUrl).toContain('page_size=25');
    });
  });

  describe('searchFiles', () => {
    it('searches and transforms results', async () => {
      (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            results: [
              {
                id: 'file-1',
                name: 'match.pdf',
                type: 'file',
                mimeType: 'application/pdf',
                size: 2048,
              },
            ],
          }),
      });

      const results = await driveApi.searchFiles('match');
      expect(results).toHaveLength(1);
      expect(results[0].name).toBe('match.pdf');
      expect(results[0].is_folder).toBe(false);
    });
  });

  describe('getDownloadUrl', () => {
    it('returns correct download URL', () => {
      const url = driveApi.getDownloadUrl('file-123');
      expect(url).toContain('/api/drive/files/file-123/download');
    });
  });

  describe('createFolder', () => {
    it('sends POST request with correct payload', async () => {
      (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ success: true }),
      });

      await driveApi.createFolder({ name: 'New Folder', parent_id: 'root' });

      const [url, options] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
      expect(url).toContain('/api/drive/folders');
      expect(options.method).toBe('POST');
      expect(JSON.parse(options.body)).toEqual({
        name: 'New Folder',
        parent_id: 'root',
      });
    });
  });

  describe('deleteFile', () => {
    it('sends DELETE request for the file', async () => {
      (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ success: true }),
      });

      await driveApi.deleteFile('file-to-delete');

      const [url, options] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
      expect(url).toContain('/api/drive/files/file-to-delete');
      expect(options.method).toBe('DELETE');
    });
  });

  describe('renameFile', () => {
    it('sends PATCH request with new name', async () => {
      (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ success: true }),
      });

      await driveApi.renameFile('file-1', 'new-name.pdf');

      const [url, options] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
      expect(url).toContain('/api/drive/files/file-1/rename');
      expect(options.method).toBe('PATCH');
      expect(JSON.parse(options.body)).toEqual({ new_name: 'new-name.pdf' });
    });
  });

  describe('moveFiles', () => {
    it('moves files to new parent', async () => {
      (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({}),
      });

      const result = await driveApi.moveFiles(['file-1', 'file-2'], 'target-folder');
      expect(result.success).toBe(true);
      expect(result.failed).toHaveLength(0);
    });

    it('reports failed moves', async () => {
      (global.fetch as ReturnType<typeof vi.fn>)
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({}),
        })
        .mockRejectedValueOnce(new Error('Move failed'));

      const result = await driveApi.moveFiles(['file-1', 'file-2'], 'target-folder');
      expect(result.success).toBe(false);
      expect(result.failed).toContain('file-2');
    });
  });

  describe('disconnect', () => {
    it('returns success', async () => {
      const result = await driveApi.disconnect();
      expect(result.success).toBe(true);
    });
  });
});
