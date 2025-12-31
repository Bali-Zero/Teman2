'use client';

import React, { useState, useEffect } from 'react';
import {
  Building2,
  FileCheck,
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
        // Select primary company or first one
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
    // Optionally set as primary on backend
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
        <div className="h-8 bg-slate-200 rounded w-64"></div>
        <div className="h-48 bg-slate-200 rounded-xl"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <AlertCircle className="w-12 h-12 text-red-500 mb-4" />
        <h2 className="text-lg font-medium text-slate-800 mb-2">Unable to load company information</h2>
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

  if (!selectedCompany) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <Building2 className="w-12 h-12 text-slate-400 mb-4" />
        <h2 className="text-lg font-medium text-slate-800 mb-2">No companies linked</h2>
        <p className="text-slate-500">Contact your account manager to link your companies.</p>
      </div>
    );
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return 'bg-emerald-100 text-emerald-700';
      case 'expiring': return 'bg-amber-100 text-amber-700';
      case 'expired': return 'bg-red-100 text-red-700';
      case 'upcoming': return 'bg-blue-100 text-blue-700';
      case 'overdue': return 'bg-red-100 text-red-700';
      case 'completed': return 'bg-emerald-100 text-emerald-700';
      default: return 'bg-slate-100 text-slate-700';
    }
  };

  return (
    <div className="space-y-8">
      {/* Header with Company Selector */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-800">Company & Licenses</h1>
          <p className="text-slate-500 mt-1">Manage your company information and compliance</p>
        </div>

        {companies.length > 1 && (
          <div className="relative">
            <button
              onClick={() => setShowSelector(!showSelector)}
              className="flex items-center gap-2 px-4 py-2 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"
            >
              <Building2 className="w-4 h-4 text-slate-500" />
              <span className="text-sm font-medium text-slate-700">{selectedCompany.name}</span>
              <ChevronDown className="w-4 h-4 text-slate-400" />
            </button>
            {showSelector && (
              <div className="absolute right-0 mt-2 w-64 bg-white border border-slate-200 rounded-lg shadow-lg z-10">
                {companies.map((company) => (
                  <button
                    key={company.id}
                    onClick={() => handleSelectCompany(company)}
                    className={`w-full px-4 py-3 text-left hover:bg-slate-50 first:rounded-t-lg last:rounded-b-lg ${
                      company.id === selectedCompany.id ? 'bg-emerald-50' : ''
                    }`}
                  >
                    <p className="font-medium text-slate-800">{company.name}</p>
                    <p className="text-sm text-slate-500">{company.type}</p>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Company Info Card */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="p-6 border-b border-slate-100">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-blue-100 rounded-xl">
                <Building2 className="w-6 h-6 text-blue-600" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-slate-800">{selectedCompany.name}</h2>
                <p className="text-sm text-slate-500">{selectedCompany.type}</p>
              </div>
            </div>
            <span className={`px-3 py-1 rounded-full text-sm font-medium ${getStatusColor(selectedCompany.status)}`}>
              {selectedCompany.status.charAt(0).toUpperCase() + selectedCompany.status.slice(1)}
            </span>
          </div>
        </div>

        <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="flex items-start gap-3">
            <MapPin className="w-5 h-5 text-slate-400 mt-0.5" />
            <div>
              <p className="text-sm text-slate-500 mb-1">Address</p>
              <p className="text-slate-800">{selectedCompany.address}</p>
            </div>
          </div>
          <div className="flex items-start gap-3">
            <Users className="w-5 h-5 text-slate-400 mt-0.5" />
            <div>
              <p className="text-sm text-slate-500 mb-1">Directors</p>
              <p className="text-slate-800">{selectedCompany.directors.join(', ')}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Licenses */}
      <div>
        <h2 className="text-lg font-medium text-slate-800 mb-4">Licenses & Permits</h2>
        <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-100">
          {selectedCompany.licenses.map((license) => (
            <div key={license.id} className="p-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className={`p-2 rounded-lg ${license.status === 'active' ? 'bg-emerald-100' : license.status === 'expiring' ? 'bg-amber-100' : 'bg-red-100'}`}>
                  {license.status === 'active' ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                  ) : (
                    <AlertCircle className="w-4 h-4 text-amber-600" />
                  )}
                </div>
                <div>
                  <p className="font-medium text-slate-800">{license.name}</p>
                  <p className="text-sm text-slate-500">Expires: {license.expiryDate}</p>
                </div>
              </div>
              <div className="text-right">
                <span className={`px-2 py-1 text-xs rounded-full ${getStatusColor(license.status)}`}>
                  {license.status}
                </span>
                {license.daysRemaining && license.daysRemaining <= 60 && (
                  <p className="text-sm text-amber-600 mt-1">{license.daysRemaining} days left</p>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Compliance Calendar */}
      <div>
        <h2 className="text-lg font-medium text-slate-800 mb-4">Compliance Calendar</h2>
        <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-100">
          {selectedCompany.compliance.map((item) => (
            <div key={item.id} className="p-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-slate-100 rounded-lg">
                  <Calendar className="w-4 h-4 text-slate-600" />
                </div>
                <div>
                  <p className="font-medium text-slate-800">{item.name}</p>
                  <p className="text-sm text-slate-500">Due: {item.dueDate}</p>
                </div>
              </div>
              <span className={`px-2 py-1 text-xs rounded-full ${getStatusColor(item.status)}`}>
                {item.status}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
