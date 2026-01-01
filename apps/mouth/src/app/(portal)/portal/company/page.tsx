'use client';

import React, { useState, useEffect } from 'react';
import {
  Building2,
  Calendar,
  MapPin,
  Users,
  AlertCircle,
  CheckCircle2,
  ChevronDown,
} from 'lucide-react';
import { api } from '@/lib/api';
import type { PortalCompany } from '@/lib/api/portal/portal.types';

export default function CompanyPage() {
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [companies, setCompanies] = useState<PortalCompany[]>([]);
  const [selectedCompany, setSelectedCompany] = useState<PortalCompany | null>(null);
  const [showSelector, setShowSelector] = useState(false);

  useEffect(() => {
    const loadCompanies = async () => {
      try {
        setIsLoading(true);
        setError(null);
        const data = await api.portal.getCompanies();
        setCompanies(data);
        const primary = data.find(c => c.isPrimary) || data[0];
        setSelectedCompany(primary || null);
      } catch (err) {
        console.error('Failed to load companies:', err);
        setError('Unable to load company information. Please try again.');
      } finally {
        setIsLoading(false);
      }
    };

    loadCompanies();
  }, []);

  const handleSelectCompany = async (company: PortalCompany) => {
    setSelectedCompany(company);
    setShowSelector(false);
    if (!company.isPrimary) {
      try {
        await api.portal.setPrimaryCompany(company.id);
      } catch (err) {
        console.error('Failed to set primary company:', err);
      }
    }
  };

  if (isLoading) {
    return (
      <div className="animate-pulse space-y-6">
        <div className="h-8 bg-[#1A1D24] rounded w-64"></div>
        <div className="h-48 bg-[#1A1D24] rounded-xl"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <AlertCircle className="w-12 h-12 text-red-400 mb-4" />
        <h2 className="text-lg font-medium text-[#E6E7EB] mb-2">Unable to load company information</h2>
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

  if (!selectedCompany) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <Building2 className="w-12 h-12 text-[#9AA0AE] mb-4" />
        <h2 className="text-lg font-medium text-[#E6E7EB] mb-2">No companies linked</h2>
        <p className="text-[#9AA0AE]">Contact your account manager to link your companies.</p>
      </div>
    );
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
      case 'expiring': return 'bg-amber-500/10 text-amber-400 border-amber-500/20';
      case 'expired': return 'bg-red-500/10 text-red-400 border-red-500/20';
      case 'upcoming': return 'bg-blue-500/10 text-blue-400 border-blue-500/20';
      case 'overdue': return 'bg-red-500/10 text-red-400 border-red-500/20';
      case 'completed': return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
      default: return 'bg-[#1A1D24] text-[#9AA0AE] border-white/10';
    }
  };

  return (
    <div className="space-y-8">
      {/* Header with Company Selector */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-[#E6E7EB]">Company & Licenses</h1>
          <p className="text-[#9AA0AE] mt-1">Your company information and compliance</p>
        </div>

        {companies.length > 1 && (
          <div className="relative">
            <button
              onClick={() => setShowSelector(!showSelector)}
              className="flex items-center gap-2 px-4 py-2 bg-[#1A1D24] border border-white/10 rounded-lg hover:bg-[#1F2329] transition-colors"
            >
              <Building2 className="w-4 h-4 text-[#9AA0AE]" />
              <span className="text-sm font-medium text-[#E6E7EB]">{selectedCompany.name}</span>
              <ChevronDown className="w-4 h-4 text-[#9AA0AE]" />
            </button>
            {showSelector && (
              <div className="absolute right-0 mt-2 w-64 bg-[#1A1D24] border border-white/10 rounded-lg shadow-lg z-10">
                {companies.map((company) => (
                  <button
                    key={company.id}
                    onClick={() => handleSelectCompany(company)}
                    className={`w-full px-4 py-3 text-left hover:bg-[#1F2329] first:rounded-t-lg last:rounded-b-lg ${
                      company.id === selectedCompany.id ? 'bg-[#4FD1C5]/10' : ''
                    }`}
                  >
                    <p className="font-medium text-[#E6E7EB]">{company.name}</p>
                    <p className="text-sm text-[#9AA0AE]">{company.type}</p>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Company Info Card */}
      <div className="bg-[#1A1D24] rounded-xl border border-white/5 overflow-hidden">
        <div className="p-6 border-b border-white/5">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-blue-500/10 rounded-xl">
                <Building2 className="w-6 h-6 text-blue-400" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-[#E6E7EB]">{selectedCompany.name}</h2>
                <p className="text-sm text-[#9AA0AE]">{selectedCompany.type}</p>
              </div>
            </div>
            <span className={`px-3 py-1 rounded-full text-sm font-medium border ${getStatusColor(selectedCompany.status)}`}>
              {selectedCompany.status.charAt(0).toUpperCase() + selectedCompany.status.slice(1)}
            </span>
          </div>
        </div>

        <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="flex items-start gap-3">
            <MapPin className="w-5 h-5 text-[#9AA0AE] mt-0.5" />
            <div>
              <p className="text-sm text-[#9AA0AE] mb-1">Address</p>
              <p className="text-[#E6E7EB]">{selectedCompany.address}</p>
            </div>
          </div>
          <div className="flex items-start gap-3">
            <Users className="w-5 h-5 text-[#9AA0AE] mt-0.5" />
            <div>
              <p className="text-sm text-[#9AA0AE] mb-1">Directors</p>
              <p className="text-[#E6E7EB]">{selectedCompany.directors.join(', ')}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Licenses */}
      {selectedCompany.licenses.length > 0 && (
        <div>
          <h2 className="text-lg font-medium text-[#E6E7EB] mb-4">Licenses & Permits</h2>
          <div className="bg-[#1A1D24] rounded-xl border border-white/5 divide-y divide-white/5">
            {selectedCompany.licenses.map((license) => (
              <div key={license.id} className="p-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className={`p-2 rounded-lg ${license.status === 'active' ? 'bg-emerald-500/10' : license.status === 'expiring' ? 'bg-amber-500/10' : 'bg-red-500/10'}`}>
                    {license.status === 'active' ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    ) : (
                      <AlertCircle className="w-4 h-4 text-amber-400" />
                    )}
                  </div>
                  <div>
                    <p className="font-medium text-[#E6E7EB]">{license.name}</p>
                    <p className="text-sm text-[#9AA0AE]">Expires: {license.expiryDate}</p>
                  </div>
                </div>
                <div className="text-right">
                  <span className={`px-2 py-1 text-xs rounded-full border ${getStatusColor(license.status)}`}>
                    {license.status}
                  </span>
                  {license.daysRemaining && license.daysRemaining <= 60 && (
                    <p className="text-sm text-amber-400 mt-1">{license.daysRemaining} days left</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Empty state for licenses */}
      {selectedCompany.licenses.length === 0 && (
        <div>
          <h2 className="text-lg font-medium text-[#E6E7EB] mb-4">Licenses & Permits</h2>
          <div className="bg-[#1A1D24] rounded-xl border border-white/5 p-8 text-center">
            <CheckCircle2 className="w-12 h-12 text-[#9AA0AE] mx-auto mb-4" />
            <h3 className="font-medium text-[#E6E7EB]">No Licenses</h3>
            <p className="text-sm text-[#9AA0AE] mt-1">Your licenses will appear here</p>
          </div>
        </div>
      )}

      {/* Compliance Calendar */}
      {selectedCompany.compliance.length > 0 && (
        <div>
          <h2 className="text-lg font-medium text-[#E6E7EB] mb-4">Compliance Calendar</h2>
          <div className="bg-[#1A1D24] rounded-xl border border-white/5 divide-y divide-white/5">
            {selectedCompany.compliance.map((item) => (
              <div key={item.id} className="p-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-violet-500/10 rounded-lg">
                    <Calendar className="w-4 h-4 text-violet-400" />
                  </div>
                  <div>
                    <p className="font-medium text-[#E6E7EB]">{item.name}</p>
                    <p className="text-sm text-[#9AA0AE]">Due: {item.dueDate}</p>
                  </div>
                </div>
                <span className={`px-2 py-1 text-xs rounded-full border ${getStatusColor(item.status)}`}>
                  {item.status}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Empty state for compliance */}
      {selectedCompany.compliance.length === 0 && (
        <div>
          <h2 className="text-lg font-medium text-[#E6E7EB] mb-4">Compliance Calendar</h2>
          <div className="bg-[#1A1D24] rounded-xl border border-white/5 p-8 text-center">
            <Calendar className="w-12 h-12 text-[#9AA0AE] mx-auto mb-4" />
            <h3 className="font-medium text-[#E6E7EB]">No Compliance Items</h3>
            <p className="text-sm text-[#9AA0AE] mt-1">Your compliance calendar will appear here</p>
          </div>
        </div>
      )}
    </div>
  );
}
