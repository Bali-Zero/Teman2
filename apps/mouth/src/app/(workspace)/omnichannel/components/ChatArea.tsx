import React from 'react';
import { EnrichedConversation, Message } from '../types';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Send, Paperclip, Mic, Lock, User, Bot } from "lucide-react";
import { cn } from "@/lib/utils";

interface ChatAreaProps {
  conversation: EnrichedConversation | null;
  messages: Message[];
  onSendMessage: (text: string, isNote: boolean) => void;
}

export function ChatArea({ conversation, messages, onSendMessage }: ChatAreaProps) {
  const [inputText, setInputText] = React.useState('');
  const [isInternalNote, setIsInternalNote] = React.useState(false);

  if (!conversation) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-muted-foreground bg-muted/10">
        <Bot className="w-16 h-16 mb-4 opacity-20" />
        <p className="text-lg font-medium">Select a conversation to start working</p>
        <p className="text-sm">Pick a lead from the inbox on the left.</p>
      </div>
    );
  }

  const handleSend = () => {
    if (!inputText.trim()) return;
    onSendMessage(inputText, isInternalNote);
    setInputText('');
  };

  const clientName = conversation.client_name || conversation.phone || "Unknown";

  return (
    <div className="flex flex-col h-full bg-background border-r border-border">
      {/* Header */}
      <div className="h-16 border-b border-border flex items-center justify-between px-6 bg-card/50">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-full bg-muted flex items-center justify-center font-bold text-muted-foreground border-2 border-background">
            {clientName.substring(0, 2).toUpperCase()}
          </div>
          <div>
            <h3 className="font-semibold text-foreground flex items-center gap-2">
              {clientName}
              <span className={cn(
                "px-2 py-0.5 rounded-full text-[10px] uppercase font-bold tracking-wider",
                conversation.channel === 'whatsapp' && "bg-green-100 text-green-700",
                conversation.channel === 'telegram' && "bg-blue-100 text-blue-700",
                conversation.channel === 'instagram' && "bg-pink-100 text-pink-700",
              )}>
                {conversation.channel}
              </span>
            </h3>
            <p className="text-xs text-muted-foreground">
              {conversation.phone} • Last active {new Date(conversation.last_message_date).toLocaleTimeString()}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm">Mark as Done</Button>
        </div>
      </div>

      {/* Messages Stream */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-muted/5">
        {messages.map((msg) => (
          <div key={msg.id} className={cn(
            "flex w-full",
            msg.sender === 'agent' ? "justify-end" : "justify-start"
          )}>
            <div className={cn(
              "max-w-[70%] rounded-2xl px-4 py-3 shadow-sm",
              msg.sender === 'agent' && !msg.isInternalNote && "bg-primary text-primary-foreground rounded-tr-none",
              msg.sender === 'user' && "bg-card border border-border text-foreground rounded-tl-none",
              msg.isInternalNote && "bg-yellow-100 border-yellow-200 text-yellow-900 border"
            )}>
              {msg.isInternalNote && (
                <div className="flex items-center gap-1 text-[10px] font-bold uppercase mb-1 opacity-70">
                  <Lock className="w-3 h-3" /> Internal Note
                </div>
              )}
              <p className="text-sm whitespace-pre-wrap leading-relaxed">{msg.text}</p>
              <span className="text-[10px] opacity-50 mt-2 block text-right">
                {new Date(msg.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Input Area */}
      <div className={cn(
        "p-4 border-t border-border transition-colors duration-300",
        isInternalNote ? "bg-yellow-50/50" : "bg-background"
      )}>
        <div className="flex items-center gap-2 mb-2">
          <div className="flex bg-muted rounded-lg p-1">
            <button 
              onClick={() => setIsInternalNote(false)}
              className={cn(
                "px-3 py-1 rounded-md text-xs font-medium transition-all",
                !isInternalNote ? "bg-background shadow-sm text-foreground" : "text-muted-foreground hover:text-foreground"
              )}
            >
              Reply
            </button>
            <button 
              onClick={() => setIsInternalNote(true)}
              className={cn(
                "px-3 py-1 rounded-md text-xs font-medium transition-all flex items-center gap-1",
                isInternalNote ? "bg-yellow-100 text-yellow-800 shadow-sm" : "text-muted-foreground hover:text-foreground"
              )}
            >
              <Lock className="w-3 h-3" /> Note
            </button>
          </div>
        </div>
        <div className="relative">
          <Input 
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder={isInternalNote ? "Add a private note for the team..." : "Type a message to the client..."}
            className={cn(
              "pr-24 min-h-[50px] py-3",
              isInternalNote && "bg-yellow-50 border-yellow-200 focus-visible:ring-yellow-400"
            )}
          />
          <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
            <Button size="icon" variant="ghost" className="h-8 w-8 text-muted-foreground hover:text-foreground">
              <Paperclip className="w-4 h-4" />
            </Button>
            <Button size="icon" variant="ghost" className="h-8 w-8 text-muted-foreground hover:text-foreground">
              <Mic className="w-4 h-4" />
            </Button>
            <Button 
              size="icon" 
              onClick={handleSend}
              className={cn(
                "h-8 w-8 ml-1",
                isInternalNote ? "bg-yellow-500 hover:bg-yellow-600 text-white" : ""
              )}
            >
              <Send className="w-4 h-4" />
            </Button>
          </div>
        </div>
        <div className="flex justify-between items-center mt-2 px-1">
          <span className="text-[10px] text-muted-foreground">
            <strong>AI Draft:</strong> Press <kbd className="bg-muted px-1 rounded">Tab</kbd> to complete
          </span>
        </div>
      </div>
    </div>
  );
}