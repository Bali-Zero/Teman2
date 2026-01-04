
import React, { useState } from 'react';
import { Client } from '@/lib/api/crm/crm.types';
import { ClientCard } from './ClientCard';
import { motion, AnimatePresence } from 'framer-motion';
import { useAutoAnimate } from '@formkit/auto-animate/react';

interface ClientKanbanProps {
  clients: Client[];
  onStatusChange: (clientId: number, newStatus: string) => Promise<void>;
}

const COLUMNS = [
  { id: 'lead', title: 'Leads', color: 'bg-blue-500' },
  { id: 'prospect', title: 'Prospects', color: 'bg-purple-500' },
  { id: 'active', title: 'Active', color: 'bg-green-500' },
  { id: 'inactive', title: 'Inactive', color: 'bg-gray-500' },
  { id: 'completed', title: 'Completed', color: 'bg-indigo-500' }
];

export const ClientKanban = ({ clients, onStatusChange }: ClientKanbanProps) => {
  const [draggedClient, setDraggedClient] = useState<Client | null>(null);
  
  // Group clients by status
  const getClientsByStatus = (status: string) => {
    return clients.filter(c => (c.status || 'lead') === status);
  };

  const handleDragStart = (e: React.DragEvent, client: Client) => {
    setDraggedClient(client);
    e.dataTransfer.setData('clientId', client.id.toString());
    e.dataTransfer.effectAllowed = 'move';
    // Transparent drag image
    const img = new Image();
    img.src = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';
    e.dataTransfer.setDragImage(img, 0, 0);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
  };

  const handleDrop = async (e: React.DragEvent, status: string) => {
    e.preventDefault();
    const clientId = parseInt(e.dataTransfer.getData('clientId'));
    
    if (clientId && draggedClient && draggedClient.status !== status) {
      // Optimistic update handled by parent usually, but we call the handler
      await onStatusChange(clientId, status);
    }
    setDraggedClient(null);
  };

  return (
    <div className="flex gap-4 overflow-x-auto pb-4 h-[calc(100vh-220px)] min-h-[500px]">
      {COLUMNS.map(column => (
        <div 
          key={column.id}
          className="flex-shrink-0 w-80 flex flex-col rounded-xl bg-[var(--background-secondary)]/50 border border-[var(--border)]"
          onDragOver={handleDragOver}
          onDrop={(e) => handleDrop(e, column.id)}
        >
          {/* Column Header */}
          <div className="p-3 border-b border-[var(--border)] flex items-center justify-between sticky top-0 bg-inherit rounded-t-xl z-10 backdrop-blur-sm">
            <div className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full ${column.color}`} />
              <h3 className="font-medium text-sm text-[var(--foreground)]">{column.title}</h3>
            </div>
            <span className="text-xs text-[var(--foreground-muted)] bg-[var(--background-elevated)] px-2 py-0.5 rounded-full">
              {getClientsByStatus(column.id).length}
            </span>
          </div>

          {/* Column Body */}
          <div className="p-3 flex-1 overflow-y-auto space-y-3 custom-scrollbar">
            <AnimatePresence>
              {getClientsByStatus(column.id).map(client => (
                <div
                  key={client.id}
                  draggable
                  onDragStart={(e) => handleDragStart(e, client)}
                  onDragEnd={() => setDraggedClient(null)}
                >
                  <ClientCard 
                    client={client} 
                    isDragging={draggedClient?.id === client.id}
                  />
                </div>
              ))}
            </AnimatePresence>
            
            {getClientsByStatus(column.id).length === 0 && (
              <div className="h-24 border-2 border-dashed border-[var(--border)] rounded-lg flex items-center justify-center text-[var(--foreground-muted)] text-xs opacity-50">
                Drop here
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
};
