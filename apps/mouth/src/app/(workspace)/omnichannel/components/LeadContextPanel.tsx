import React from 'react';
import { EnrichedConversation } from '../types';
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { 
  User, Briefcase, MapPin, 
  TrendingUp, AlertTriangle, CheckCircle 
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

interface LeadContextPanelProps {
  conversation: EnrichedConversation | null;
  enrichment: any;
  onAssign: (userId: string) => void;
  onStatusChange: (status: string) => void;
  isLoading?: boolean;
}

export function LeadContextPanel({ conversation, enrichment, onAssign, onStatusChange, isLoading }: LeadContextPanelProps) {
  if (!conversation) {
    return (
      <div className="w-[350px] border-l border-slate-200 bg-white p-6 flex flex-col items-center justify-center text-center">
        <p className="text-slate-400 text-xs font-black uppercase tracking-widest leading-relaxed">
          Select a lead to unlock intelligence
        </p>
      </div>
    );
  }

  const clientName = enrichment?.profile?.full_name || conversation.client_name || "Unknown Lead";
  const email = enrichment?.profile?.email || "No email linked";
  const nationality = enrichment?.profile?.nationality || "Unknown Nationality";
  const crmStatus = enrichment?.profile?.status || "Prospect";
  
  const practices = enrichment?.practices || [];

  return (
    <motion.div 
      initial={{ x: 50, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      className="w-[350px] border-l border-white/10 bg-[#0EA5E9] overflow-y-auto h-full text-white shadow-2xl transition-all duration-500"
    >
      <div className="p-6 space-y-6">
        
        {/* Profile Card */}
        <div className="text-center">
          <motion.div 
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className="w-20 h-20 bg-black/20 rounded-full mx-auto mb-3 flex items-center justify-center text-2xl font-black text-white border-4 border-white/40 shadow-xl"
          >
            {clientName.substring(0, 2).toUpperCase()}
          </motion.div>
          <h2 className="font-black text-xl tracking-tight leading-none mb-1 uppercase drop-shadow-md">{clientName}</h2>
          <p className="text-[10px] text-white/70 font-black mb-1 tracking-tighter uppercase">{email}</p>
          <p className="text-sm text-white font-black mb-4 tracking-tighter">{conversation.phone}</p>
          
          <div className="flex justify-center gap-2">
            <Button size="sm" variant="outline" className="bg-white/10 border-white/30 text-white hover:bg-white/20 font-black border-2 text-[10px] uppercase transition-all active:scale-95">
              {enrichment?.exists_in_crm ? "Profile Details" : "Add to CRM"}
            </Button>
          </div>
        </div>

        <div className="h-0.5 bg-white/20 w-full rounded-full" />

        {/* Lead Intelligence */}
        <Card className="bg-black/20 border-white/30 text-white shadow-xl overflow-hidden">
          <CardHeader className="pb-2 bg-black/10">
            <CardTitle className="text-[10px] uppercase font-black text-white flex justify-between tracking-[0.2em]">
              SYSTEM CONTEXT
              <span className="text-[10px] text-white bg-blue-600 px-2 py-0.5 rounded uppercase font-black shadow-lg border border-white/20">{crmStatus}</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-4">
            {isLoading ? (
              <div className="space-y-2">
                <Skeleton className="h-4 w-full bg-white/10" />
                <Skeleton className="h-4 w-2/3 bg-white/10" />
              </div>
            ) : enrichment?.exists_in_crm ? (
              <div className="space-y-3">
                <div className="flex items-center gap-2 text-xs font-black uppercase text-blue-100">
                  <CheckCircle className="w-4 h-4" /> CRM Linked Verified
                </div>
                <p className="text-[11px] text-white leading-relaxed font-black italic bg-white/10 p-3 rounded border border-white/20 shadow-inner">
                  "{enrichment.profile.notes || "Ready for follow-up. High engagement detected."}"
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                <div className="flex items-center gap-2 text-xs font-black text-white uppercase animate-pulse">
                  <AlertTriangle className="w-4 h-4 text-yellow-300" /> Lead Sync Required
                </div>
                <Button 
                  onClick={() => onStatusChange('open')}
                  size="sm" className="w-full bg-white text-blue-600 font-black text-[10px] uppercase shadow-lg hover:bg-blue-50"
                >
                  Initialize Sync
                </Button>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Actions */}
        <div className="space-y-3">
          <h3 className="font-black text-[10px] uppercase tracking-[0.3em] text-white/60">Quick Operations</h3>
          <div className="grid grid-cols-1 gap-3">
            <Button 
              onClick={() => onAssign('Team Member')}
              variant="outline" size="sm" className="w-full justify-start text-[10px] font-black bg-white/10 border-white/40 text-white hover:bg-white/20 border-2 uppercase tracking-widest shadow-md active:scale-95 transition-all"
            >
              <User className="w-3 h-3 mr-3" /> Assign to Me
            </Button>
            <Button 
              onClick={() => onStatusChange('closed')}
              variant="outline" size="sm" className="w-full justify-start text-[10px] font-black bg-black/30 border-white/20 text-white hover:bg-black/40 border-2 uppercase tracking-widest shadow-lg active:scale-95 transition-all"
            >
              <CheckCircle className="w-3 h-3 mr-3" /> Processed & Close
            </Button>
            <Button 
              onClick={() => onStatusChange('escalated')}
              variant="outline" size="sm" className="w-full justify-start text-[10px] font-black bg-yellow-400 text-blue-900 hover:bg-yellow-300 border-none uppercase tracking-widest shadow-lg active:scale-95 transition-all"
            >
              <AlertTriangle className="w-3 h-3 mr-3" /> Legal Escalation
            </Button>
          </div>
        </div>

      </div>
    </motion.div>
  );
}