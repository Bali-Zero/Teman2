import React from 'react';
import { EnrichedConversation } from '../types';
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { 
  User, Briefcase, MapPin, Calendar, 
  TrendingUp, AlertTriangle, CheckCircle 
} from "lucide-react";

interface LeadContextPanelProps {
  conversation: EnrichedConversation | null;
}

export function LeadContextPanel({ conversation }: LeadContextPanelProps) {
  if (!conversation) {
    return (
      <div className="w-[350px] border-l border-slate-200 bg-white p-6 flex flex-col items-center justify-center text-center">
        <p className="text-slate-400 text-xs font-black uppercase tracking-widest leading-relaxed">
          Select a lead to unlock intelligence
        </p>
      </div>
    );
  }

  const clientName = conversation.client_name || conversation.phone || "Unknown";
  const dealValue = conversation.crmData?.dealValue || "$2,500";

  return (
    <div className="w-[350px] border-l border-white/10 bg-[#DC2626] overflow-y-auto h-full text-white shadow-2xl transition-all duration-500"> {/* Bold Red (Red 600) */}
      <div className="p-6 space-y-6">
        
        {/* Profile Card */}
        <div className="text-center">
          <div className="w-20 h-20 bg-black/20 rounded-full mx-auto mb-3 flex items-center justify-center text-2xl font-black text-white border-4 border-white/40 shadow-xl">
            {clientName.substring(0, 2).toUpperCase()}
          </div>
          <h2 className="font-black text-xl tracking-tight leading-none mb-1 uppercase">{clientName}</h2>
          <p className="text-sm text-white/80 font-black mb-4 tracking-tighter">{conversation.phone}</p>
          <div className="flex justify-center gap-2">
            <Button size="sm" variant="outline" className="bg-white/10 border-white/40 text-white hover:bg-white/20 font-black border-2 text-[10px] uppercase">CRM Profile</Button>
            <Button size="sm" className="bg-white text-red-600 hover:bg-red-50 font-black text-[10px] uppercase shadow-lg">Create Deal</Button>
          </div>
        </div>

        <div className="h-0.5 bg-white/20 w-full rounded-full" />

        {/* Lead Score AI */}
        <Card className="bg-black/30 border-white/30 text-white shadow-inner">
          <CardHeader className="pb-2">
            <CardTitle className="text-[10px] uppercase font-black text-white flex justify-between tracking-[0.2em]">
              AI LEAD SCORE
              <span className="text-lg text-white bg-red-500 px-2 py-0 rounded shadow-sm">75/100</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="w-full bg-black/40 h-3 rounded-full overflow-hidden border border-white/20 p-0.5">
              <div className="bg-gradient-to-r from-red-400 to-white h-full w-[75%] rounded-full shadow-[0_0_15px_rgba(255,255,255,0.8)]" />
            </div>
            <p className="text-xs text-white mt-4 font-black leading-tight uppercase italic tracking-tighter">
              High intent detected for <span className="text-yellow-300 underline underline-offset-4 decoration-2">PT PMA Setup</span>.
            </p>
          </CardContent>
        </Card>

        {/* CRM Details */}
        <div className="space-y-4">
          <h3 className="font-black text-[10px] uppercase tracking-[0.3em] text-white/60">Lead Intelligence</h3>
          
          <div className="grid gap-4">
            <div className="flex items-center gap-3 text-sm font-black uppercase">
              <div className="p-2 bg-black/20 rounded-xl shadow-lg border border-white/10"><Briefcase className="w-4 h-4 text-white" /></div>
              <span className="tracking-tighter">Digital Nomad (Solo)</span>
            </div>
            <div className="flex items-center gap-3 text-sm font-black uppercase">
              <div className="p-2 bg-black/20 rounded-xl shadow-lg border border-white/10"><MapPin className="w-4 h-4 text-white" /></div>
              <span className="tracking-tighter">Bali, Indonesia</span>
            </div>
            <div className="flex items-center gap-3 text-sm font-black uppercase">
              <div className="p-2 bg-black/20 rounded-xl shadow-lg border border-white/10"><TrendingUp className="w-4 h-4 text-white" /></div>
              <span className="tracking-tighter">Deal Value: <span className="text-yellow-300 bg-black/40 px-2 py-0.5 rounded ml-1">{dealValue}</span></span>
            </div>
          </div>
        </div>

        <div className="h-0.5 bg-white/20 w-full rounded-full" />

        {/* Actions */}
        <div className="space-y-3">
          <h3 className="font-black text-[10px] uppercase tracking-[0.3em] text-white/60">Team Actions</h3>
          <div className="grid grid-cols-1 gap-3">
            <Button variant="outline" size="sm" className="w-full justify-start text-[10px] font-black bg-white/10 border-white/40 text-white hover:bg-white/20 border-2 uppercase tracking-widest shadow-md">
              <User className="w-3 h-3 mr-3" /> Assign to Sales
            </Button>
            <Button variant="outline" size="sm" className="w-full justify-start text-[10px] font-black bg-white/10 border-white/40 text-white hover:bg-white/20 border-2 uppercase tracking-widest shadow-md">
              <CheckCircle className="w-3 h-3 mr-3" /> Close Ticket
            </Button>
            <Button variant="outline" size="sm" className="w-full justify-start text-[10px] font-black bg-black/40 border-yellow-400/50 text-yellow-400 hover:bg-black/60 border-2 uppercase tracking-widest shadow-lg">
              <AlertTriangle className="w-3 h-3 mr-3" /> Legal Escalation
            </Button>
          </div>
        </div>

        {/* Tags */}
        <div>
          <h3 className="font-black text-[10px] uppercase tracking-widest text-white/60 mb-2">Labels</h3>
          <div className="flex flex-wrap gap-2">
            <div className="px-3 py-1 rounded bg-black/40 text-white text-[9px] font-black uppercase border border-white/20 shadow-sm">#VISA-REQ</div>
            <div className="px-3 py-1 rounded bg-black/40 text-white text-[9px] font-black uppercase border border-white/20 shadow-sm">#HIGH-VALUE</div>
          </div>
        </div>

      </div>
    </div>
  );
}