import React from 'react';
import { EnrichedConversation } from '../types';
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { 
  User, Briefcase, MapPin, Calendar, 
  TrendingUp, AlertTriangle, CheckCircle, Search
} from "lucide-react";

interface LeadContextPanelProps {
  conversation: EnrichedConversation | null;
  enrichment: any;
  onAssign: (userId: string) => void;
}

export function LeadContextPanel({ conversation, enrichment, onAssign }: LeadContextPanelProps) {
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
  
  // Real practices from CRM
  const practices = enrichment?.practices || [];

  return (
    <div className="w-[350px] border-l border-white/10 bg-[#DC2626] overflow-y-auto h-full text-white shadow-2xl transition-all duration-500">
      <div className="p-6 space-y-6">
        
        {/* Profile Card */}
        <div className="text-center">
          <div className="w-20 h-20 bg-black/20 rounded-full mx-auto mb-3 flex items-center justify-center text-2xl font-black text-white border-4 border-white/40 shadow-xl">
            {clientName.substring(0, 2).toUpperCase()}
          </div>
          <h2 className="font-black text-xl tracking-tight leading-none mb-1 uppercase">{clientName}</h2>
          <p className="text-[10px] text-white/60 font-black mb-1 tracking-tighter uppercase">{email}</p>
          <p className="text-sm text-white/80 font-black mb-4 tracking-tighter">{conversation.phone}</p>
          
          <div className="flex justify-center gap-2">
            <Button size="sm" variant="outline" className="bg-white/10 border-white/30 text-white hover:bg-white/20 font-black border-2 text-[10px] uppercase">
              {enrichment?.exists_in_crm ? "View CRM Profile" : "Add to CRM"}
            </Button>
          </div>
        </div>

        <div className="h-0.5 bg-white/20 w-full rounded-full" />

        {/* Lead Intelligence */}
        <Card className="bg-black/30 border-white/30 text-white shadow-inner">
          <CardHeader className="pb-2">
            <CardTitle className="text-[10px] uppercase font-black text-white flex justify-between tracking-[0.2em]">
              CRM MATCH STATUS
              <span className="text-[10px] text-white bg-black/40 px-2 py-0.5 rounded uppercase">{crmStatus}</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {enrichment?.exists_in_crm ? (
              <div className="space-y-3 mt-2">
                <div className="flex items-center gap-2 text-xs font-bold">
                  <CheckCircle className="w-4 h-4 text-green-400" /> Linked to Client Record
                </div>
                <p className="text-[10px] text-white/80 leading-relaxed font-medium italic">
                  "{enrichment.profile.notes || "No recent notes in CRM."}"
                </p>
              </div>
            ) : (
              <div className="space-y-3 mt-2">
                <div className="flex items-center gap-2 text-xs font-bold text-yellow-300 uppercase">
                  <AlertTriangle className="w-4 h-4" /> New Lead (No CRM Match)
                </div>
                <Button size="sm" className="w-full bg-white text-red-600 font-black text-[10px] uppercase">Initialize Profile</Button>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Active Practices */}
        {practices.length > 0 && (
          <div className="space-y-3">
            <h3 className="font-black text-[10px] uppercase tracking-[0.3em] text-white/60 italic">Active Deals</h3>
            {practices.map((p: any, i: number) => (
              <div key={i} className="bg-black/20 p-3 rounded-lg border border-white/10">
                <div className="flex justify-between items-start mb-1">
                  <span className="text-xs font-black uppercase">{p.practice_name}</span>
                  <span className="text-[9px] bg-white/20 px-1.5 rounded">{p.status}</span>
                </div>
                <div className="text-[10px] font-bold text-white/60 italic">Value: {p.quoted_price ? `${p.quoted_price} IDR` : "Not quoted"}</div>
              </div>
            ))}
          </div>
        )}

        {/* Lead Data */}
        <div className="space-y-4">
          <h3 className="font-black text-[10px] uppercase tracking-[0.3em] text-white/60">Lead Data</h3>
          <div className="grid gap-4">
            <div className="flex items-center gap-3 text-sm font-black uppercase">
              <div className="p-2 bg-black/20 rounded-xl shadow-lg border border-white/10"><MapPin className="w-4 h-4 text-white" /></div>
              <span className="tracking-tighter">{nationality}</span>
            </div>
            <div className="flex items-center gap-3 text-sm font-black uppercase">
              <div className="p-2 bg-black/20 rounded-xl shadow-lg border border-white/10"><Briefcase className="w-4 h-4 text-white" /></div>
              <span className="tracking-tighter">{enrichment?.profile?.client_type || "Prospect"}</span>
            </div>
          </div>
        </div>

        <div className="h-0.5 bg-white/20 w-full rounded-full" />

        {/* Actions */}
        <div className="space-y-3">
          <h3 className="font-black text-[10px] uppercase tracking-[0.3em] text-white/60">Team Actions</h3>
          <div className="grid grid-cols-1 gap-3">
            <Button 
              onClick={() => onAssign('Sales Team')}
              variant="outline" size="sm" className="w-full justify-start text-[10px] font-black bg-white/10 border-white/40 text-white hover:bg-white/20 border-2 uppercase tracking-widest shadow-md"
            >
              <User className="w-3 h-3 mr-3" /> Assign to Me
            </Button>
            <Button variant="outline" size="sm" className="w-full justify-start text-[10px] font-black bg-black/40 border-yellow-400/50 text-yellow-400 hover:bg-black/60 border-2 uppercase tracking-widest shadow-lg">
              <AlertTriangle className="w-3 h-3 mr-3" /> Escalate to Legal
            </Button>
          </div>
        </div>

      </div>
    </div>
  );
}
