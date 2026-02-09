import React from 'react';
import { EnrichedConversation } from '../types';
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
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
      <div className="w-[300px] border-l border-border bg-card p-6 flex flex-col items-center justify-center text-center">
        <p className="text-muted-foreground text-sm">Select a lead to view CRM details & Intelligence.</p>
      </div>
    );
  }

  // Mock CRM data for visual impact (will be real later)
  const dealValue = conversation.crmData?.dealValue || "$2,500";
  const sentiment = conversation.crmData?.sentiment || "neutral";
  const score = 75; // Mock lead score

  return (
    <div className="w-[350px] border-l border-border bg-card overflow-y-auto h-full">
      <div className="p-6 space-y-6">
        
        {/* Profile Card */}
        <div className="text-center">
          <div className="w-20 h-20 bg-muted rounded-full mx-auto mb-3 flex items-center justify-center text-2xl font-bold text-muted-foreground">
            {conversation.client_name.substring(0, 2).toUpperCase()}
          </div>
          <h2 className="font-bold text-xl">{conversation.client_name}</h2>
          <p className="text-sm text-muted-foreground">{conversation.phone}</p>
          <div className="flex justify-center gap-2 mt-3">
            <Button size="sm" variant="outline">CRM Profile</Button>
            <Button size="sm">Create Deal</Button>
          </div>
        </div>

        <Separator />

        {/* Lead Score AI */}
        <Card className="bg-gradient-to-br from-indigo-50 to-purple-50 border-indigo-100 dark:from-indigo-950/20 dark:to-purple-950/20 dark:border-indigo-900">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs uppercase font-bold text-indigo-600 flex justify-between">
              AI Lead Score
              <span className="text-lg">75/100</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="w-full bg-indigo-200 h-2 rounded-full overflow-hidden">
              <div className="bg-indigo-600 h-full w-[75%]" />
            </div>
            <p className="text-xs text-indigo-700 mt-2">
              High intent detected for <strong>PT PMA Setup</strong>. Sentiment is positive.
            </p>
          </CardContent>
        </Card>

        {/* CRM Details */}
        <div className="space-y-4">
          <h3 className="font-semibold text-sm">CRM Details</h3>
          
          <div className="grid gap-3">
            <div className="flex items-center gap-3 text-sm">
              <Briefcase className="w-4 h-4 text-muted-foreground" />
              <span>Digital Nomad (Solo)</span>
            </div>
            <div className="flex items-center gap-3 text-sm">
              <MapPin className="w-4 h-4 text-muted-foreground" />
              <span>Bali, Indonesia</span>
            </div>
            <div className="flex items-center gap-3 text-sm">
              <TrendingUp className="w-4 h-4 text-muted-foreground" />
              <span>Potential Value: <strong>{dealValue}</strong></span>
            </div>
            <div className="flex items-center gap-3 text-sm">
              <Calendar className="w-4 h-4 text-muted-foreground" />
              <span>Last Contact: Today</span>
            </div>
          </div>
        </div>

        <Separator />

        {/* Actions */}
        <div className="space-y-3">
          <h3 className="font-semibold text-sm">Workflow</h3>
          <div className="grid grid-cols-2 gap-2">
            <Button variant="outline" size="sm" className="w-full justify-start text-xs">
              <User className="w-3 h-3 mr-2" /> Assign
            </Button>
            <Button variant="outline" size="sm" className="w-full justify-start text-xs">
              <CheckCircle className="w-3 h-3 mr-2" /> Close
            </Button>
            <Button variant="outline" size="sm" className="w-full justify-start text-xs text-yellow-600 border-yellow-200 bg-yellow-50 hover:bg-yellow-100">
              <AlertTriangle className="w-3 h-3 mr-2" /> Escalate
            </Button>
          </div>
        </div>

        {/* Tags */}
        <div>
          <h3 className="font-semibold text-sm mb-2">Tags</h3>
          <div className="flex flex-wrap gap-2">
            <Badge variant="secondary" className="text-[10px]">#Visa</Badge>
            <Badge variant="secondary" className="text-[10px]">#NewLead</Badge>
            <Badge variant="outline" className="text-[10px] border-dashed border-muted-foreground">+ Add</Badge>
          </div>
        </div>

      </div>
    </div>
  );
}
