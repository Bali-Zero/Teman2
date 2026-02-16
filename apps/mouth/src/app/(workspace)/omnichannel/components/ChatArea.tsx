import React, { useEffect, useRef } from "react";
import { EnrichedConversation, Message } from "../types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Send, Paperclip, Mic, Lock, Bot } from "lucide-react";
import { cn } from "@/lib/utils";
import { motion, AnimatePresence } from "framer-motion";

interface ChatAreaProps {
  conversation: EnrichedConversation | null;
  messages: Message[];
  onSendMessage: (text: string, isNote: boolean) => void;
  onStatusChange?: (status: string) => void;
  isLoading?: boolean;
}

export function ChatArea({
  conversation,
  messages,
  onSendMessage,
  onStatusChange,
  isLoading,
}: ChatAreaProps) {
  const [inputText, setInputText] = React.useState("");
  const [isInternalNote, setIsInternalNote] = React.useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTo({
        top: scrollRef.current.scrollHeight,
        behavior: "smooth",
      });
    }
  }, [messages, isLoading]);

  if (!conversation) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-slate-400 bg-[#f8fafc]">
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5 }}
          className="flex flex-col items-center"
        >
          <Bot className="w-16 h-16 mb-4 opacity-20" />
          <p className="text-lg font-bold uppercase tracking-widest">
            Select a conversation
          </p>
          <p className="text-xs font-black text-blue-500 uppercase">
            --- SYSTEM VERIFIED v2.2 ---
          </p>
        </motion.div>
      </div>
    );
  }

  const handleSend = () => {
    if (!inputText.trim()) return;
    onSendMessage(inputText, isInternalNote);
    setInputText("");
  };

  const clientName =
    conversation.client_name || conversation.phone || "Unknown";

  return (
    <div className="flex flex-col h-full bg-[#f3f4f6] overflow-hidden">
      {/* Header */}
      <motion.div
        initial={{ y: -20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        className="h-16 border-b border-slate-200 flex items-center justify-between px-6 bg-white shadow-sm z-10"
      >
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-full bg-slate-800 flex items-center justify-center font-bold text-white border-2 border-white shadow-sm">
            {clientName.substring(0, 2).toUpperCase()}
          </div>
          <div>
            <h3 className="font-bold text-slate-900 flex items-center gap-2">
              {clientName}
              <span
                className={cn(
                  "px-2 py-0.5 rounded-full text-[10px] uppercase font-black tracking-widest",
                  conversation.channel === "whatsapp" &&
                    "bg-green-100 text-green-700",
                  conversation.channel === "telegram" &&
                    "bg-blue-100 text-blue-700",
                  conversation.channel === "instagram" &&
                    "bg-pink-100 text-pink-700",
                )}
              >
                {conversation.channel}
              </span>
            </h3>
            <p className="text-[10px] font-bold text-slate-500 uppercase tracking-tight">
              {conversation.phone}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            onClick={() => onStatusChange?.("closed")}
            variant="outline"
            size="sm"
            className="font-bold text-xs uppercase border-slate-300 hover:bg-slate-50 transition-colors"
          >
            Mark as Done
          </Button>
        </div>
      </motion.div>

      {/* Messages Stream */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-6 space-y-4 scroll-smooth"
      >
        <AnimatePresence initial={false}>
          {messages.map((msg) => (
            <motion.div
              key={msg.id}
              initial={{ opacity: 0, y: 10, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              transition={{ duration: 0.2 }}
              className={cn(
                "flex w-full",
                msg.sender === "agent" ? "justify-end" : "justify-start",
              )}
            >
              <div
                className={cn(
                  "max-w-[75%] rounded-2xl px-4 py-3 shadow-sm transition-all",
                  msg.sender === "agent" &&
                    !msg.isInternalNote &&
                    "bg-slate-800 text-white rounded-tr-none hover:bg-slate-700",
                  msg.sender === "user" &&
                    "bg-white border border-slate-200 text-slate-900 rounded-tl-none font-medium hover:border-slate-300",
                  msg.isInternalNote &&
                    "bg-amber-100 border-amber-200 text-amber-900 border font-medium shadow-inner",
                )}
              >
                {msg.isInternalNote && (
                  <div className="flex items-center gap-1 text-[9px] font-black uppercase mb-1 text-amber-700">
                    <Lock className="w-3 h-3" /> Internal Team Note
                  </div>
                )}
                <p className="text-sm whitespace-pre-wrap leading-relaxed tracking-tight">
                  {msg.text}
                </p>
                <span
                  className={cn(
                    "text-[9px] mt-2 block text-right font-bold uppercase opacity-50",
                    msg.sender === "agent" ? "text-white/70" : "text-slate-400",
                  )}
                >
                  {new Date(msg.timestamp).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </span>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>

      {/* Input Area */}
      <div
        className={cn(
          "p-4 border-t border-slate-200 bg-white transition-all duration-300",
          isInternalNote ? "bg-amber-50" : "bg-white",
        )}
      >
        <div className="flex items-center gap-2 mb-2">
          <div className="flex bg-slate-100 rounded-lg p-1 border border-slate-200 shadow-sm">
            <button
              onClick={() => setIsInternalNote(false)}
              className={cn(
                "px-4 py-1 rounded-md text-[10px] font-black uppercase transition-all",
                !isInternalNote
                  ? "bg-white shadow-sm text-slate-900"
                  : "text-slate-400 hover:text-slate-600",
              )}
            >
              Reply
            </button>
            <button
              onClick={() => setIsInternalNote(true)}
              className={cn(
                "px-4 py-1 rounded-md text-[10px] font-black uppercase transition-all flex items-center gap-1",
                isInternalNote
                  ? "bg-amber-200 text-amber-900 shadow-sm"
                  : "text-slate-400 hover:text-slate-600",
              )}
            >
              <Lock className="w-3 h-3" /> Team Note
            </button>
          </div>
        </div>
        <div className="relative">
          <Input
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            placeholder={
              isInternalNote
                ? "Add a private team note..."
                : "Type your message..."
            }
            className={cn(
              "pr-24 min-h-[50px] py-3 border-slate-300 font-medium placeholder:text-slate-400 shadow-sm transition-all focus:shadow-md",
              isInternalNote &&
                "bg-amber-50 border-amber-300 focus-visible:ring-amber-400",
            )}
          />
          <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
            <Button
              size="icon"
              variant="ghost"
              className="h-8 w-8 text-slate-400 hover:bg-slate-100"
            >
              <Paperclip className="w-4 h-4" />
            </Button>
            <Button
              size="icon"
              onClick={handleSend}
              className={cn(
                "h-8 w-8 ml-1 rounded-full shadow-lg transition-all active:scale-95",
                isInternalNote
                  ? "bg-amber-500 hover:bg-amber-600 text-white"
                  : "bg-slate-900 hover:bg-slate-800 text-white",
              )}
            >
              <Send className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
