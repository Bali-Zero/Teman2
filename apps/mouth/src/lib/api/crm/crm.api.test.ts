import { describe, it, expect, beforeEach, vi } from "vitest";
import { CrmApi } from "./crm.api";
import { ApiClientBase } from "../client";
import type { Practice, Interaction, RenewalAlert } from "./crm.types";

describe("CrmApi", () => {
  let crmApi: CrmApi;
  let mockClient: { request: ReturnType<typeof vi.fn> };

  beforeEach(() => {
    mockClient = {
      request: vi.fn(),
    } as any;
    crmApi = new CrmApi(mockClient as unknown as ApiClientBase);
  });

  describe("getUpcomingRenewals", () => {
    it("should fetch upcoming renewals with default 90 days", async () => {
      const mockRenewals: RenewalAlert[] = [
        {
          id: 1,
          practice_id: 1,
          client_id: 1,
          alert_type: "renewal_due",
          description: "Practice renewal due soon",
          target_date: "2025-01-15",
          alert_date: "2025-01-01",
          status: "pending",
        },
      ];

      mockClient.request.mockResolvedValue(mockRenewals);

      const result = await crmApi.getUpcomingRenewals();

      expect(mockClient.request).toHaveBeenCalledWith(
        "/api/crm/practices/renewals/upcoming?days=90",
      );
      expect(result).toEqual(mockRenewals);
    });

    it("should fetch upcoming renewals with custom days", async () => {
      const mockRenewals: RenewalAlert[] = [];
      mockClient.request.mockResolvedValue(mockRenewals);

      await crmApi.getUpcomingRenewals(30);

      expect(mockClient.request).toHaveBeenCalledWith(
        "/api/crm/practices/renewals/upcoming?days=30",
      );
    });
  });

  describe("getRevenueGrowth", () => {
    it("should fetch revenue growth data", async () => {
      const mockGrowth = {
        current_month: {
          total_revenue: 50000000,
          paid_revenue: 30000000,
          outstanding_revenue: 20000000,
        },
        previous_month: {
          total_revenue: 40000000,
          paid_revenue: 25000000,
          outstanding_revenue: 15000000,
        },
        growth_percentage: 25.0,
        monthly_breakdown: [],
      };

      (mockClient.request as ReturnType<typeof vi.fn>).mockResolvedValue(
        mockGrowth,
      );

      const result = await crmApi.getRevenueGrowth();

      expect(mockClient.request).toHaveBeenCalledWith(
        "/api/crm/practices/stats/revenue-growth",
      );
      expect(result).toEqual(mockGrowth);
      expect(result.growth_percentage).toBe(25.0);
    });
  });

  describe("markInteractionRead", () => {
    it("should mark interaction as read", async () => {
      const mockResponse = {
        success: true,
        interaction_id: 1,
        read_receipt: true,
        read_at: "2025-01-01T10:00:00Z",
        read_by: "zero@balizero.com",
      };

      (mockClient.request as ReturnType<typeof vi.fn>).mockResolvedValue(
        mockResponse,
      );

      const result = await crmApi.markInteractionRead(1, "zero@balizero.com");

      expect(mockClient.request).toHaveBeenCalledWith(
        "/api/crm/interactions/1/mark-read?read_by=zero%40balizero.com",
        { method: "PATCH" },
      );
      expect(result.success).toBe(true);
      expect(result.read_receipt).toBe(true);
    });
  });

  describe("markInteractionsReadBatch", () => {
    it("should mark multiple interactions as read", async () => {
      const mockResponse = {
        success: true,
        updated_count: 3,
        read_by: "zero@balizero.com",
      };

      (mockClient.request as ReturnType<typeof vi.fn>).mockResolvedValue(
        mockResponse,
      );

      const result = await crmApi.markInteractionsReadBatch(
        [1, 2, 3],
        "zero@balizero.com",
      );

      expect(mockClient.request).toHaveBeenCalledWith(
        expect.stringContaining("/api/crm/interactions/mark-read-batch"),
        { method: "PATCH" },
      );
      expect(result.success).toBe(true);
      expect(result.updated_count).toBe(3);
    });
  });

  describe("Client CRUD Operations", () => {
    describe("getClients", () => {
      it("should fetch all clients without filters", async () => {
        const mockClients = [
          { id: 1, full_name: "John Doe", email: "john@example.com" },
          { id: 2, full_name: "Jane Smith", email: "jane@example.com" },
        ];

        mockClient.request.mockResolvedValue(mockClients);

        const result = await crmApi.getClients();

        expect(mockClient.request).toHaveBeenCalledWith(
          "/api/crm/clients",
          undefined,
          30000,
        );
        expect(result).toEqual(mockClients);
      });

      it("should fetch clients with search filter", async () => {
        const mockClients = [
          { id: 1, full_name: "John Doe", email: "john@example.com" },
        ];

        mockClient.request.mockResolvedValue(mockClients);

        await crmApi.getClients({ search: "John", limit: 10 });

        expect(mockClient.request).toHaveBeenCalledWith(
          "/api/crm/clients?search=John&limit=10",
          undefined,
          30000,
        );
      });
    });

    describe("createClient", () => {
      it("should create a new client", async () => {
        const newClient = {
          full_name: "New Client",
          email: "new@example.com",
          phone: "+1234567890",
          nationality: "US",
        };

        const mockResponse = {
          id: 123,
          ...newClient,
          created_at: "2026-02-04T10:00:00Z",
        };

        mockClient.request.mockResolvedValue(mockResponse);

        const result = await crmApi.createClient(
          newClient,
          "admin@balizero.com",
        );

        expect(mockClient.request).toHaveBeenCalledWith(
          expect.stringContaining(
            "/api/crm/clients?created_by=admin%40balizero.com",
          ),
          expect.objectContaining({
            method: "POST",
            body: JSON.stringify(newClient),
          }),
          60000,
        );
        expect(result.id).toBe(123);
      });
    });

    describe("updateClient", () => {
      it("should update client information", async () => {
        const updates = {
          full_name: "Updated Name",
          phone: "+9876543210",
        };

        const mockResponse = {
          id: 1,
          full_name: "Updated Name",
          email: "client@example.com",
          phone: "+9876543210",
        };

        mockClient.request.mockResolvedValue(mockResponse);

        const result = await crmApi.updateClient(
          1,
          updates,
          "admin@balizero.com",
        );

        expect(mockClient.request).toHaveBeenCalledWith(
          expect.stringContaining(
            "/api/crm/clients/1?updated_by=admin%40balizero.com",
          ),
          expect.objectContaining({
            method: "PATCH",
            body: JSON.stringify(updates),
          }),
        );
        expect(result.full_name).toBe("Updated Name");
      });
    });

    describe("deleteClient", () => {
      it("should soft delete a client", async () => {
        const mockResponse = {
          success: true,
          message: "Client deleted successfully",
        };

        mockClient.request.mockResolvedValue(mockResponse);

        const result = await crmApi.deleteClient(1, "admin@balizero.com");

        expect(mockClient.request).toHaveBeenCalledWith(
          expect.stringContaining(
            "/api/crm/clients/1?deleted_by=admin%40balizero.com",
          ),
          { method: "DELETE" },
        );
        expect(result.success).toBe(true);
      });
    });

    describe("getClientByEmail", () => {
      it("should fetch client by email", async () => {
        const mockClient = {
          id: 1,
          email: "test@example.com",
          full_name: "Test User",
        };

        (crmApi as any).client.request.mockResolvedValue(mockClient);

        const result = await crmApi.getClientByEmail("test@example.com");

        expect(result).toEqual(mockClient);
      });

      it("should return null when client not found", async () => {
        const error = new Error("404 Not Found");
        (crmApi as any).client.request.mockRejectedValue(error);

        const result = await crmApi.getClientByEmail("notfound@example.com");

        expect(result).toBeNull();
      });

      it("should throw error for non-404 errors", async () => {
        const error = new Error("500 Server Error");
        (crmApi as any).client.request.mockRejectedValue(error);

        await expect(
          crmApi.getClientByEmail("error@example.com"),
        ).rejects.toThrow("500 Server Error");
      });
    });
  });

  describe("Practice CRUD Operations", () => {
    describe("getPractices", () => {
      it("should fetch practices with filters", async () => {
        const mockPractices = [
          { id: 1, practice_type: "KITAS", status: "active" },
          { id: 2, practice_type: "PMA", status: "pending" },
        ];

        mockClient.request.mockResolvedValue(mockPractices);

        await crmApi.getPractices({ status: "active", limit: 10 });

        expect(mockClient.request).toHaveBeenCalledWith(
          "/api/crm/practices?status=active&limit=10",
        );
      });
    });

    describe("createPractice", () => {
      it("should create a new practice", async () => {
        const newPractice = {
          client_id: 1,
          practice_type_code: "KITAS",
          status: "pending",
          quoted_price: 5000000,
        };

        const mockResponse = {
          id: 456,
          ...newPractice,
          created_at: "2026-02-04T10:00:00Z",
        };

        mockClient.request.mockResolvedValue(mockResponse);

        const result = await crmApi.createPractice(newPractice);

        expect(mockClient.request).toHaveBeenCalledWith(
          "/api/crm/practices/",
          expect.objectContaining({
            method: "POST",
            body: JSON.stringify(newPractice),
          }),
          60000,
        );
        expect(result.id).toBe(456);
      });
    });

    describe("updatePractice", () => {
      it("should update practice status and payment", async () => {
        const updates = {
          status: "completed",
          payment_status: "paid",
          actual_price: 4500000,
        };

        const mockResponse = {
          id: 1,
          ...updates,
        };

        mockClient.request.mockResolvedValue(mockResponse);

        const result = await crmApi.updatePractice(1, updates);

        expect(mockClient.request).toHaveBeenCalledWith(
          "/api/crm/practices/1/",
          expect.objectContaining({
            method: "PATCH",
            body: JSON.stringify(updates),
          }),
          60000,
        );
        expect(result.status).toBe("completed");
      });
    });

    describe("deletePractice", () => {
      it("should soft delete a practice", async () => {
        const mockResponse = {
          success: true,
          message: "Practice cancelled successfully",
        };

        mockClient.request.mockResolvedValue(mockResponse);

        const result = await crmApi.deletePractice(1, "admin@balizero.com");

        expect(mockClient.request).toHaveBeenCalledWith(
          expect.stringContaining(
            "/api/crm/practices/1?deleted_by=admin%40balizero.com",
          ),
          { method: "DELETE" },
        );
        expect(result.success).toBe(true);
      });
    });

    describe("getPractice", () => {
      it("should fetch single practice by ID", async () => {
        const mockPractice = {
          id: 1,
          practice_type: "KITAS",
          status: "active",
          client: { id: 1, full_name: "John Doe" },
        };

        mockClient.request.mockResolvedValue(mockPractice);

        const result = await crmApi.getPractice(1);

        expect(mockClient.request).toHaveBeenCalledWith("/api/crm/practices/1");
        expect(result).toEqual(mockPractice);
      });
    });
  });

  describe("Interaction Operations", () => {
    describe("createInteraction", () => {
      it("should create a new interaction", async () => {
        const newInteraction = {
          client_id: 1,
          interaction_type: "note" as const,
          summary: "Client called about visa status",
          team_member: "admin@balizero.com",
        };

        const mockResponse = {
          id: 789,
          ...newInteraction,
          direction: "outbound",
          channel: "in_person",
          created_at: "2026-02-04T10:00:00Z",
        };

        mockClient.request.mockResolvedValue(mockResponse);

        const result = await crmApi.createInteraction(newInteraction);

        expect(mockClient.request).toHaveBeenCalledWith(
          "/api/crm/interactions/",
          expect.objectContaining({
            method: "POST",
            body: expect.stringContaining("Client called about visa status"),
          }),
        );
        expect(result.id).toBe(789);
      });
    });

    describe("deleteInteraction", () => {
      it("should delete an interaction", async () => {
        const mockResponse = { success: true };

        mockClient.request.mockResolvedValue(mockResponse);

        const result = await crmApi.deleteInteraction(1, "admin@balizero.com");

        expect(mockClient.request).toHaveBeenCalledWith(
          expect.stringContaining(
            "/api/crm/interactions/1?deleted_by=admin%40balizero.com",
          ),
          { method: "DELETE" },
        );
        expect(result.success).toBe(true);
      });
    });

    describe("getClientTimeline", () => {
      it("should fetch client interaction timeline", async () => {
        const mockTimeline = [
          { id: 1, interaction_type: "call", summary: "Initial consultation" },
          { id: 2, interaction_type: "email", summary: "Document request" },
        ];

        mockClient.request.mockResolvedValue({ timeline: mockTimeline });

        const result = await crmApi.getClientTimeline(1, 20);

        expect(mockClient.request).toHaveBeenCalledWith(
          "/api/crm/interactions/client/1/timeline?limit=20",
          undefined,
          10000,
        );
        expect(result).toEqual(mockTimeline);
      });

      it("should handle empty timeline", async () => {
        mockClient.request.mockResolvedValue({ timeline: [] });

        const result = await crmApi.getClientTimeline(1);

        expect(result).toEqual([]);
      });
    });
  });

  describe("Document Management", () => {
    describe("getClientDocuments", () => {
      it("should fetch client documents", async () => {
        const mockDocs = [
          { id: 1, category: "passport", file_name: "passport.pdf" },
          { id: 2, category: "visa", file_name: "visa.pdf" },
        ];

        mockClient.request.mockResolvedValue(mockDocs);

        const result = await crmApi.getClientDocuments(1);

        expect(mockClient.request).toHaveBeenCalledWith(
          "/api/crm/clients/1/documents",
        );
        expect(result).toEqual(mockDocs);
      });

      it("should filter documents by category", async () => {
        mockClient.request.mockResolvedValue([]);

        await crmApi.getClientDocuments(1, "passport", true);

        expect(mockClient.request).toHaveBeenCalledWith(
          "/api/crm/clients/1/documents?category=passport&include_archived=true",
        );
      });
    });

    describe("createDocument", () => {
      it("should create a new document", async () => {
        const newDoc = {
          document_type: "passport",
          file_name: "passport.pdf",
          file_url: "https://example.com/passport.pdf",
        };

        const mockResponse = { id: 123, success: true };

        mockClient.request.mockResolvedValue(mockResponse);

        const result = await crmApi.createDocument(1, newDoc);

        expect(mockClient.request).toHaveBeenCalledWith(
          "/api/crm/clients/1/documents",
          expect.objectContaining({
            method: "POST",
            body: JSON.stringify(newDoc),
          }),
        );
        expect(result.id).toBe(123);
      });
    });

    describe("updateDocument", () => {
      it("should update document status", async () => {
        const updates = { status: "verified", is_archived: false };

        mockClient.request.mockResolvedValue({ success: true });

        await crmApi.updateDocument(1, 10, updates);

        expect(mockClient.request).toHaveBeenCalledWith(
          "/api/crm/clients/1/documents/10",
          expect.objectContaining({
            method: "PATCH",
            body: JSON.stringify(updates),
          }),
        );
      });
    });

    describe("deleteDocument", () => {
      it("should archive document by default", async () => {
        mockClient.request.mockResolvedValue({
          success: true,
          action: "archived",
        });

        const result = await crmApi.deleteDocument(1, 10);

        expect(mockClient.request).toHaveBeenCalledWith(
          "/api/crm/clients/1/documents/10",
          {
            method: "DELETE",
          },
        );
        expect(result.action).toBe("archived");
      });

      it("should permanently delete when specified", async () => {
        mockClient.request.mockResolvedValue({
          success: true,
          action: "deleted",
        });

        await crmApi.deleteDocument(1, 10, true);

        expect(mockClient.request).toHaveBeenCalledWith(
          "/api/crm/clients/1/documents/10?permanent=true",
          { method: "DELETE" },
        );
      });
    });
  });

  describe("Statistics and Analytics", () => {
    describe("getPracticeStats", () => {
      it("should fetch practice statistics", async () => {
        const mockStats = {
          total_practices: 100,
          active_practices: 50,
          by_status: { completed: 30, pending: 20 },
          by_type: [],
          revenue: {
            total_revenue: 0,
            paid_revenue: 0,
            outstanding_revenue: 0,
          },
        };

        mockClient.request.mockResolvedValue(mockStats);

        const result = await crmApi.getPracticeStats();

        expect(mockClient.request).toHaveBeenCalledWith(
          "/api/crm/practices/stats/overview",
        );
        expect(result.total_practices).toBe(100);
      });
    });

    describe("getInteractionStats", () => {
      it("should fetch interaction statistics", async () => {
        const mockStats = {
          total_interactions: 500,
          last_7_days: 100,
          by_type: { call: 200, email: 150, whatsapp: 150 },
          by_sentiment: {},
          by_team_member: [],
        };

        mockClient.request.mockResolvedValue(mockStats);

        const result = await crmApi.getInteractionStats();

        expect(mockClient.request).toHaveBeenCalledWith(
          "/api/crm/interactions/stats/overview",
        );
        expect(result.total_interactions).toBe(500);
      });
    });

    describe("getClientSummary", () => {
      it("should fetch complete client summary", async () => {
        const mockSummary = {
          client: { id: 1, full_name: "John Doe" },
          practices: [{ id: 1, practice_type: "KITAS" }],
          interactions_count: 10,
          total_revenue: 15000000,
        };

        mockClient.request.mockResolvedValue(mockSummary);

        const result = await crmApi.getClientSummary(1);

        expect(mockClient.request).toHaveBeenCalledWith(
          "/api/crm/clients/1/summary",
          undefined,
          10000,
        );
        expect(result.client.id).toBe(1);
      });
    });
  });

  describe("Google Drive Operations", () => {
    describe("createDriveFolder", () => {
      it("should create standardized Google Drive folder structure", async () => {
        const mockResponse = {
          success: true,
          root_folder_id: "folder-123",
          root_folder_url: "https://drive.google.com/drive/folders/folder-123",
          root_folder_name: "Client - John Doe",
          folders: {
            immigration: { id: "imm-123", url: "https://drive.google.com/..." },
            pma: { id: "pma-123", url: "https://drive.google.com/..." },
          },
          created_count: 5,
        };

        mockClient.request.mockResolvedValue(mockResponse);

        const result = await crmApi.createDriveFolder(1);

        expect(mockClient.request).toHaveBeenCalledWith(
          "/api/clients/1/create-drive-folder",
          {
            method: "POST",
          },
        );
        expect(result.success).toBe(true);
        expect(result.root_folder_id).toBe("folder-123");
        expect(result.created_count).toBe(5);
      });
    });

    describe("getDriveFolder", () => {
      it("should get Google Drive folder information", async () => {
        const mockResponse = {
          client_id: 1,
          folder_id: "folder-123",
          folder_url: "https://drive.google.com/drive/folders/folder-123",
          exists: true,
        };

        mockClient.request.mockResolvedValue(mockResponse);

        const result = await crmApi.getDriveFolder(1);

        expect(mockClient.request).toHaveBeenCalledWith(
          "/api/clients/1/drive-folder",
        );
        expect(result.exists).toBe(true);
        expect(result.folder_id).toBe("folder-123");
      });

      it("should handle non-existent folder", async () => {
        const mockResponse = {
          client_id: 1,
          folder_id: null,
          folder_url: null,
          exists: false,
          message: "No folder linked",
        };

        mockClient.request.mockResolvedValue(mockResponse);

        const result = await crmApi.getDriveFolder(1);

        expect(result.exists).toBe(false);
        expect(result.folder_id).toBeNull();
      });
    });

    describe("unlinkDriveFolder", () => {
      it("should unlink Google Drive folder from client", async () => {
        const mockResponse = {
          success: true,
          message: "Folder unlinked successfully",
          note: "Folder not deleted from Google Drive",
        };

        mockClient.request.mockResolvedValue(mockResponse);

        const result = await crmApi.unlinkDriveFolder(1);

        expect(mockClient.request).toHaveBeenCalledWith(
          "/api/clients/1/drive-folder",
          {
            method: "DELETE",
          },
        );
        expect(result.success).toBe(true);
      });
    });

    describe("getDriveFolderStructure", () => {
      it("should get complete folder structure with file counts", async () => {
        const mockResponse = {
          root_folder_id: "folder-123",
          folders: [
            {
              name: "Immigration",
              id: "imm-123",
              file_count: 5,
              total_size_bytes: 1024000,
              last_modified: "2026-02-04T10:00:00Z",
            },
          ],
          total_files: 5,
          total_size_bytes: 1024000,
        };

        mockClient.request.mockResolvedValue(mockResponse);

        const result = await crmApi.getDriveFolderStructure(1);

        expect(mockClient.request).toHaveBeenCalledWith(
          "/api/clients/1/drive-folder/structure",
        );
        expect(result.total_files).toBe(5);
        expect(result.folders).toHaveLength(1);
      });
    });

    describe("listFolderFiles", () => {
      it("should list files in a subfolder", async () => {
        const mockResponse = {
          folder_name: "Immigration",
          folder_id: "imm-123",
          files: [
            {
              id: "file-1",
              name: "passport.pdf",
              mime_type: "application/pdf",
              size_bytes: 102400,
              created_time: "2026-02-04T10:00:00Z",
              modified_time: "2026-02-04T10:00:00Z",
              thumbnail_url: null,
              download_url: "https://drive.google.com/...",
              is_folder: false,
            },
          ],
          total: 1,
          limit: 50,
          offset: 0,
          has_more: false,
        };

        mockClient.request.mockResolvedValue(mockResponse);

        const result = await crmApi.listFolderFiles(1, "Immigration");

        expect(mockClient.request).toHaveBeenCalledWith(
          "/api/clients/1/drive-folder/Immigration/files",
        );
        expect(result.files).toHaveLength(1);
      });

      it("should list files with search and pagination", async () => {
        mockClient.request.mockResolvedValue({
          folder_name: "Immigration",
          folder_id: "imm-123",
          files: [],
          total: 0,
          limit: 10,
          offset: 5,
          has_more: false,
        });

        await crmApi.listFolderFiles(1, "Immigration", {
          limit: 10,
          offset: 5,
          search: "passport",
        });

        expect(mockClient.request).toHaveBeenCalledWith(
          "/api/clients/1/drive-folder/Immigration/files?limit=10&offset=5&search=passport",
        );
      });
    });

    describe("uploadFileToFolder", () => {
      it("should upload file to a subfolder", async () => {
        const mockFile = new File(["content"], "test.pdf", {
          type: "application/pdf",
        });
        const mockResponse = {
          success: true,
          folder_name: "Immigration",
          folder_id: "imm-123",
          file_id: "file-123",
          file_name: "test.pdf",
          size_bytes: 102400,
          download_url: "https://drive.google.com/...",
        };

        mockClient.request.mockResolvedValue(mockResponse);

        const result = await crmApi.uploadFileToFolder(
          1,
          "Immigration",
          mockFile,
        );

        expect(mockClient.request).toHaveBeenCalledWith(
          "/api/clients/1/drive-folder/Immigration/upload",
          expect.objectContaining({
            method: "POST",
            body: expect.any(FormData),
          }),
        );
        expect(result.success).toBe(true);
        expect(result.file_id).toBe("file-123");
      });
    });

    describe("getDriveFolderStats", () => {
      it("should get folder statistics", async () => {
        const mockResponse = {
          total_files: 25,
          total_size_bytes: 5120000,
          total_size_mb: 4.88,
          last_synced: "2026-02-04T10:00:00Z",
          by_category: {
            Immigration: { files: 10, size_bytes: 2048000, size_mb: 1.95 },
            PMA: { files: 15, size_bytes: 3072000, size_mb: 2.93 },
          },
        };

        mockClient.request.mockResolvedValue(mockResponse);

        const result = await crmApi.getDriveFolderStats(1);

        expect(mockClient.request).toHaveBeenCalledWith(
          "/api/clients/1/drive-folder/stats",
        );
        expect(result.total_files).toBe(25);
        expect(result.total_size_mb).toBe(4.88);
      });
    });
  });

  describe("Family Members CRUD", () => {
    describe("getFamilyMembers", () => {
      it("should get family members for a client", async () => {
        const mockMembers = [
          {
            id: 1,
            client_id: 1,
            full_name: "Jane Doe",
            relationship: "spouse",
            passport_number: "P123456",
          },
          {
            id: 2,
            client_id: 1,
            full_name: "Jimmy Doe",
            relationship: "child",
            date_of_birth: "2015-05-15",
          },
        ];

        mockClient.request.mockResolvedValue(mockMembers);

        const result = await crmApi.getFamilyMembers(1);

        expect(mockClient.request).toHaveBeenCalledWith(
          "/api/crm/clients/1/family",
        );
        expect(result).toHaveLength(2);
        expect(result[0].relationship).toBe("spouse");
      });
    });

    describe("createFamilyMember", () => {
      it("should add a family member", async () => {
        const newMember = {
          full_name: "Jane Doe",
          relationship: "spouse",
          date_of_birth: "1990-01-15",
          nationality: "American",
          passport_number: "P123456",
          passport_expiry: "2030-01-15",
        };

        const mockResponse = { id: 10, success: true };

        mockClient.request.mockResolvedValue(mockResponse);

        const result = await crmApi.createFamilyMember(1, newMember);

        expect(mockClient.request).toHaveBeenCalledWith(
          "/api/crm/clients/1/family",
          expect.objectContaining({
            method: "POST",
            body: JSON.stringify(newMember),
          }),
        );
        expect(result.id).toBe(10);
        expect(result.success).toBe(true);
      });
    });

    describe("updateFamilyMember", () => {
      it("should update a family member", async () => {
        const updates = {
          passport_expiry: "2031-01-15",
          visa_expiry: "2027-06-30",
        };

        mockClient.request.mockResolvedValue({ success: true });

        const result = await crmApi.updateFamilyMember(1, 10, updates);

        expect(mockClient.request).toHaveBeenCalledWith(
          "/api/crm/clients/1/family/10",
          expect.objectContaining({
            method: "PATCH",
            body: JSON.stringify(updates),
          }),
        );
        expect(result.success).toBe(true);
      });
    });

    describe("deleteFamilyMember", () => {
      it("should delete a family member", async () => {
        mockClient.request.mockResolvedValue({ success: true });

        const result = await crmApi.deleteFamilyMember(1, 10);

        expect(mockClient.request).toHaveBeenCalledWith(
          "/api/crm/clients/1/family/10",
          {
            method: "DELETE",
          },
        );
        expect(result.success).toBe(true);
      });
    });
  });

  describe("Expiry Alerts", () => {
    describe("getExpiryAlerts", () => {
      it("should get all expiry alerts", async () => {
        const mockAlerts = [
          {
            entity_type: "client",
            entity_id: 1,
            entity_name: "John Doe",
            client_id: 1,
            client_name: "John Doe",
            document_type: "Passport",
            expiry_date: "2026-03-15",
            days_until_expiry: 39,
            alert_color: "yellow",
            assigned_to: "admin@balizero.com",
          },
        ];

        mockClient.request.mockResolvedValue(mockAlerts);

        const result = await crmApi.getExpiryAlerts();

        expect(mockClient.request).toHaveBeenCalledWith(
          "/api/crm/expiry-alerts",
        );
        expect(result).toHaveLength(1);
        expect(result[0].alert_color).toBe("yellow");
      });

      it("should filter expiry alerts by color and assigned user", async () => {
        mockClient.request.mockResolvedValue([]);

        await crmApi.getExpiryAlerts({
          alertColor: "red",
          assignedTo: "admin@balizero.com",
          limit: 50,
        });

        expect(mockClient.request).toHaveBeenCalledWith(
          "/api/crm/expiry-alerts?alert_color=red&assigned_to=admin%40balizero.com&limit=50",
        );
      });
    });

    describe("getExpiryAlertsSummary", () => {
      it("should get expiry alerts summary for dashboard", async () => {
        const mockSummary = {
          counts: {
            expired: 2,
            red: 5,
            yellow: 10,
            green: 50,
          },
          urgent_alerts: [
            {
              client_name: "John Doe",
              entity_name: "John Doe",
              document_type: "Passport",
              expiry_date: "2026-02-10",
              days_until_expiry: 6,
              alert_color: "red",
            },
          ],
        };

        mockClient.request.mockResolvedValue(mockSummary);

        const result = await crmApi.getExpiryAlertsSummary();

        expect(mockClient.request).toHaveBeenCalledWith(
          "/api/crm/expiry-alerts/summary",
        );
        expect(result.counts.expired).toBe(2);
        expect(result.counts.red).toBe(5);
        expect(result.urgent_alerts).toHaveLength(1);
      });
    });
  });

  describe("Client Profile (Enhanced)", () => {
    describe("getClientProfile", () => {
      it("should get enhanced client profile with family, documents, alerts", async () => {
        const mockProfile = {
          client: {
            id: 1,
            full_name: "John Doe",
            email: "john@example.com",
          },
          family_members: [
            { id: 1, full_name: "Jane Doe", relationship: "spouse" },
          ],
          documents: [{ id: 1, document_type: "Passport", status: "verified" }],
          expiry_alerts: [
            {
              entity_type: "client",
              document_type: "Passport",
              days_until_expiry: 30,
              alert_color: "yellow",
            },
          ],
          practices: [
            {
              id: 1,
              status: "active",
              practice_type_code: "KITAS",
              practice_type_name: "KITAS Work Permit",
            },
          ],
          stats: {
            family_count: 1,
            documents_count: 1,
            practices_count: 1,
            expired_count: 0,
            red_alerts: 0,
            yellow_alerts: 1,
          },
        };

        mockClient.request.mockResolvedValue(mockProfile);

        const result = await crmApi.getClientProfile(1);

        expect(mockClient.request).toHaveBeenCalledWith(
          "/api/crm/clients/1/profile",
        );
        expect(result.client.id).toBe(1);
        expect(result.family_members).toHaveLength(1);
        expect(result.documents).toHaveLength(1);
        expect(result.stats.yellow_alerts).toBe(1);
      });
    });

    describe("updateClientProfile", () => {
      it("should update client profile information", async () => {
        const updates = {
          avatar_url: "https://example.com/avatar.jpg",
          google_drive_folder_id: "folder-123",
          date_of_birth: "1985-05-15",
          passport_expiry: "2030-05-15",
        };

        mockClient.request.mockResolvedValue({ success: true });

        const result = await crmApi.updateClientProfile(1, updates);

        expect(mockClient.request).toHaveBeenCalledWith(
          "/api/crm/clients/1/profile",
          expect.objectContaining({
            method: "PATCH",
            body: JSON.stringify(updates),
          }),
        );
        expect(result.success).toBe(true);
      });
    });

    describe("getDocumentCategories", () => {
      it("should get document categories for dropdowns", async () => {
        const mockCategories = [
          {
            code: "PASSPORT",
            name: "Passport",
            category_group: "visas",
            has_expiry: true,
          },
          {
            code: "VISA",
            name: "Visa",
            category_group: "visas",
            has_expiry: true,
          },
        ];

        mockClient.request.mockResolvedValue(mockCategories);

        const result = await crmApi.getDocumentCategories();

        expect(mockClient.request).toHaveBeenCalledWith(
          "/api/crm/document-categories",
        );
        expect(result).toHaveLength(2);
        expect(result[0].has_expiry).toBe(true);
      });
    });

    describe("getClientPractices", () => {
      it("should get practices for a specific client", async () => {
        const mockPractices = [
          { id: 1, practice_type_code: "KITAS", status: "active" },
          { id: 2, practice_type_code: "PMA", status: "completed" },
        ];

        mockClient.request.mockResolvedValue(mockPractices);

        const result = await crmApi.getClientPractices(1);

        expect(mockClient.request).toHaveBeenCalledWith(
          "/api/crm/practices/?client_id=1",
        );
        expect(result).toHaveLength(2);
      });
    });

    describe("getClient", () => {
      it("should get a single client by ID", async () => {
        const mockClient = {
          id: 1,
          full_name: "John Doe",
          email: "john@example.com",
          status: "active",
        };

        (crmApi as any).client.request.mockResolvedValue(mockClient);

        const result = await crmApi.getClient(1);

        expect((crmApi as any).client.request).toHaveBeenCalledWith(
          "/api/crm/clients/1",
          undefined,
          10000,
        );
        expect(result.id).toBe(1);
      });
    });

    describe("getInteractions", () => {
      it("should get interactions with filters", async () => {
        const mockInteractions = [
          { id: 1, interaction_type: "whatsapp", summary: "Initial contact" },
          { id: 2, interaction_type: "email", summary: "Document request" },
        ];

        (crmApi as any).client.request.mockResolvedValue(mockInteractions);

        const result = await crmApi.getInteractions({
          interaction_type: "whatsapp",
          limit: 50,
        });

        expect((crmApi as any).client.request).toHaveBeenCalledWith(
          "/api/crm/interactions/?interaction_type=whatsapp&limit=50",
        );
        expect(result).toHaveLength(2);
      });
    });
  });
});
