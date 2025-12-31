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
        <div className="h-8 bg-slate-200 rounded w-64"></div>
        <div className="h-48 bg-slate-200 rounded-xl"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <AlertCircle className="w-12 h-12 text-red-500 mb-4" />
        <h2 className="text-lg font-medium text-slate-800 mb-2">Unable to load visa information</h2>
        <p className="text-slate-500 mb-4">{error}</p>
        <button
          onClick={() => window.location.reload()}
          className="px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors"
        >
          Try Again
        </button>
      </div>
    );
  }

  if (!visaData) return null;

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return 'bg-emerald-100 text-emerald-700';
      case 'pending': return 'bg-amber-100 text-amber-700';
      case 'expired': return 'bg-red-100 text-red-700';
      default: return 'bg-slate-100 text-slate-700';
    }
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold text-slate-800">Visa & Immigration</h1>
        <p className="text-slate-500 mt-1">Your immigration status and documents</p>
      </div>

      {/* Current Visa Status */}
      {visaData.current ? (
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <div className="p-6 border-b border-slate-100">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-4">
                <div className="p-3 bg-emerald-100 rounded-xl">
                  <Plane className="w-6 h-6 text-emerald-600" />
                </div>
                <div>
                  <h2 className="text-lg font-semibold text-slate-800">{visaData.current.type}</h2>
                  <p className="text-sm text-slate-500">Permit #{visaData.current.permitNumber}</p>
                </div>
              </div>
              <span className={`px-3 py-1 rounded-full text-sm font-medium ${getStatusColor(visaData.current.status)}`}>
                {visaData.current.status.charAt(0).toUpperCase() + visaData.current.status.slice(1)}
              </span>
            </div>
          </div>

          <div className="p-6 grid grid-cols-1 md:grid-cols-3 gap-6">
            <div>
              <p className="text-sm text-slate-500 mb-1">Issue Date</p>
              <p className="font-medium text-slate-800">{visaData.current.issueDate}</p>
            </div>
            <div>
              <p className="text-sm text-slate-500 mb-1">Expiry Date</p>
              <p className="font-medium text-slate-800">{visaData.current.expiryDate}</p>
            </div>
            <div>
              <p className="text-sm text-slate-500 mb-1">Days Remaining</p>
              <p className={`font-medium ${visaData.current.daysRemaining <= 60 ? 'text-orange-600' : 'text-emerald-600'}`}>
                {visaData.current.daysRemaining} days
              </p>
            </div>
            <div className="md:col-span-3">
              <p className="text-sm text-slate-500 mb-1">Sponsor</p>
              <p className="font-medium text-slate-800">{visaData.current.sponsor}</p>
            </div>
          </div>

          {visaData.current.daysRemaining <= 60 && (
            <div className="px-6 pb-6">
              <div className="flex items-center gap-3 p-4 bg-amber-50 border border-amber-200 rounded-lg">
                <AlertCircle className="w-5 h-5 text-amber-600" />
                <div>
                  <p className="font-medium text-amber-800">Renewal Recommended</p>
                  <p className="text-sm text-amber-600">Your visa expires in {visaData.current.daysRemaining} days. Please contact us to start the renewal process.</p>
                </div>
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="bg-slate-50 rounded-xl border border-slate-200 p-8 text-center">
          <Plane className="w-12 h-12 text-slate-400 mx-auto mb-4" />
          <h3 className="font-medium text-slate-700">No Active Visa</h3>
          <p className="text-sm text-slate-500 mt-1">Contact us to apply for a visa</p>
        </div>
      )}

      {/* History */}
      <div>
        <h2 className="text-lg font-medium text-slate-800 mb-4">Visa History</h2>
        <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-100">
          {visaData.history.map((item) => (
            <div key={item.id} className="p-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className={`p-2 rounded-lg ${item.status === 'completed' ? 'bg-emerald-100' : 'bg-slate-100'}`}>
                  {item.status === 'completed' ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                  ) : (
                    <Clock className="w-4 h-4 text-slate-500" />
                  )}
                </div>
                <div>
                  <p className="font-medium text-slate-800">{item.type}</p>
                  <p className="text-sm text-slate-500">{item.period}</p>
                </div>
              </div>
              <span className={`px-2 py-1 text-xs rounded-full ${item.status === 'completed' ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-600'}`}>
                {item.status}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Documents */}
      <div>
        <h2 className="text-lg font-medium text-slate-800 mb-4">Immigration Documents</h2>
        <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-100">
          {visaData.documents.map((doc) => (
            <div key={doc.id} className="p-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-blue-100 rounded-lg">
                  <FileText className="w-4 h-4 text-blue-600" />
                </div>
                <div>
                  <p className="font-medium text-slate-800">{doc.name}</p>
                  <p className="text-sm text-slate-500">Uploaded {doc.uploadDate}</p>
                </div>
              </div>
              <button className="p-2 text-slate-500 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition-colors">
                <Download className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
