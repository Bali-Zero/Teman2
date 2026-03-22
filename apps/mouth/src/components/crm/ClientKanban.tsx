import React, { useState, useRef } from "react";
import { Client } from "@/lib/api/crm/crm.types";
import { ClientCard } from "./ClientCard";
import { motion, AnimatePresence } from "framer-motion";
import { useAutoAnimate } from "@formkit/auto-animate/react";
import { useVirtualizer } from "@tanstack/react-virtual";

interface ClientKanbanProps {
  clients: Client[];
  onStatusChange: (clientId: number, newStatus: string) => Promise<void>;
}

const COLUMNS = [
  { id: "lead", title: "Leads", color: "bg-blue-500" },
  { id: "active", title: "Active", color: "bg-green-500" },
  { id: "completed", title: "Completed", color: "bg-purple-500" },
  { id: "inactive", title: "Inactive", color: "bg-gray-500" },
  { id: "lost", title: "Lost", color: "bg-red-500" },
];

// Estimated height for ClientCard (for virtualization)
const ESTIMATED_CARD_HEIGHT = 180;
const VIRTUALIZATION_THRESHOLD = 20; // Virtualize if more than 20 items

/**
 * Virtualized column body for better performance with large lists
 */
function ColumnBody({
  clients,
  draggedClient,
  onDragStart,
  onDragEnd,
}: {
  clients: Client[];
  draggedClient: Client | null;
  onDragStart: (e: React.DragEvent, client: Client) => void;
  onDragEnd: () => void;
}) {
  const parentRef = useRef<HTMLDivElement>(null);
  const shouldVirtualize = clients.length > VIRTUALIZATION_THRESHOLD;

  const virtualizer = useVirtualizer({
    count: clients.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => ESTIMATED_CARD_HEIGHT,
    overscan: 3,
  });

  if (clients.length === 0) {
    return (
      <div className="p-3 flex-1 flex items-center justify-center">
        <div className="h-24 border-2 border-dashed border-[var(--border)] rounded-lg flex items-center justify-center text-[var(--foreground-muted)] text-xs opacity-50 w-full">
          Drop here
        </div>
      </div>
    );
  }

  if (!shouldVirtualize) {
    // For small lists, render normally (better for drag & drop)
    return (
      <div className="p-3 flex-1 overflow-y-auto space-y-3 custom-scrollbar">
        <AnimatePresence>
          {clients.map((client) => (
            <div
              key={client.id}
              draggable
              onDragStart={(e) => onDragStart(e, client)}
              onDragEnd={onDragEnd}
            >
              <ClientCard
                client={client}
                isDragging={draggedClient?.id === client.id}
              />
            </div>
          ))}
        </AnimatePresence>
      </div>
    );
  }

  // Virtualized rendering for large lists
  const virtualItems = virtualizer.getVirtualItems();

  return (
    <div
      ref={parentRef}
      className="p-3 flex-1 overflow-y-auto custom-scrollbar"
      style={{ contain: "strict" }}
    >
      <div
        style={{
          height: `${virtualizer.getTotalSize()}px`,
          width: "100%",
          position: "relative",
        }}
      >
        {virtualItems.map((virtualItem) => {
          const client = clients[virtualItem.index];
          return (
            <div
              key={client.id}
              style={{
                position: "absolute",
                top: 0,
                left: 0,
                width: "100%",
                height: `${virtualItem.size}px`,
                transform: `translateY(${virtualItem.start}px)`,
              }}
            >
              <div
                draggable
                onDragStart={(e) => onDragStart(e, client)}
                onDragEnd={onDragEnd}
                className="mb-3"
              >
                <ClientCard
                  client={client}
                  isDragging={draggedClient?.id === client.id}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export const ClientKanban = ({
  clients,
  onStatusChange,
}: ClientKanbanProps) => {
  const [draggedClient, setDraggedClient] = useState<Client | null>(null);

  // Group clients by status
  const getClientsByStatus = (status: string) => {
    return clients.filter((c) => (c.status || "lead") === status);
  };

  const handleDragStart = (e: React.DragEvent, client: Client) => {
    setDraggedClient(client);
    e.dataTransfer.setData("clientId", client.id.toString());
    e.dataTransfer.effectAllowed = "move";
    // Transparent drag image
    const img = new Image();
    img.src =
      "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7";
    e.dataTransfer.setDragImage(img, 0, 0);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
  };

  const handleDrop = async (e: React.DragEvent, status: string) => {
    e.preventDefault();
    const clientId = parseInt(e.dataTransfer.getData("clientId"));

    if (clientId && draggedClient && draggedClient.status !== status) {
      // Optimistic update handled by parent usually, but we call the handler
      await onStatusChange(clientId, status);
    }
    setDraggedClient(null);
  };

  return (
    <div className="flex gap-4 overflow-x-auto pb-4 h-[calc(100vh-220px)] min-h-[500px]">
      {COLUMNS.map((column) => (
        <div
          key={column.id}
          className="flex-shrink-0 w-80 flex flex-col rounded-xl shadow-xl backdrop-blur-md"
          style={{
            background: "rgba(25, 25, 30, 0.45)",
            border: "1px solid rgba(255, 255, 255, 0.05)",
          }}
          onDragOver={handleDragOver}
          onDrop={(e) => handleDrop(e, column.id)}
        >
          {/* Column Header */}
          <div
            className="p-3 border-b flex items-center justify-between sticky top-0 bg-inherit rounded-t-xl z-10 backdrop-blur-md"
            style={{ borderColor: "rgba(255,255,255,0.05)" }}
          >
            <div className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full ${column.color}`} />
              <h3 className="font-medium text-sm text-[var(--foreground)]">
                {column.title}
              </h3>
            </div>
            <span className="text-xs text-[var(--foreground-muted)] bg-[var(--background-elevated)] px-2 py-0.5 rounded-full">
              {getClientsByStatus(column.id).length}
            </span>
          </div>

          {/* Column Body */}
          <ColumnBody
            clients={getClientsByStatus(column.id)}
            draggedClient={draggedClient}
            onDragStart={handleDragStart}
            onDragEnd={() => setDraggedClient(null)}
          />
        </div>
      ))}
    </div>
  );
};
