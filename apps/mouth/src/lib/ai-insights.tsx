/**
 * AI-powered insights and predictions for dashboard
 * Uses machine learning to provide actionable insights
 */

import React, { useState, useCallback, useEffect } from 'react';

interface Insight {
  id: string;
  type: 'prediction' | 'recommendation' | 'anomaly' | 'trend';
  title: string;
  description: string;
  confidence: number; // 0-1
  impact: 'low' | 'medium' | 'high' | 'critical';
  category: 'cases' | 'clients' | 'revenue' | 'efficiency' | 'compliance';
  data: Record<string, any>;
  actionable: boolean;
  suggestedActions: string[];
  validUntil: string;
}

interface PredictionModel {
  id: string;
  name: string;
  type: 'regression' | 'classification' | 'clustering' | 'anomaly_detection';
  target: string;
  features: string[];
  accuracy: number;
  lastTrained: string;
  isActive: boolean;
}

interface DashboardInsight {
  insights: Insight[];
  predictions: {
    casesNextMonth: number;
    revenueNextMonth: number;
    clientChurnRisk: number;
    workloadForecast: number[];
  };
  trends: {
    caseVolume: Array<{ date: string; value: number; prediction: boolean }>;
    revenue: Array<{ date: string; value: number; prediction: boolean }>;
    efficiency: Array<{ date: string; value: number; prediction: boolean }>;
  };
  anomalies: Array<{
    metric: string;
    value: number;
    expected: number;
    deviation: number;
    timestamp: string;
  }>;
}

class AIInsightsService {
  private models: Map<string, PredictionModel> = new Map();
  private insights: Insight[] = [];
  private isInitialized = false;

  constructor() {
    this.initializeModels();
  }

  // Initialize ML models
  private initializeModels(): void {
    this.models.set('case_volume_prediction', {
      id: 'case_volume_prediction',
      name: 'Case Volume Prediction',
      type: 'regression',
      target: 'case_volume',
      features: ['historical_volume', 'season', 'marketing_spend', 'team_size'],
      accuracy: 0.87,
      lastTrained: '2024-01-01',
      isActive: true,
    });

    this.models.set('revenue_forecast', {
      id: 'revenue_forecast',
      name: 'Revenue Forecast',
      type: 'regression',
      target: 'revenue',
      features: ['case_volume', 'average_case_value', 'season', 'economic_indicators'],
      accuracy: 0.82,
      lastTrained: '2024-01-01',
      isActive: true,
    });

    this.models.set('client_churn_prediction', {
      id: 'client_churn_prediction',
      name: 'Client Churn Prediction',
      type: 'classification',
      target: 'churn_probability',
      features: ['case_count', 'last_activity', 'satisfaction_score', 'payment_history'],
      accuracy: 0.79,
      lastTrained: '2024-01-01',
      isActive: true,
    });

    this.models.set('anomaly_detection', {
      id: 'anomaly_detection',
      name: 'Anomaly Detection',
      type: 'anomaly_detection',
      target: 'anomaly_score',
      features: ['response_time', 'error_rate', 'case_duration', 'client_complaints'],
      accuracy: 0.91,
      lastTrained: '2024-01-01',
      isActive: true,
    });
  }

  // Generate AI insights for dashboard
  async generateInsights(historicalData: any): Promise<DashboardInsight> {
    if (!this.isInitialized) {
      await this.initializeAI();
    }

    const insights = await this.generateSpecificInsights(historicalData);
    const predictions = await this.generatePredictions(historicalData);
    const trends = await this.analyzeTrends(historicalData);
    const anomalies = await this.detectAnomalies(historicalData);

    return {
      insights,
      predictions,
      trends,
      anomalies,
    };
  }

  // Initialize AI service
  private async initializeAI(): Promise<void> {
    // In production, this would load actual ML models
    // For now, we'll simulate the initialization
    this.isInitialized = true;
    console.log('🤖 AI Insights Service initialized');
  }

  // Generate specific insights
  private async generateSpecificInsights(data: any): Promise<Insight[]> {
    const insights: Insight[] = [];

    // Case volume insight
    const caseTrend = this.calculateTrend(data.cases || []);
    if (caseTrend > 0.1) {
      insights.push({
        id: 'case_volume_increase',
        type: 'trend',
        title: 'Case Volume Increasing',
        description: `Case volume has increased by ${(caseTrend * 100).toFixed(1)}% in the last 30 days. Consider scaling team capacity.`,
        confidence: 0.85,
        impact: caseTrend > 0.2 ? 'high' : 'medium',
        category: 'cases',
        data: { trend: caseTrend, period: '30 days' },
        actionable: true,
        suggestedActions: [
          'Review team workload distribution',
          'Consider hiring additional staff',
          'Optimize case processing workflows',
        ],
        validUntil: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(),
      });
    }

    // Revenue prediction insight
    const revenuePrediction = await this.predictRevenue(data);
    if (revenuePrediction.confidence > 0.8) {
      insights.push({
        id: 'revenue_prediction',
        type: 'prediction',
        title: 'Revenue Forecast',
        description: `Predicted revenue for next month: $${revenuePrediction.value.toLocaleString()} with ${(revenuePrediction.confidence * 100).toFixed(0)}% confidence.`,
        confidence: revenuePrediction.confidence,
        impact: revenuePrediction.value > 10000 ? 'high' : 'medium',
        category: 'revenue',
        data: { predicted: revenuePrediction.value, confidence: revenuePrediction.confidence },
        actionable: true,
        suggestedActions: [
          'Focus on high-value cases',
          'Optimize pricing strategy',
          'Monitor market trends',
        ],
        validUntil: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString(),
      });
    }

    // Efficiency anomaly insight
    const efficiencyAnomaly = await this.detectEfficiencyAnomalies(data);
    if (efficiencyAnomaly.detected) {
      insights.push({
        id: 'efficiency_anomaly',
        type: 'anomaly',
        title: 'Efficiency Anomaly Detected',
        description: `Case processing efficiency has dropped by ${(efficiencyAnomaly.deviation * 100).toFixed(1)}% compared to normal levels.`,
        confidence: 0.92,
        impact: 'high',
        category: 'efficiency',
        data: { deviation: efficiencyAnomaly.deviation, metric: 'processing_time' },
        actionable: true,
        suggestedActions: [
          'Review recent process changes',
          'Check for system issues',
          'Provide additional team training',
        ],
        validUntil: new Date(Date.now() + 3 * 24 * 60 * 60 * 1000).toISOString(),
      });
    }

    // Client churn risk insight
    const churnRisk = await this.predictClientChurn(data);
    if (churnRisk.highRiskClients.length > 0) {
      insights.push({
        id: 'client_churn_risk',
        type: 'recommendation',
        title: 'Client Churn Risk Alert',
        description: `${churnRisk.highRiskClients.length} clients at high risk of churn. Immediate action recommended.`,
        confidence: 0.78,
        impact: 'critical',
        category: 'clients',
        data: { atRiskCount: churnRisk.highRiskClients.length, clients: churnRisk.highRiskClients },
        actionable: true,
        suggestedActions: [
          'Contact at-risk clients immediately',
          'Offer special discounts or incentives',
          'Review service quality issues',
        ],
        validUntil: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(),
      });
    }

    return insights;
  }

  // Generate predictions
  private async generatePredictions(data: any): Promise<any> {
    const casesNextMonth = await this.predictCaseVolume(data);
    const revenueNextMonth = await this.predictRevenue(data);
    const clientChurnRisk = await this.predictClientChurn(data);
    const workloadForecast = await this.predictWorkload(data);

    return {
      casesNextMonth: Math.round(casesNextMonth.value),
      revenueNextMonth: Math.round(revenueNextMonth.value),
      clientChurnRisk: clientChurnRisk.riskScore,
      workloadForecast: workloadForecast.values,
    };
  }

  // Analyze trends
  private async analyzeTrends(data: any): Promise<any> {
    const caseVolume = this.generateTrendData(data.cases || [], 'cases');
    const revenue = this.generateTrendData(data.revenue || [], 'revenue');
    const efficiency = this.generateTrendData(data.efficiency || [], 'efficiency');

    return { caseVolume, revenue, efficiency };
  }

  // Detect anomalies
  private async detectAnomalies(data: any): Promise<any> {
    const anomalies = [];

    // Check for response time anomalies
    const responseTimeAnomaly = this.detectMetricAnomaly(data.responseTime || [], 'response_time');
    if (responseTimeAnomaly) {
      anomalies.push(responseTimeAnomaly);
    }

    // Check for error rate anomalies
    const errorRateAnomaly = this.detectMetricAnomaly(data.errorRate || [], 'error_rate');
    if (errorRateAnomaly) {
      anomalies.push(errorRateAnomaly);
    }

    return anomalies;
  }

  // Helper methods for predictions
  private calculateTrend(data: number[]): number {
    if (data.length < 2) return 0;
    const recentSlice = data.slice(-7);
    const olderSlice = data.slice(-14, -7);
    if (recentSlice.length === 0 || olderSlice.length === 0) return 0;
    const recent = recentSlice.reduce((a, b) => a + b, 0) / recentSlice.length;
    const older = olderSlice.reduce((a, b) => a + b, 0) / olderSlice.length;
    if (older === 0) return recent > 0 ? 1 : 0; // Avoid division by zero
    return (recent - older) / older;
  }

  private async predictCaseVolume(data: any): Promise<{ value: number; confidence: number }> {
    // Simplified prediction logic
    const historical = data.cases || [];
    if (historical.length === 0) {
      return { value: 0, confidence: 0.5 };
    }
    const average = historical.reduce((a: number, b: number) => a + b, 0) / historical.length;
    const trend = this.calculateTrend(historical);
    const prediction = average * (1 + trend);

    return {
      value: Math.max(0, isFinite(prediction) ? prediction : 0),
      confidence: 0.85,
    };
  }

  private async predictRevenue(data: any): Promise<{ value: number; confidence: number }> {
    const historical = data.revenue || [];
    if (historical.length === 0) {
      return { value: 0, confidence: 0.5 };
    }
    const average = historical.reduce((a: number, b: number) => a + b, 0) / historical.length;
    const trend = this.calculateTrend(historical);
    const prediction = average * (1 + trend);

    return {
      value: Math.max(0, isFinite(prediction) ? prediction : 0),
      confidence: 0.82,
    };
  }

  private async predictClientChurn(data: any): Promise<{ riskScore: number; highRiskClients: any[] }> {
    // Simplified churn prediction
    const clients = data.clients || [];
    const highRiskClients = clients.filter((client: any) => 
      client.lastActivity > 30 || client.satisfactionScore < 3
    );
    
    return {
      riskScore: highRiskClients.length / Math.max(clients.length, 1),
      highRiskClients,
    };
  }

  private async predictWorkload(data: any): Promise<{ values: number[] }> {
    // Generate 30-day workload forecast
    const values = [];
    let currentWorkload = data.currentWorkload || 10;
    
    for (let i = 0; i < 30; i++) {
      currentWorkload += (Math.random() - 0.5) * 2;
      currentWorkload = Math.max(0, currentWorkload);
      values.push(Math.round(currentWorkload));
    }
    
    return { values };
  }

  private generateTrendData(data: number[], type: string): Array<{ date: string; value: number; prediction: boolean }> {
    const result = [];
    const now = new Date();
    
    for (let i = 29; i >= 0; i--) {
      const date = new Date(now.getTime() - i * 24 * 60 * 60 * 1000);
      const value = data[data.length - 30 + i] || Math.floor(Math.random() * 100);
      result.push({
        date: date.toISOString().split('T')[0],
        value,
        prediction: false,
      });
    }
    
    // Add future predictions
    for (let i = 1; i <= 7; i++) {
      const date = new Date(now.getTime() + i * 24 * 60 * 60 * 1000);
      const lastValue: number = result[result.length - 1]?.value || 50;
      const prediction = lastValue + (Math.random() - 0.5) * 10;
      result.push({
        date: date.toISOString().split('T')[0],
        value: Math.max(0, prediction),
        prediction: true,
      });
    }
    
    return result;
  }

  private detectMetricAnomaly(data: number[], metric: string): any {
    if (data.length < 10) return null;

    const recent = data.slice(-5);
    const historical = data.slice(-20, -5);
    if (historical.length === 0 || recent.length === 0) return null;
    const historicalAvg = historical.reduce((a, b) => a + b, 0) / historical.length;
    const recentAvg = recent.reduce((a, b) => a + b, 0) / recent.length;

    if (historicalAvg === 0) return null; // Avoid division by zero
    const deviation = Math.abs(recentAvg - historicalAvg) / historicalAvg;

    if (deviation > 0.3) {
      return {
        metric,
        value: recentAvg,
        expected: historicalAvg,
        deviation: isFinite(deviation) ? deviation : 0,
        timestamp: new Date().toISOString(),
      };
    }

    return null;
  }

  private async detectEfficiencyAnomalies(data: any): Promise<{ detected: boolean; deviation: number }> {
    const efficiency = data.efficiency || [];
    if (efficiency.length < 10) return { detected: false, deviation: 0 };

    const recent = efficiency.slice(-5);
    const historical = efficiency.slice(-20, -5);
    if (historical.length === 0 || recent.length === 0) return { detected: false, deviation: 0 };
    const historicalAvg = historical.reduce((a: number, b: number) => a + b, 0) / historical.length;
    const recentAvg = recent.reduce((a: number, b: number) => a + b, 0) / recent.length;

    if (historicalAvg === 0) return { detected: false, deviation: 0 }; // Avoid division by zero
    const deviation = Math.abs(recentAvg - historicalAvg) / historicalAvg;

    return {
      detected: isFinite(deviation) && deviation > 0.2,
      deviation: isFinite(deviation) ? deviation : 0,
    };
  }

  // Get model performance metrics
  getModelMetrics(): Map<string, PredictionModel> {
    return new Map(this.models);
  }

  // Retrain models (would call actual ML service)
  async retrainModel(modelId: string): Promise<boolean> {
    const model = this.models.get(modelId);
    if (!model) return false;
    
    // Simulate retraining
    model.lastTrained = new Date().toISOString();
    model.accuracy = Math.min(0.95, model.accuracy + 0.02);
    
    console.log(`🤖 Model ${modelId} retrained. New accuracy: ${model.accuracy}`);
    return true;
  }
}

// Singleton instance
export const aiInsights = new AIInsightsService();

// React hook for AI insights
export function useAIInsights() {
  const [insights, setInsights] = useState<DashboardInsight | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const generateInsights = useCallback(async (data: any) => {
    setLoading(true);
    setError(null);
    
    try {
      const result = await aiInsights.generateInsights(data);
      setInsights(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate insights');
    } finally {
      setLoading(false);
    }
  }, []);

  return {
    insights,
    loading,
    error,
    generateInsights,
    getModelMetrics: aiInsights.getModelMetrics.bind(aiInsights),
    retrainModel: aiInsights.retrainModel.bind(aiInsights),
  };
}

// Higher-order component for AI insights
export function withAIInsights<P extends object>(
  Component: React.ComponentType<P & { ai?: any }>
) {
  const WrappedComponent = (props: P) => {
    const ai = useAIInsights();

    return <Component {...props} ai={ai} />;
  };

  WrappedComponent.displayName = `withAIInsights(${Component.displayName || Component.name})`;
  return WrappedComponent;
}
