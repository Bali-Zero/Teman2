'use client';

import React, { useState, useEffect } from 'react';
import {
  Plane,
  Calendar,
  Clock,
  FileText,
  CheckCircle2,
  AlertCircle,
  Download,
} from 'lucide-react';
import { api } from '@/lib/api';
import type { VisaInfo } from '@/lib/api/portal/portal.types';

export default function VisaPage() {
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [visaData, setVisaData] = useState<VisaInfo | null>(null);

  useEffect(() => {
    const loadVisaData = async () => {
      try {
        setIsLoading(true);
        setError(null);
        const data = await api.portal.getVisaStatus();
        setVisaData(data);
      } catch (err) {
        console.error('Failed to load visa data:', err);
        setError('Unable to load visa information. Please try again.');
      } finally {
        setIsLoading(false);
      }
    };

    loadVisaData();
  }, []);

  if (isLoading) {
    return (
      <div className="animate-pulse space-y-6">
        <div className="h-8 bg-[#1A1D24] rounded w-64"></div>
        <div className="h-48 bg-[#1A1D24] rounded-xl"></div>
        <div className="h-32 bg-[#1A1D24] rounded-xl"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <AlertCircle className="w-12 h-12 text-red-400 mb-4" />
        <h2 className="text-lg font-medium text-[#E6E7EB] mb-2">Unable to load visa information</h2>
        <p className="text-[#9AA0AE] mb-4">{error}</p>
        <button
          onClick={() => window.location.reload()}
          className="px-4 py-2 bg-[#4FD1C5] text-[#0B0E13] font-medium rounded-lg hover:bg-[#38B2AC] transition-colors"
        >
          Try Again
        </button>
      </div>
    );
  }

  if (!visaData) return null;

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
      case 'pending': return 'bg-amber-500/10 text-amber-400 border-amber-500/20';
      case 'expired': return 'bg-red-500/10 text-red-400 border-red-500/20';
      default: return 'bg-[#1A1D24] text-[#9AA0AE] border-white/10';
    }
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold text-[#E6E7EB]">Visa & Immigration</h1>
        <p className="text-[#9AA0AE] mt-1">Your immigration status and documents</p>
      </div>

      {/* Current Visa Status */}
      {visaData.current ? (
        <div className="bg-[#1A1D24] rounded-xl border border-white/5 overflow-hidden">
          <div className="p-6 border-b border-white/5">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-4">
                <div className="p-3 bg-emerald-500/10 rounded-xl">
                  <Plane className="w-6 h-6 text-emerald-400" />
                </div>
                <div>
                  <h2 className="text-lg font-semibold text-[#E6E7EB]">{visaData.current.type}</h2>
                  <p className="text-sm text-[#9AA0AE]">Permit #{visaData.current.permitNumber}</p>
                </div>
              </div>
              <span className={`px-3 py-1 rounded-full text-sm font-medium border ${getStatusColor(visaData.current.status)}`}>
                {visaData.current.status.charAt(0).toUpperCase() + visaData.current.status.slice(1)}
              </span>
            </div>
          </div>

          <div className="p-6 grid grid-cols-1 md:grid-cols-3 gap-6">
            <div>
              <p className="text-sm text-[#9AA0AE] mb-1">Issue Date</p>
              <p className="font-medium text-[#E6E7EB]">{visaData.current.issueDate}</p>
            </div>
            <div>
              <p className="text-sm text-[#9AA0AE] mb-1">Expiry Date</p>
              <p className="font-medium text-[#E6E7EB]">{visaData.current.expiryDate}</p>
            </div>
            <div>
              <p className="text-sm text-[#9AA0AE] mb-1">Days Remaining</p>
              <p className={`font-medium ${visaData.current.daysRemaining <= 60 ? 'text-orange-400' : 'text-emerald-400'}`}>
                {visaData.current.daysRemaining} days
              </p>
            </div>
            <div className="md:col-span-3">
              <p className="text-sm text-[#9AA0AE] mb-1">Sponsor</p>
              <p className="font-medium text-[#E6E7EB]">{visaData.current.sponsor}</p>
            </div>
          </div>

          {visaData.current.daysRemaining <= 60 && (
            <div className="px-6 pb-6">
              <div className="flex items-center gap-3 p-4 bg-amber-500/10 border border-amber-500/20 rounded-lg">
                <AlertCircle className="w-5 h-5 text-amber-400" />
                <div>
                  <p className="font-medium text-amber-300">Renewal Recommended</p>
                  <p className="text-sm text-amber-400/80">Your visa expires in {visaData.current.daysRemaining} days. Please contact us to start the renewal process.</p>
                </div>
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="bg-[#1A1D24] rounded-xl border border-white/5 p-8 text-center">
          <Plane className="w-12 h-12 text-[#9AA0AE] mx-auto mb-4" />
          <h3 className="font-medium text-[#E6E7EB]">No Active Visa</h3>
          <p className="text-sm text-[#9AA0AE] mt-1">Contact us to apply for a visa</p>
        </div>
      )}

      {/* History */}
      {visaData.history.length > 0 && (
        <div>
          <h2 className="text-lg font-medium text-[#E6E7EB] mb-4">Visa History</h2>
          <div className="bg-[#1A1D24] rounded-xl border border-white/5 divide-y divide-white/5">
            {visaData.history.map((item) => (
              <div key={item.id} className="p-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className={`p-2 rounded-lg ${item.status === 'completed' ? 'bg-emerald-500/10' : 'bg-[#242424]'}`}>
                    {item.status === 'completed' ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    ) : (
                      <Clock className="w-4 h-4 text-[#9AA0AE]" />
                    )}
                  </div>
                  <div>
                    <p className="font-medium text-[#E6E7EB]">{item.type}</p>
                    <p className="text-sm text-[#9AA0AE]">{item.period}</p>
                  </div>
                </div>
                <span className={`px-2 py-1 text-xs rounded-full border ${item.status === 'completed' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 'bg-[#242424] text-[#9AA0AE] border-white/10'}`}>
                  {item.status}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Documents */}
      {visaData.documents.length > 0 && (
        <div>
          <h2 className="text-lg font-medium text-[#E6E7EB] mb-4">Immigration Documents</h2>
          <div className="bg-[#1A1D24] rounded-xl border border-white/5 divide-y divide-white/5">
            {visaData.documents.map((doc) => (
              <div key={doc.id} className="p-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-blue-500/10 rounded-lg">
                    <FileText className="w-4 h-4 text-blue-400" />
                  </div>
                  <div>
                    <p className="font-medium text-[#E6E7EB]">{doc.name}</p>
                    <p className="text-sm text-[#9AA0AE]">Uploaded {doc.uploadDate}</p>
                  </div>
                </div>
                <button className="p-2 text-[#9AA0AE] hover:text-[#4FD1C5] hover:bg-[#4FD1C5]/10 rounded-lg transition-colors">
                  <Download className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Empty state for documents */}
      {visaData.documents.length === 0 && (
        <div>
          <h2 className="text-lg font-medium text-[#E6E7EB] mb-4">Immigration Documents</h2>
          <div className="bg-[#1A1D24] rounded-xl border border-white/5 p-8 text-center">
            <FileText className="w-12 h-12 text-[#9AA0AE] mx-auto mb-4" />
            <h3 className="font-medium text-[#E6E7EB]">No Documents</h3>
            <p className="text-sm text-[#9AA0AE] mt-1">Your immigration documents will appear here</p>
          </div>
        </div>
      )}
    </div>
  );
}
