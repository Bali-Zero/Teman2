import type { CalculatorField, CalculatorResult } from "./Calculator";
import { cn } from "@/lib/utils";

type CalculatorValue = number | string | boolean;

type LegacyCalculatorField = CalculatorField & {
  suffix?: string;
};

type LegacyBreakdownItem = {
  label: string;
  amount?: number;
  value?: number;
  format?: CalculatorResult["format"];
  currency?: string;
  description?: string;
  isTotal?: boolean;
  highlight?: boolean;
};

type LegacyCalculatorResult = {
  total?: number;
  breakdown?: LegacyBreakdownItem[];
  currency?: string;
  note?: string;
};

export interface CalculatorRSCProps {
  id?: string;
  title?: string;
  subtitle?: string;
  description?: string;
  fields?: LegacyCalculatorField[];
  calculate?: (values: Record<string, CalculatorValue>) => CalculatorResult[];
  calculateResult?: (
    values: Record<string, CalculatorValue>,
  ) => CalculatorResult[] | LegacyCalculatorResult;
  showBreakdown?: boolean;
  disclaimer?: string;
  className?: string;
}

function defaultFieldValue(field: LegacyCalculatorField): CalculatorValue {
  if (field.defaultValue !== undefined) {
    return field.defaultValue;
  }

  if (field.type === "number" || field.type === "slider") {
    return field.min ?? 0;
  }

  if (field.type === "checkbox") {
    return false;
  }

  if (field.type === "select" && field.options?.length) {
    return field.options[0].value;
  }

  return "";
}

function buildDefaultValues(
  fields: LegacyCalculatorField[],
): Record<string, CalculatorValue> {
  return fields.reduce<Record<string, CalculatorValue>>((values, field) => {
    values[field.id] = defaultFieldValue(field);
    return values;
  }, {});
}

function inferFormat(
  value: number,
  currency?: string,
): CalculatorResult["format"] {
  if (currency) {
    return "currency";
  }

  return Math.abs(value) <= 1 ? "percentage" : "number";
}

function normalizeLegacyResult(
  result: CalculatorResult[] | LegacyCalculatorResult,
): CalculatorResult[] {
  if (Array.isArray(result)) {
    return result;
  }

  const currency = result.currency;
  const breakdown = (result.breakdown ?? []).map((item) => {
    const value = item.amount ?? item.value ?? 0;

    return {
      label: item.label,
      value,
      format: item.format ?? inferFormat(value, item.currency ?? currency),
      currency: item.currency ?? currency,
      description: item.description,
      isTotal: item.isTotal,
      highlight: item.highlight,
    } satisfies CalculatorResult;
  });

  if (typeof result.total === "number") {
    breakdown.push({
      label: "Estimated total",
      value: result.total,
      format: inferFormat(result.total, currency),
      currency,
      description: result.note,
      isTotal: true,
      highlight: true,
    });
  }

  return breakdown;
}

function calculateStaticResults({
  fields,
  calculate,
  calculateResult,
}: {
  fields: LegacyCalculatorField[];
  calculate?: CalculatorRSCProps["calculate"];
  calculateResult?: CalculatorRSCProps["calculateResult"];
}): CalculatorResult[] {
  const defaultValues = buildDefaultValues(fields);

  try {
    if (calculateResult) {
      return normalizeLegacyResult(calculateResult(defaultValues));
    }

    if (calculate) {
      return calculate(defaultValues);
    }
  } catch {
    return [];
  }

  return [];
}

function formatValue(result: CalculatorResult): string {
  if (result.format === "currency") {
    const currency = result.currency ?? "IDR";

    if (currency === "IDR") {
      return `Rp ${result.value.toLocaleString("id-ID")}`;
    }

    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency,
    }).format(result.value);
  }

  if (result.format === "percentage") {
    return `${result.value.toFixed(1)}%`;
  }

  return result.value.toLocaleString("en-US");
}

function formatFieldValue(field: LegacyCalculatorField): string {
  const value = defaultFieldValue(field);
  const unit = field.unit ?? field.suffix;

  if (typeof value === "number") {
    return `${value.toLocaleString("en-US")}${unit ? ` ${unit}` : ""}`;
  }

  if (typeof value === "boolean") {
    return value ? "Yes" : "No";
  }

  const optionLabel = field.options?.find(
    (option) => option.value === value,
  )?.label;

  return optionLabel ?? value;
}

export function CalculatorRSC({
  title = "Calculator",
  subtitle,
  description,
  fields = [],
  calculate,
  calculateResult,
  showBreakdown = true,
  disclaimer,
  className,
}: CalculatorRSCProps) {
  const results = calculateStaticResults({
    fields,
    calculate,
    calculateResult,
  });
  const totalResult = results.find((result) => result.isTotal);
  const breakdownResults = results.filter((result) => !result.isTotal);

  return (
    <div
      className={cn(
        "bg-black/40 rounded-2xl border border-white/10 overflow-hidden",
        className,
      )}
      data-mdx-calculator-rsc="true"
    >
      <div className="px-6 py-4 border-b border-white/10 bg-gradient-to-r from-emerald-500/10 to-transparent">
        <h3 className="font-serif text-xl font-semibold text-white">{title}</h3>
        {(subtitle || description) && (
          <p className="text-white/60 text-sm mt-1">
            {subtitle ?? description}
          </p>
        )}
      </div>

      <div className="p-6 grid md:grid-cols-2 gap-8">
        <div>
          <h4 className="text-sm font-medium text-white/60 uppercase tracking-wider mb-4">
            Default Inputs
          </h4>
          {fields.length > 0 ? (
            <dl className="space-y-3">
              {fields.map((field) => (
                <div
                  key={field.id}
                  className="flex items-center justify-between gap-4 rounded-lg bg-white/5 px-3 py-2"
                >
                  <dt className="text-white/70 text-sm">{field.label}</dt>
                  <dd className="text-white font-mono text-sm text-right">
                    {formatFieldValue(field)}
                  </dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="text-white/50 text-sm">No calculator inputs found.</p>
          )}
        </div>

        <div>
          <h4 className="text-sm font-medium text-white/60 uppercase tracking-wider mb-4">
            Estimated Result
          </h4>
          {results.length > 0 ? (
            <div className="space-y-4">
              {showBreakdown && breakdownResults.length > 0 && (
                <div className="space-y-2">
                  {breakdownResults.map((result) => (
                    <div
                      key={result.label}
                      className={cn(
                        "flex items-center justify-between gap-4 rounded-lg px-3 py-2",
                        result.highlight ? "bg-amber-500/10" : "bg-white/5",
                      )}
                    >
                      <span className="text-white/70 text-sm">
                        {result.label}
                      </span>
                      <span
                        className={cn(
                          "font-mono text-sm text-right",
                          result.highlight ? "text-amber-400" : "text-white",
                        )}
                      >
                        {formatValue(result)}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {totalResult && (
                <div className="p-4 rounded-xl bg-gradient-to-r from-emerald-500/20 to-teal-500/20 border border-emerald-500/30">
                  <div className="flex items-center justify-between gap-4">
                    <div>
                      <p className="text-emerald-400/80 text-sm">
                        {totalResult.label}
                      </p>
                      {totalResult.description && (
                        <p className="text-white/50 text-xs mt-0.5">
                          {totalResult.description}
                        </p>
                      )}
                    </div>
                    <p className="text-2xl font-bold text-emerald-400 font-mono text-right">
                      {formatValue(totalResult)}
                    </p>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <p className="text-white/50 text-sm">No calculator result found.</p>
          )}
        </div>
      </div>

      {disclaimer && (
        <div className="px-6 pb-6">
          <p className="border-t border-white/10 pt-4 text-xs text-white/40">
            {disclaimer}
          </p>
        </div>
      )}
    </div>
  );
}
