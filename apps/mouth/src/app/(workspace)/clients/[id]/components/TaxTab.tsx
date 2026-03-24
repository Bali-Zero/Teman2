'use client';

import React, { useState, useRef, useCallback, memo } from 'react';
import {
  User,
  Building2,
  Calendar,
  FileText,
  Upload,
  X,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import { fileToBase64 } from '@/lib/utils';

// ============================================
// TAX TYPES AND INTERFACES
// ============================================
type TaxYear = 2024 | 2025 | 2026;
type TaxSection = 'personal' | 'annual' | 'monthly' | 'lkpm';

interface TaxDocument {
  id?: string;
  file?: File;
  fileName?: string;
  uploadedAt?: string;
  status: 'pending' | 'uploaded' | 'verified';
}

interface PersonalTaxData {
  npwp: string;
  annualIncome: string;
  documents: {
    form1770?: TaxDocument;
    buktiPotong?: TaxDocument;
    sptTahunan?: TaxDocument;
  };
}

interface AnnualCompanyTaxData {
  companyId: string;
  companyName: string;
  npwp: string;
  documents: {
    sptTahunan?: TaxDocument;
    laporanKeuangan?: TaxDocument;
    buktiPembayaran?: TaxDocument;
    formTaxAmnesty?: TaxDocument;
  };
}

interface MonthlyReportData {
  month: string;
  year: number;
  pph21: TaxDocument;
  pph23: TaxDocument;
  ppn: TaxDocument;
  pph25: TaxDocument;
}

interface LKPMQuarterData {
  quarter: 1 | 2 | 3 | 4;
  year: number;
  realization: string;
  documents: {
    lkpmReport?: TaxDocument;
    investmentRealization?: TaxDocument;
    employeeReport?: TaxDocument;
    productionReport?: TaxDocument;
  };
}

// ============================================
// FILE UPLOAD COMPONENT
// ============================================
interface FileUploadFieldProps {
  id: string;
  label: string;
  subLabel?: string;
  file?: File;
  error?: string;
  accept?: string;
  onChange: (file: File | undefined) => void;
  onClear: () => void;
  extraButton?: React.ReactNode;
  className?: string;
}

const FileUploadField = memo(function FileUploadField({
  id,
  label,
  subLabel,
  file,
  error,
  accept = '.pdf,.jpg,.jpeg,.png',
  onChange,
  onClear,
  extraButton,
  className = '',
}: FileUploadFieldProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const selectedFile = e.target.files?.[0];
      if (selectedFile) {
        // Validate file size (10MB max)
        if (selectedFile.size > 10 * 1024 * 1024) {
          toast.error('File too large', {
            description: 'Maximum size is 10MB',
          });
          return;
        }
        // Validate file type
        const allowedTypes = ['application/pdf', 'image/jpeg', 'image/jpg', 'image/png'];
        if (!allowedTypes.includes(selectedFile.type)) {
          toast.error('Invalid file type', {
            description: 'Please upload PDF, JPG, or PNG',
          });
          return;
        }
        onChange(selectedFile);
      }
    },
    [onChange]
  );

  const handleClear = useCallback(() => {
    onClear();
    if (inputRef.current) {
      inputRef.current.value = '';
    }
  }, [onClear]);

  return (
    <div className={className}>
      <label className="block text-xs font-medium mb-1.5">
        {label}
        {subLabel && <span className="text-[var(--bz-text-2)]"> {subLabel}</span>}
      </label>
      <div className="flex items-center gap-2">
        <input
          ref={inputRef}
          type="file"
          id={id}
          accept={accept}
          onChange={handleChange}
          className="hidden"
        />
        <label
          htmlFor={id}
          className={`
            flex-1 px-3 py-2 rounded-lg border border-dashed cursor-pointer transition-colors text-sm truncate
            ${
              error
                ? 'border-red-500 bg-red-500/10 text-red-500'
                : 'border-[var(--bz-border)] bg-[var(--bz-surface)] hover:border-[var(--accent)]'
            }
          `}
        >
          {file ? file.name : `Upload ${label}`}
        </label>
        {file && (
          <>
            {extraButton}
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-8 w-8 p-0 text-red-500 hover:text-red-600"
              onClick={handleClear}
            >
              <X className="w-4 h-4" />
            </Button>
          </>
        )}
      </div>
      {error && <p className="text-xs text-red-500 mt-1">{error}</p>}
    </div>
  );
});

// ============================================
// TAX TAB COMPONENT
// ============================================
export function TaxTab({ clientId, formatDate }: { clientId: number; formatDate: (d: string) => string }) {
  const [selectedYear, setSelectedYear] = useState<TaxYear>(2025);
  const [activeSection, setActiveSection] = useState<TaxSection>('personal');
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Calculate deadlines based on selected year
  const deadlines = {
    personalTax: new Date(selectedYear, 2, 31), // March 31
    annualCompany: new Date(selectedYear, 3, 30), // April 30
  };

  const handleFileUpload = async (section: TaxSection, docType: string, file: File) => {
    setIsUploading(true);
    setUploadError(null);
    try {
      const base64 = await fileToBase64(file);
      await api.post(`/api/crm/clients/${clientId}/tax-documents`, {
        file: base64,
        file_name: file.name,
        document_type: docType,
        section: section,
        year: selectedYear,
      });
      toast.success(`${docType} uploaded successfully`);
    } catch (err) {
      setUploadError(`Failed to upload ${docType}: ${(err as Error).message}`);
      toast.error('Upload failed', { description: (err as Error).message });
    } finally {
      setIsUploading(false);
    }
  };

  // Year selector buttons
  const YearSelector = () => (
    <div className="flex items-center gap-2">
      {[2024, 2025, 2026].map((year) => (
        <Button
          key={year}
          variant={selectedYear === year ? 'default' : 'outline'}
          size="sm"
          onClick={() => setSelectedYear(year as TaxYear)}
        >
          {year}
        </Button>
      ))}
    </div>
  );

  // File upload workspace component
  const UploadWorkspace = ({
    section,
    title,
    description,
    docTypes,
  }: {
    section: TaxSection;
    title: string;
    description: string;
    docTypes: { key: string; label: string; hint: string }[];
  }) => (
    <div className="bg-[var(--bz-surface)] border border-[var(--bz-border)] rounded-xl p-4 space-y-4">
      <div>
        <h4 className="font-semibold text-[var(--bz-text-1)]">{title}</h4>
        <p className="text-xs text-[var(--bz-text-2)]">{description}</p>
      </div>

      <div className="space-y-3">
        {docTypes.map((doc) => (
          <div
            key={doc.key}
            className="border border-dashed border-[var(--bz-border)] rounded-lg p-3"
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium">{doc.label}</span>
              <span className="text-xs text-[var(--bz-text-2)]">{doc.hint}</span>
            </div>
            <div className="flex items-center gap-2">
              <input
                type="file"
                id={`${section}-${doc.key}`}
                accept=".pdf,.jpg,.jpeg,.png"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) handleFileUpload(section, doc.key, file);
                }}
                disabled={isUploading}
              />
              <label
                htmlFor={`${section}-${doc.key}`}
                className="flex-1 px-3 py-2 rounded-lg border border-[var(--bz-border)] bg-[var(--bz-base)] cursor-pointer hover:border-[var(--accent)] transition-colors text-sm truncate"
              >
                {isUploading ? 'Uploading...' : `Select ${doc.label} file`}
              </label>
            </div>
          </div>
        ))}
      </div>

      {uploadError && <p className="text-xs text-red-500">{uploadError}</p>}
    </div>
  );

  // Side panel for upload workspace
  const SideWorkspace = () => {
    const configs = {
      personal: {
        title: 'Personal Tax Documents',
        description: `Deadline: March 31, ${selectedYear}`,
        docTypes: [
          { key: 'form1770', label: 'Form 1770', hint: 'Annual Tax Return' },
          { key: 'buktiPotong', label: 'Bukti Potong', hint: 'Withholding Tax Slips' },
          { key: 'sptTahunan', label: 'SPT Tahunan', hint: 'Annual Tax Report' },
          { key: 'bupot1721', label: 'Bukti Potong 1721', hint: 'Employment Income' },
          { key: 'bupot1721A1', label: 'Bukti Potong 1721-A1', hint: 'Annual Tax Slip' },
        ],
      },
      annual: {
        title: 'Annual Company Tax',
        description: `Deadline: April 30, ${selectedYear}`,
        docTypes: [
          { key: 'sptTahunanBadan', label: 'SPT Tahunan Badan', hint: 'Corporate Annual Tax Return' },
          { key: 'laporanKeuangan', label: 'Laporan Keuangan', hint: 'Financial Statements' },
          { key: 'buktiPembayaran', label: 'Bukti Pembayaran', hint: 'Payment Receipts' },
          { key: 'formTaxAmnesty', label: 'Form Tax Amnesty', hint: 'If applicable' },
          { key: 'neraca', label: 'Neraca', hint: 'Balance Sheet' },
          { key: 'labaRugi', label: 'Laba Rugi', hint: 'Profit & Loss' },
        ],
      },
      monthly: {
        title: 'Monthly Company Reports',
        description: 'Due monthly by the 20th',
        docTypes: [
          { key: 'pph21', label: 'PPH 21', hint: 'Employee Income Tax' },
          { key: 'pph23', label: 'PPH 23', hint: 'Services Withholding Tax' },
          { key: 'ppn', label: 'PPN', hint: 'VAT Return' },
          { key: 'pph25', label: 'PPH 25', hint: 'Installment Tax' },
          { key: 'pph4ayat2', label: 'PPH 4(2)', hint: 'Final Income Tax' },
          { key: 'pph26', label: 'PPH 26', hint: 'Foreign Tax' },
        ],
      },
      lkpm: {
        title: 'LKPM Quarterly Reports',
        description: 'Investment Activity Reports',
        docTypes: [
          { key: 'lkpmReport', label: 'LKPM Report', hint: 'Main Investment Report' },
          { key: 'realisasiInvestasi', label: 'Realisasi Investasi', hint: 'Investment Realization' },
          { key: 'laporanTenagaKerja', label: 'Laporan Tenaga Kerja', hint: 'Employment Report' },
          { key: 'laporanProduksi', label: 'Laporan Produksi', hint: 'Production Report' },
          { key: 'rawMaterial', label: 'Raw Material Usage', hint: 'Import/Local breakdown' },
          { key: 'exportValue', label: 'Export Value', hint: 'Export realization' },
        ],
      },
    };

    const config = configs[activeSection];
    return <UploadWorkspace section={activeSection} {...config} />;
  };

  // Tax cards
  const TaxCard = ({
    title,
    subtitle,
    deadline,
    icon: Icon,
    color,
    section,
    onClick,
  }: {
    title: string;
    subtitle: string;
    deadline: Date;
    icon: React.ComponentType<{ className?: string; size?: number }>;
    color: string;
    section: TaxSection;
    onClick: () => void;
  }) => {
    const isOverdue = new Date() > deadline;
    const daysUntil = Math.ceil(
      (deadline.getTime() - new Date().getTime()) / (1000 * 60 * 60 * 24)
    );

    return (
      <div
        onClick={onClick}
        className={`rounded-xl border border-[var(--bz-border)] bg-[var(--bz-surface)] p-5 cursor-pointer transition-all hover:border-[var(--accent)] ${
          activeSection === section ? 'ring-2 ring-[var(--bz-accent)]' : ''
        }`}
      >
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className={`w-12 h-12 rounded-xl ${color} flex items-center justify-center`}>
              <Icon className="w-6 h-6 text-white" />
            </div>
            <div>
              <h4 className="font-semibold text-[var(--bz-text-1)]">{title}</h4>
              <p className="text-xs text-[var(--bz-text-2)]">{subtitle}</p>
            </div>
          </div>
          {isOverdue ? (
            <span className="px-2 py-1 rounded-full bg-red-500/20 text-red-400 text-xs font-medium">
              Overdue
            </span>
          ) : daysUntil <= 30 ? (
            <span className="px-2 py-1 rounded-full bg-yellow-500/20 text-yellow-400 text-xs font-medium">
              {daysUntil}d left
            </span>
          ) : (
            <span className="px-2 py-1 rounded-full bg-emerald-500/20 text-emerald-400 text-xs font-medium">
              On Track
            </span>
          )}
        </div>

        <div className="mt-4 pt-4 border-t border-[var(--bz-border)]">
          <div className="flex items-center justify-between">
            <span className="text-sm text-[var(--bz-text-2)]">Deadline</span>
            <span
              className={`text-sm font-medium ${isOverdue ? 'text-red-400' : daysUntil <= 30 ? 'text-yellow-400' : 'text-emerald-400'}`}
            >
              {formatDate(deadline.toISOString())}
            </span>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {/* Header with year selector */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-[var(--bz-text-1)]">Tax Overview</h3>
          <p className="text-sm text-[var(--bz-text-2)]">Manage tax obligations and filings</p>
        </div>
        <YearSelector />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main content - Tax cards */}
        <div className="lg:col-span-2 space-y-4">
          <TaxCard
            title="Personal Tax"
            subtitle="Individual SPT Tahunan"
            deadline={deadlines.personalTax}
            icon={User}
            color="bg-gradient-to-br from-emerald-500 to-teal-600"
            section="personal"
            onClick={() => setActiveSection('personal')}
          />

          <TaxCard
            title="Annual Company Tax"
            subtitle="Corporate SPT Tahunan Badan"
            deadline={deadlines.annualCompany}
            icon={Building2}
            color="bg-gradient-to-br from-blue-500 to-cyan-600"
            section="annual"
            onClick={() => setActiveSection('annual')}
          />

          <TaxCard
            title="Monthly Reports"
            subtitle="PPH 21, 23, PPN, PPH 25"
            deadline={new Date(selectedYear, 11, 20)} // Dec 20 as example
            icon={Calendar}
            color="bg-gradient-to-br from-purple-500 to-pink-600"
            section="monthly"
            onClick={() => setActiveSection('monthly')}
          />

          {/* LKPM with 4 quarters */}
          <div className="rounded-xl border border-[var(--bz-border)] bg-[var(--bz-surface)] p-5">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-orange-500 to-red-600 flex items-center justify-center">
                  <FileText className="w-6 h-6 text-white" />
                </div>
                <div>
                  <h4 className="font-semibold text-[var(--bz-text-1)]">LKPM</h4>
                  <p className="text-xs text-[var(--bz-text-2)]">
                    Laporan Kegiatan Penanaman Modal
                  </p>
                </div>
              </div>
              <Button
                variant={activeSection === 'lkpm' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setActiveSection('lkpm')}
              >
                Manage
              </Button>
            </div>

            <div className="grid grid-cols-4 gap-2">
              {[1, 2, 3, 4].map((q) => (
                <div
                  key={q}
                  className={`text-center p-3 rounded-lg border ${
                    activeSection === 'lkpm'
                      ? 'border-[var(--accent)] bg-[var(--bz-accent)]/10'
                      : 'border-[var(--bz-border)]'
                  }`}
                >
                  <p className="text-lg font-bold">Q{q}</p>
                  <p className="text-xs text-[var(--bz-text-2)]">
                    {q === 1 && 'Jan-Mar'}
                    {q === 2 && 'Apr-Jun'}
                    {q === 3 && 'Jul-Sep'}
                    {q === 4 && 'Oct-Dec'}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Side workspace for uploads */}
        <div className="lg:col-span-1">
          <SideWorkspace />
        </div>
      </div>
    </div>
  );
}
