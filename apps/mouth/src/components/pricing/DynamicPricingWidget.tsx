/**
 * Dynamic Pricing Calculator Widget
 * Calculates comprehensive pricing for business scenarios
 */

'use client';

import { useState } from 'react';
import { Calculator, Loader2, TrendingUp, Clock } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import type { PricingResult, CostItem } from '@/lib/api/zantara-sdk/types';
import { ZantaraSDK } from '@/lib/api/zantara-sdk';

export interface DynamicPricingWidgetProps {
  sdk: ZantaraSDK;
  onCalculate?: (result: PricingResult) => void;
}

export function DynamicPricingWidget({ sdk, onCalculate }: DynamicPricingWidgetProps) {
  const [scenario, setScenario] = useState('');
  const [result, setResult] = useState<PricingResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCalculate = async () => {
    if (!scenario.trim()) {
      setError('Please enter a scenario');
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const pricingResult = await sdk.calculatePricing(scenario.trim());
      setResult(pricingResult);
      onCalculate?.(pricingResult);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to calculate pricing');
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('id-ID', {
      style: 'currency',
      currency: 'IDR',
      minimumFractionDigits: 0,
    }).format(amount);
  };

  const getCategoryColor = (category: string) => {
    const colors: Record<string, string> = {
      Legal: 'bg-blue-100 text-blue-800',
      Licensing: 'bg-green-100 text-green-800',
      Tax: 'bg-yellow-100 text-yellow-800',
      Visa: 'bg-purple-100 text-purple-800',
      Property: 'bg-orange-100 text-orange-800',
      'Service Fees': 'bg-gray-100 text-gray-800',
    };
    return colors[category] || 'bg-gray-100 text-gray-800';
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Calculator className="h-6 w-6" />
        <h2 className="text-2xl font-bold">Dynamic Pricing Calculator</h2>
      </div>

      {/* Input Section */}
      <div className="space-y-2">
        <label className="text-sm font-medium">Business Scenario</label>
        <div className="flex gap-2">
          <Input
            value={scenario}
            onChange={(e) => setScenario(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleCalculate();
              }
            }}
            placeholder="e.g., PT PMA Restaurant in Seminyak, 3 foreign directors"
            disabled={loading}
            className="flex-1"
          />
          <Button onClick={handleCalculate} disabled={loading || !scenario.trim()}>
            {loading ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Calculating...
              </>
            ) : (
              'Calculate'
            )}
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">
          Describe your business scenario to get a comprehensive cost breakdown
        </p>
      </div>

      {/* Error Display */}
      {error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-sm text-red-800">{error}</p>
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="space-y-4">
          {/* Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
              <div className="flex items-center gap-2 text-blue-800 mb-2">
                <TrendingUp className="h-5 w-5" />
                <span className="text-sm font-medium">Setup Cost</span>
              </div>
              <div className="text-2xl font-bold text-blue-900">
                {formatCurrency(result.total_setup_cost)}
              </div>
              <p className="text-xs text-blue-700 mt-1">One-time investment</p>
            </div>

            {result.total_recurring_cost > 0 && (
              <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
                <div className="flex items-center gap-2 text-green-800 mb-2">
                  <Clock className="h-5 w-5" />
                  <span className="text-sm font-medium">Annual Cost</span>
                </div>
                <div className="text-2xl font-bold text-green-900">
                  {formatCurrency(result.total_recurring_cost)}
                </div>
                <p className="text-xs text-green-700 mt-1">Recurring expenses</p>
              </div>
            )}

            <div className="p-4 bg-purple-50 border border-purple-200 rounded-lg">
              <div className="flex items-center gap-2 text-purple-800 mb-2">
                <Clock className="h-5 w-5" />
                <span className="text-sm font-medium">Timeline</span>
              </div>
              <div className="text-lg font-bold text-purple-900">
                {result.timeline_estimate}
              </div>
              <p className="text-xs text-purple-700 mt-1">Estimated duration</p>
            </div>
          </div>

          {/* Confidence Score */}
          <div className="p-3 bg-muted rounded-lg">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Confidence Score</span>
              <span className="text-sm font-semibold">
                {(result.confidence * 100).toFixed(0)}%
              </span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2 mt-2">
              <div
                className="bg-blue-600 h-2 rounded-full transition-all"
                style={{ width: `${result.confidence * 100}%` }}
              />
            </div>
          </div>

          {/* Breakdown by Category */}
          <div className="space-y-2">
            <h3 className="text-lg font-semibold">Breakdown by Category</h3>
            <div className="space-y-2">
              {Object.entries(result.breakdown_by_category)
                .sort(([, a], [, b]) => b - a)
                .map(([category, amount]) => {
                  const percentage =
                    result.total_setup_cost > 0
                      ? ((amount / result.total_setup_cost) * 100).toFixed(1)
                      : '0';
                  return (
                    <div key={category} className="flex items-center justify-between p-3 bg-muted rounded-lg">
                      <div className="flex items-center gap-2">
                        <span className={`px-2 py-1 text-xs rounded ${getCategoryColor(category)}`}>
                          {category}
                        </span>
                        <span className="text-xs text-muted-foreground">{percentage}%</span>
                      </div>
                      <span className="font-semibold">{formatCurrency(amount)}</span>
                    </div>
                  );
                })}
            </div>
          </div>

          {/* Detailed Cost Items */}
          <div className="space-y-2">
            <h3 className="text-lg font-semibold">Detailed Cost Items</h3>
            <div className="space-y-2 max-h-96 overflow-y-auto">
              {result.cost_items.map((item, index) => (
                <div
                  key={index}
                  className="p-3 border rounded-lg hover:bg-muted transition-colors"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className={`px-2 py-1 text-xs rounded ${getCategoryColor(item.category)}`}>
                          {item.category}
                        </span>
                        {item.is_recurring && (
                          <span className="px-2 py-1 text-xs bg-yellow-100 text-yellow-800 rounded">
                            Recurring
                          </span>
                        )}
                      </div>
                      <p className="text-sm mt-1">{item.description}</p>
                      {item.source_oracle && (
                        <p className="text-xs text-muted-foreground mt-1">
                          Source: {item.source_oracle}
                        </p>
                      )}
                    </div>
                    <div className="text-right">
                      <div className="font-semibold">{formatCurrency(item.amount)}</div>
                      {item.frequency && (
                        <div className="text-xs text-muted-foreground">{item.frequency}</div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Key Assumptions */}
          {result.key_assumptions.length > 0 && (
            <div className="space-y-2">
              <h3 className="text-lg font-semibold">Key Assumptions</h3>
              <ul className="list-disc list-inside space-y-1 text-sm text-muted-foreground">
                {result.key_assumptions.map((assumption, index) => (
                  <li key={index}>{assumption}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}







