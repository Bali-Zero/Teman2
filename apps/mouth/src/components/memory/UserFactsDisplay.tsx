/**
 * User Facts Display Component
 * Shows user profile facts with add/remove capabilities
 */

'use client';

import { useState } from 'react';
import { Plus, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

export interface UserFactsDisplayProps {
  facts: string[];
  maxFacts?: number;
  onAddFact?: (fact: string) => Promise<void>;
  onRemoveFact?: (index: number) => Promise<void>;
  readonly?: boolean;
}

export function UserFactsDisplay({
  facts,
  maxFacts = 10,
  onAddFact,
  onRemoveFact,
  readonly = false,
}: UserFactsDisplayProps) {
  const [newFact, setNewFact] = useState('');
  const [isAdding, setIsAdding] = useState(false);

  const handleAdd = async () => {
    if (!newFact.trim() || !onAddFact) return;
    if (facts.length >= maxFacts) {
      alert(`Maximum ${maxFacts} facts allowed`);
      return;
    }

    setIsAdding(true);
    try {
      await onAddFact(newFact.trim());
      setNewFact('');
    } catch (error) {
      console.error('Failed to add fact:', error);
    } finally {
      setIsAdding(false);
    }
  };

  const handleRemove = async (index: number) => {
    if (!onRemoveFact) return;
    try {
      await onRemoveFact(index);
    } catch (error) {
      console.error('Failed to remove fact:', error);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Profile Facts</h3>
        <span className="text-sm text-muted-foreground">
          {facts.length}/{maxFacts}
        </span>
      </div>

      <div className="space-y-2">
        {facts.length === 0 ? (
          <p className="text-sm text-muted-foreground italic">
            No facts stored yet
          </p>
        ) : (
          facts.map((fact, index) => (
            <div
              key={index}
              className="flex items-start gap-2 p-3 bg-muted rounded-lg"
            >
              <span className="flex-1 text-sm">{fact}</span>
              {!readonly && onRemoveFact && (
                <button
                  onClick={() => handleRemove(index)}
                  className="text-muted-foreground hover:text-destructive transition-colors"
                  aria-label="Remove fact"
                >
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>
          ))
        )}
      </div>

      {!readonly && onAddFact && facts.length < maxFacts && (
        <div className="flex gap-2">
          <Input
            value={newFact}
            onChange={(e) => setNewFact(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleAdd();
              }
            }}
            placeholder="Add a fact about this user..."
            disabled={isAdding}
            className="flex-1"
          />
          <Button onClick={handleAdd} disabled={isAdding || !newFact.trim()}>
            <Plus className="h-4 w-4" />
          </Button>
        </div>
      )}
    </div>
  );
}






