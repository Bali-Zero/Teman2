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
      <div className="w-[350px] border-l border-slate-200 bg-[#FFF9F5] p-6 flex flex-col items-center justify-center text-center">
        <p className="text-amber-900/40 text-xs font-black uppercase tracking-widest leading-relaxed">
          Select a lead to unlock intelligence
        </p>
      </div>
    );
  }

  const clientName = conversation.client_name || conversation.phone || "Unknown";
  const dealValue = conversation.crmData?.dealValue || "$2,500";

  return (
    <div className="w-[350px] border-l border-white/10 bg-[#EA580C] overflow-y-auto h-full text-white shadow-2xl"> {/* Claude Orange (Orange 600) */}
      <div className="p-6 space-y-6">
        
        {/* Profile Card */}
        <div className="text-center">
          <div className="w-20 h-20 bg-white/20 rounded-full mx-auto mb-3 flex items-center justify-center text-2xl font-black text-white border-4 border-white/30">
            {clientName.substring(0, 2).toUpperCase()}
          </div>
          <h2 className="font-black text-xl tracking-tight leading-none mb-1">{clientName}</h2>
          <p className="text-sm text-white/70 font-bold mb-4">{conversation.phone}</p>
          <div className="flex justify-center gap-2">
            <Button size="sm" variant="outline" className="bg-white/10 border-white/30 text-white hover:bg-white/20 font-bold border-2">CRM Profile</Button>
            <Button size="sm" className="bg-white text-orange-600 hover:bg-orange-50 font-black">Create Deal</Button>
          </div>
        </div>

        <div className="h-px bg-white/20 w-full" />

        {/* Lead Score AI */}
        <Card className="bg-white/10 border-white/20 text-white">
          <CardHeader className="pb-2">
            <CardTitle className="text-[10px] uppercase font-black text-white/80 flex justify-between tracking-widest">
              AI LEAD SCORE
              <span className="text-lg text-white">75/100</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="w-full bg-black/20 h-2.5 rounded-full overflow-hidden border border-white/10">
              <div className="bg-white h-full w-[75%] shadow-[0_0_10px_rgba(255,255,255,0.5)]" />
            </div>
            <p className="text-xs text-white/90 mt-3 font-bold leading-snug">
              High intent detected for <span className="underline decoration-white/40">PT PMA Setup</span>. Sentiment is positive.
            </p>
          </CardContent>
        </Card>

        {/* CRM Details */}
        <div className="space-y-4">
          <h3 className="font-black text-xs uppercase tracking-widest text-white/60">Lead Data</h3>
          
          <div className="grid gap-4">
            <div className="flex items-center gap-3 text-sm font-bold">
              <div className="p-2 bg-white/10 rounded-lg"><Briefcase className="w-4 h-4 text-white" /></div>
              <span>Digital Nomad (Solo)</span>
            </div>
            <div className="flex items-center gap-3 text-sm font-bold">
              <div className="p-2 bg-white/10 rounded-lg"><MapPin className="w-4 h-4 text-white" /></div>
              <span>Bali, Indonesia</span>
            </div>
            <div className="flex items-center gap-3 text-sm font-bold">
              <div className="p-2 bg-white/10 rounded-lg"><TrendingUp className="w-4 h-4 text-white" /></div>
              <span>Potential: <span className="text-white bg-black/20 px-2 py-0.5 rounded">{dealValue}</span></span>
            </div>
          </div>
        </div>

        <div className="h-px bg-white/20 w-full" />

        {/* Actions */}
        <div className="space-y-3">
          <h3 className="font-black text-xs uppercase tracking-widest text-white/60">Quick Actions</h3>
          <div className="grid grid-cols-1 gap-2">
            <Button variant="outline" size="sm" className="w-full justify-start text-xs font-black bg-white/10 border-white/20 text-white hover:bg-white/20 border-2 uppercase">
              <User className="w-3 h-3 mr-3" /> Assign to Sales
            </Button>
            <Button variant="outline" size="sm" className="w-full justify-start text-xs font-black bg-white/10 border-white/20 text-white hover:bg-white/20 border-2 uppercase">
              <CheckCircle className="w-3 h-3 mr-3" /> Mark as Processed
            </Button>
            <Button variant="outline" size="sm" className="w-full justify-start text-xs font-black bg-red-500/20 border-red-500/40 text-red-100 hover:bg-red-500/30 border-2 uppercase">
              <AlertTriangle className="w-3 h-3 mr-3" /> Escalate to Legal
            </Button>
          </div>
        </div>

        {/* Tags */}
        <div>
          <h3 className="font-black text-[10px] uppercase tracking-widest text-white/60 mb-2">Internal Tags</h3>
          <div className="flex flex-wrap gap-2">
            <div className="px-3 py-1 rounded-full bg-white/20 text-white text-[9px] font-black uppercase border border-white/10">#Visa</div>
            <div className="px-3 py-1 rounded-full bg-white/20 text-white text-[9px] font-black uppercase border border-white/10">#PT-PMA</div>
          </div>
        </div>

      </div>
    </div>
  );
}
