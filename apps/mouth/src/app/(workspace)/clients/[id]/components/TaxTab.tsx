'use client';

import React, { useState, useRef, useCallback, memo } from 'react';
import { User, Building2, Calendar, FileText, Upload, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import { fileToBase64 } from '@/lib/utils';

// ============================================
// TAX TYPES AND INTERFACES
// ============================================
type TaxYear = number;
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
// YEAR SELECTOR — module-scope to prevent remount
// ============================================
interface YearSelectorProps {
  selectedYear: TaxYear;
  onYearChange: (year: TaxYear) => void;
}

const YearSelector = memo(function YearSelector({ selectedYear, onYearChange }: YearSelectorProps) {
  const currentYear = new Date().getFullYear();
  const years = Array.from({ length: 5 }, (_, i) => currentYear - i);

  return (
    <div className="flex items-center gap-2">
      <span className="text-sm text-[var(--bz-text-2)]">Year:</span>
      <div className="flex gap-1">
        {years.map((year) => (
          <Button
            key={year}
            variant={selectedYear === year ? 'default' : 'outline'}
            size="sm"
            className="h-8 px-3 text-xs"
            onClick={() => onYearChange(year)}
          >
            {year}
          </Button>
        ))}
      </div>
    </div>
  );
});

// ============================================
// TAX CARD — module-scope to prevent remount
// ============================================
interface TaxCardProps {
  title: string;
  subtitle: string;
  deadline: Date;
  icon: React.ElementType;
  color: string;
  section: TaxSection;
  activeSection: TaxSection;
  onClick: () => void;
}

const TaxCard = memo(function TaxCard({
  title,
  subtitle,
  deadline,
  icon: Icon,
  color,
  section,
  activeSection,
  onClick,
}: TaxCardProps) {
  const isActive = activeSection === section;
  const now = new Date();
  const daysUntilDeadline = Math.ceil((deadline.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
  const isOverdue = daysUntilDeadline < 0;
  const isUrgent = daysUntilDeadline >= 0 && daysUntilDeadline <= 30;

  return (
    <div
      className={`rounded-xl border bg-[var(--bz-surface)] p-5 cursor-pointer transition-all ${
        isActive
          ? 'border-[var(--accent)] ring-1 ring-[var(--accent)]/30'
          : 'border-[var(--bz-border)] hover:border-[var(--bz-border)]/80'
      }`}
      onClick={onClick}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={`w-12 h-12 rounded-xl ${color} flex items-center justify-center`}>
            <Icon className="w-6 h-6 text-white" />
          </div>
          <div>
            <h4 className="font-semibold text-[var(--bz-text-1)]">{title}</h4>
            <p className="text-xs text-[var(--bz-text-2)]">{subtitle}</p>
          </div>
        </div>
        <div className="text-right">
          <p className="text-xs text-[var(--bz-text-2)]">Deadline</p>
          <p
            className={`text-sm font-medium ${
              isOverdue ? 'text-red-500' : isUrgent ? 'text-yellow-500' : 'text-[var(--bz-text-1)]'
            }`}
          >
            {deadline.toLocaleDateString('en-GB', {
              day: 'numeric',
              month: 'short',
              year: 'numeric',
            })}
          </p>
          <div className="flex justify-end mt-1">
            <span
              className={`text-[10px] px-1.5 py-0.5 rounded-full font-semibold ${
                isOverdue
                  ? 'bg-red-500/15 text-red-400'
                  : isUrgent
                    ? 'bg-yellow-500/15 text-yellow-400'
                    : 'bg-[rgba(255,255,255,0.04)] text-[var(--bz-text-2)]'
              }`}
            >
              {isOverdue
                ? `${Math.abs(daysUntilDeadline)}d overdue`
                : daysUntilDeadline === 0
                  ? 'today'
                  : daysUntilDeadline <= 365
                    ? `⏰ ${daysUntilDeadline}d left`
                    : `${Math.floor(daysUntilDeadline / 30)}mo left`}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
});

// ============================================
// SIDE WORKSPACE — module-scope to prevent remount
// ============================================
interface SideWorkspaceProps {
  activeSection: TaxSection;
  selectedYear: TaxYear;
  isUploading: boolean;
  uploadError: string | null;
  onFileUpload: (section: TaxSection, docType: string, file: File) => void;
}

const DOC_TYPES: Record<TaxSection, { key: string; label: string }[]> = {
  personal: [
    { key: 'form1770', label: 'Form 1770' },
    { key: 'buktiPotong', label: 'Bukti Potong' },
    { key: 'sptTahunan', label: 'SPT Tahunan' },
  ],
  annual: [
    { key: 'sptTahunan', label: 'SPT Tahunan Badan' },
    { key: 'laporanKeuangan', label: 'Laporan Keuangan' },
    { key: 'buktiPembayaran', label: 'Bukti Pembayaran' },
    { key: 'formTaxAmnesty', label: 'Form Tax Amnesty' },
  ],
  monthly: [
    { key: 'pph21', label: 'PPH 21' },
    { key: 'pph23', label: 'PPH 23' },
    { key: 'ppn', label: 'PPN' },
    { key: 'pph25', label: 'PPH 25' },
  ],
  lkpm: [
    { key: 'lkpmReport', label: 'LKPM Report' },
    { key: 'investmentRealization', label: 'Investment Realization' },
    { key: 'employeeReport', label: 'Employee Report' },
    { key: 'productionReport', label: 'Production Report' },
  ],
};

const SECTION_TITLES: Record<TaxSection, string> = {
  personal: 'Personal Tax Documents',
  annual: 'Annual Company Documents',
  monthly: 'Monthly Report Documents',
  lkpm: 'LKPM Documents',
};

const SideWorkspace = memo(function SideWorkspace({
  activeSection,
  selectedYear,
  isUploading,
  uploadError,
  onFileUpload,
}: SideWorkspaceProps) {
  const [files, setFiles] = useState<Record<string, File | undefined>>({});

  const docTypes = DOC_TYPES[activeSection];
  const title = SECTION_TITLES[activeSection];

  const handleFileChange = useCallback((docKey: string, file: File | undefined) => {
    setFiles((prev) => ({ ...prev, [docKey]: file }));
  }, []);

  const handleFileClear = useCallback((docKey: string) => {
    setFiles((prev) => ({ ...prev, [docKey]: undefined }));
  }, []);

  const handleUpload = useCallback(
    (docKey: string) => {
      const file = files[docKey];
      if (!file) return;
      onFileUpload(activeSection, docKey, file);
      setFiles((prev) => ({ ...prev, [docKey]: undefined }));
    },
    [files, activeSection, onFileUpload]
  );

  return (
    <div className="rounded-xl border border-[var(--bz-border)] bg-[var(--bz-surface)] p-5 sticky top-4">
      <h4 className="font-semibold text-[var(--bz-text-1)] mb-1">{title}</h4>
      <p className="text-xs text-[var(--bz-text-2)] mb-4">Tax year {selectedYear}</p>

      {uploadError && (
        <div className="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-xs text-red-400">
          {uploadError}
        </div>
      )}

      <div className="space-y-3">
        {docTypes.map(({ key, label }) => (
          <FileUploadField
            key={key}
            id={`tax-doc-${activeSection}-${key}`}
            label={label}
            file={files[key]}
            onChange={(file) => handleFileChange(key, file)}
            onClear={() => handleFileClear(key)}
            extraButton={
              files[key] ? (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-8 px-2 text-xs gap-1"
                  onClick={() => handleUpload(key)}
                  disabled={isUploading}
                >
                  <Upload className="w-3 h-3" />
                  {isUploading ? '...' : 'Upload'}
                </Button>
              ) : undefined
            }
          />
        ))}
      </div>
    </div>
  );
});

// ============================================
// TAX TAB COMPONENT
// ============================================
export function TaxTab({
  clientId,
  formatDate,
}: {
  clientId: number;
  formatDate: (d: string) => string;
}) {
  const [selectedYear, setSelectedYear] = useState<TaxYear>(new Date().getFullYear());
  const [activeSection, setActiveSection] = useState<TaxSection>('personal');
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Calculate deadlines based on selected year
  const deadlines = {
    personalTax: new Date(selectedYear, 2, 31), // March 31
    annualCompany: new Date(selectedYear, 3, 30), // April 30
  };

  const handleFileUpload = useCallback(
    async (section: TaxSection, docType: string, file: File) => {
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
    },
    [clientId, selectedYear]
  );

  return (
    <div className="space-y-6">
      {/* Header with year selector */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-[var(--bz-text-1)]">Tax Overview</h3>
          <p className="text-sm text-[var(--bz-text-2)]">Manage tax obligations and filings</p>
        </div>
        <YearSelector selectedYear={selectedYear} onYearChange={setSelectedYear} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main content - Tax cards */}
        <div className="lg:col-span-2 space-y-4">
          <TaxCard
            title="Personal Tax"
            aria-label="Personal Tax"
            subtitle="Individual SPT Tahunan"
            deadline={deadlines.personalTax}
            icon={User}
            color="bg-gradient-to-br from-emerald-500 to-teal-600"
            section="personal"
            activeSection={activeSection}
            onClick={() => setActiveSection('personal')}
          />

          <TaxCard
            title="Annual Company Tax"
            aria-label="Annual Company Tax"
            subtitle="Corporate SPT Tahunan Badan"
            deadline={deadlines.annualCompany}
            icon={Building2}
            color="bg-gradient-to-br from-blue-500 to-cyan-600"
            section="annual"
            activeSection={activeSection}
            onClick={() => setActiveSection('annual')}
          />

          <TaxCard
            title="Monthly Reports"
            aria-label="Monthly Reports"
            subtitle="PPH 21, 23, PPN, PPH 25"
            deadline={new Date(selectedYear, 11, 20)} // Dec 20 as example
            icon={Calendar}
            color="bg-gradient-to-br from-purple-500 to-pink-600"
            section="monthly"
            activeSection={activeSection}
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
          <SideWorkspace
            activeSection={activeSection}
            selectedYear={selectedYear}
            isUploading={isUploading}
            uploadError={uploadError}
            onFileUpload={handleFileUpload}
          />
        </div>
      </div>
    </div>
  );
}
