import React, { useState, useEffect, useCallback } from 'react';
import { getProducts, getRecommendations, getRecommendationExplanation, getAiExplanation, postRecommendationDecision, getRecommendationDecisions, getProductAffinity, getCustomerSegments, getSegmentPromotions, getCampaignReports, getCampaignOutcomes, postCampaignOutcome, uploadRetailerData, getImportBatches, getBatchStatus, previewBatch, commitBatch, getAnalyticsReadiness, runAnalytics, getAnalyticsResults } from './api';
import { Package, TrendingUp, Search, Store, LayoutDashboard, Loader2, AlertCircle, BarChart2, PieChart as PieChartIcon, Activity, Lightbulb, HelpCircle, X, ChevronDown, ChevronUp, Sparkles, RefreshCw, Upload, Layers, CheckCircle2, AlertTriangle, History, BarChart as BarChartIcon } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell, ComposedChart, Line } from 'recharts';

const COLORS = ['#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', '#f43f5e', '#ec4899', '#64748b'];

const App = () => {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [storeId, setStoreId] = useState('CA_1');
  const [searchItem, setSearchItem] = useState('');
  
  const [products, setProducts] = useState([]);
  const [recommendations, setRecommendations] = useState([]);
  
  const [loadingProducts, setLoadingProducts] = useState(true);
  const [errorProducts, setErrorProducts] = useState(null);
  
  const [loadingRecs, setLoadingRecs] = useState(true);
  const [errorRecs, setErrorRecs] = useState(null);

  // Explanation modal state
  const [explanationModal, setExplanationModal] = useState(null);   // null = closed
  const [explanationData, setExplanationData] = useState(null);
  const [explanationLoading, setExplanationLoading] = useState(false);
  const [explanationError, setExplanationError] = useState(null);
  const [expandedLimitations, setExpandedLimitations] = useState(false);
  // AI tab state (lazy — only fetched when user clicks "Generate")
  const [activeModalTab, setActiveModalTab] = useState('rule'); // 'rule' | 'ai'
  const [aiData, setAiData] = useState(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState(null);

  // Manager decision state
  const [decisionLoading, setDecisionLoading] = useState(false);
  const [decisionError, setDecisionError] = useState(null);
  const [decisionNotes, setDecisionNotes] = useState('');

  const handleDecision = async (itemId, storeId, action) => {
    setDecisionLoading(true);
    setDecisionError(null);
    try {
      const res = await postRecommendationDecision(itemId, storeId, action, decisionNotes);
      fetchData();
      if (explanationModal && explanationModal.itemId === itemId && explanationModal.storeId === storeId) {
        const expData = await getRecommendationExplanation(itemId, storeId);
        setExplanationData(expData);
      }
      setDecisionNotes('');
    } catch (err) {
      const msg = err?.response?.data?.detail || err?.message || 'Failed to record decision.';
      setDecisionError(msg);
    } finally {
      setDecisionLoading(false);
    }
  };

  const [totalProducts, setTotalProducts] = useState(0);
  const [totalRecs, setTotalRecs] = useState(0);

  const fetchData = async () => {
    setLoadingProducts(true);
    setErrorProducts(null);
    setLoadingRecs(true);
    setErrorRecs(null);

    try {
      const prodData = await getProducts(20, storeId, searchItem);
      setProducts(prodData.results || []);
      setTotalProducts(prodData.total_matching || 0);
    } catch (err) {
      setErrorProducts(err.message || 'Failed to fetch products');
      setProducts([]);
    } finally {
      setLoadingProducts(false);
    }

    try {
      const recData = await getRecommendations(20, storeId, searchItem);
      setRecommendations(recData.results || []);
      setTotalRecs(recData.total_matching || 0);
    } catch (err) {
      setErrorRecs(err.message || 'Failed to fetch recommendations');
      setRecommendations([]);
    } finally {
      setLoadingRecs(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [storeId]); // Re-fetch on storeId change

  const handleSearch = (e) => {
    e.preventDefault();
    fetchData();
  };

  // -------------------------------------------------------------
  // Data Calculations for Dashboard
  // -------------------------------------------------------------
  const avgInventory = products.length > 0 
    ? Math.round(products.reduce((acc, p) => acc + (p.simulated_inventory_units || 0), 0) / products.length) 
    : 0;
  const lowStockCount = products.filter(p => (p.simulated_coverage_days || 0) < 14).length;

  const promos = recommendations.filter(r => (r.selected_candidate_discount_pct || 0) > 0);
  const promoCount = promos.length;
  const noPromoCount = recommendations.length - promoCount;
  const avgDiscount = promos.length > 0
    ? (promos.reduce((acc, r) => acc + (r.selected_candidate_discount_pct || 0), 0) / promos.length).toFixed(1)
    : 0;

  // Chart 1: Demand/Sales (Top 10 products by average daily units)
  const demandData = [...products]
    .sort((a, b) => (b.average_daily_units || 0) - (a.average_daily_units || 0))
    .slice(0, 10)
    .map(p => ({
      name: p.item_id.replace('FOODS_1_', ''),
      demand: parseFloat((p.average_daily_units || 0).toFixed(2))
    }));

  // Chart 2: Promotion Distribution (Pie Chart)
  const discountCounts = {};
  recommendations.forEach(r => {
    const pct = r.selected_candidate_discount_pct || 0;
    const label = pct === 0 ? 'No Promo' : `${pct}% Off`;
    discountCounts[label] = (discountCounts[label] || 0) + 1;
  });
  const promoDistributionData = Object.keys(discountCounts).map(key => ({
    name: key,
    value: discountCounts[key]
  })).sort((a, b) => b.value - a.value);

  // Chart 3: Inventory Levels & Coverage (Composed Chart)
  const inventoryData = [...products]
    .sort((a, b) => (b.simulated_inventory_units || 0) - (a.simulated_inventory_units || 0))
    .slice(0, 10)
    .map(p => ({
      name: p.item_id.replace('FOODS_1_', ''),
      stock: p.simulated_inventory_units || 0,
      coverage: parseFloat((p.simulated_coverage_days || 0).toFixed(1))
    }));

  // Product affinity state
  const [affinityData, setAffinityData] = useState(null);
  const [affinityLoading, setAffinityLoading] = useState(false);
  const [affinityError, setAffinityError] = useState(null);

  // Customer segments state
  const [segments, setSegments] = useState([]);
  const [segmentPromos, setSegmentPromos] = useState([]);
  const [loadingSegments, setLoadingSegments] = useState(false);
  const [errorSegments, setErrorSegments] = useState(null);

  // Campaign reports state
  const [campaignReports, setCampaignReports] = useState(null);
  const [campaignOutcomesData, setCampaignOutcomesData] = useState(null);
  const [loadingCampaignReports, setLoadingCampaignReports] = useState(false);
  const [errorCampaignReports, setErrorCampaignReports] = useState(null);

  // Outcome form state
  const [outcomeItemId, setOutcomeItemId] = useState('FOODS_1_001');
  const [outcomeStoreIdForm, setOutcomeStoreIdForm] = useState('CA_1');
  const [outcomeRedemptions, setOutcomeRedemptions] = useState(100);
  const [outcomeSalesLift, setOutcomeSalesLift] = useState(15.0);
  const [outcomeRevenueGain, setOutcomeRevenueGain] = useState(1000.0);
  const [outcomePeriod, setOutcomePeriod] = useState('2026-Q3 Weekend Promo');
  const [outcomeDataSource, setOutcomeDataSource] = useState('SYNTHETIC_DEMO_DATA');
  const [outcomeSubmitting, setOutcomeSubmitting] = useState(false);
  const [outcomeError, setOutcomeError] = useState(null);
  const [outcomeSuccess, setOutcomeSuccess] = useState(null);

  useEffect(() => {
    if (activeTab === 'segments') {
      setLoadingSegments(true);
      setErrorSegments(null);
      Promise.all([
        getCustomerSegments(),
        getSegmentPromotions()
      ])
        .then(([segRes, promoRes]) => {
          setSegments(segRes.segments || []);
          setSegmentPromos(promoRes.promotions || []);
        })
        .catch(err => {
          setErrorSegments(err?.message || 'Failed to load customer segments');
        })
        .finally(() => setLoadingSegments(false));
    }
  }, [activeTab]);

  useEffect(() => {
    if (activeTab === 'reports') {
      setLoadingCampaignReports(true);
      setErrorCampaignReports(null);
      Promise.all([
        getCampaignReports(storeId),
        getCampaignOutcomes(storeId)
      ])
        .then(([repRes, outRes]) => {
          setCampaignReports(repRes);
          setCampaignOutcomesData(outRes);
        })
        .catch(err => {
          setErrorCampaignReports(err?.message || 'Failed to load campaign reports');
        })
        .finally(() => setLoadingCampaignReports(false));
    }
  }, [activeTab, storeId]);

  const handleOutcomeSubmit = async (e) => {
    e.preventDefault();
    setOutcomeSubmitting(true);
    setOutcomeError(null);
    setOutcomeSuccess(null);
    try {
      const payload = {
        item_id: outcomeItemId,
        store_id: outcomeStoreIdForm,
        actual_redemptions: parseInt(outcomeRedemptions, 10),
        actual_sales_lift_pct: parseFloat(outcomeSalesLift),
        actual_revenue_gain: parseFloat(outcomeRevenueGain),
        measured_period: outcomePeriod,
        data_source: outcomeDataSource
      };
      await postCampaignOutcome(payload);
      setOutcomeSuccess('Campaign outcome successfully recorded and evaluated.');
      const outRes = await getCampaignOutcomes(storeId);
      setCampaignOutcomesData(outRes);
      const repRes = await getCampaignReports(storeId);
      setCampaignReports(repRes);
    } catch (err) {
      const msg = err?.response?.data?.detail || err?.message || 'Failed to save campaign outcome.';
      setOutcomeError(msg);
    } finally {
      setOutcomeSubmitting(false);
    }
  };

  // Upload wizard & analytics state
  const [uploadRetailerId, setUploadRetailerId] = useState('retailer_alpha');
  const [uploadSubTab, setUploadSubTab] = useState('ingest'); // 'ingest' | 'analytics'
  const [uploadFile, setUploadFile] = useState(null);
  const [uploadLoading, setUploadLoading] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const [currentBatch, setCurrentBatch] = useState(null);
  const [columnMapping, setColumnMapping] = useState({});
  const [previewData, setPreviewData] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState(null);
  const [commitLoading, setCommitLoading] = useState(false);
  const [commitError, setCommitError] = useState(null);
  const [commitResult, setCommitResult] = useState(null);
  const [importBatches, setImportBatches] = useState([]);
  const [batchesLoading, setBatchesLoading] = useState(false);
  const [batchesError, setBatchesError] = useState(null);

  // Analytics state
  const [analyticsReadiness, setAnalyticsReadiness] = useState(null);
  const [readinessLoading, setReadinessLoading] = useState(false);
  const [readinessError, setReadinessError] = useState(null);
  const [analyticsResults, setAnalyticsResults] = useState(null);
  const [analyticsLoading, setAnalyticsLoading] = useState(false);
  const [analyticsError, setAnalyticsError] = useState(null);
  const [runningAnalytics, setRunningAnalytics] = useState(false);

  const canonicalFieldsMap = {
    products: ['item_id', 'product_name', 'category', 'retail_price', 'unit_cost', 'department', 'brand'],
    sales: ['transaction_id', 'date', 'store_id', 'item_id', 'quantity', 'unit_price', 'customer_id', 'discount_amount'],
    inventory: ['store_id', 'item_id', 'date', 'stock_on_hand', 'reorder_point', 'safety_stock'],
    prices: ['store_id', 'item_id', 'effective_date', 'unit_price', 'unit_cost'],
    customers: ['customer_id', 'segment', 'signup_date', 'lifetime_spend'],
    stores: ['store_id', 'store_name', 'region', 'format_type'],
    campaign_outcomes: ['campaign_id', 'item_id', 'store_id', 'start_date', 'end_date', 'discount_pct', 'actual_lift_pct', 'actual_revenue', 'approval_status']
  };

  useEffect(() => {
    if (activeTab === 'upload') {
      fetchImportBatches();
      fetchAnalyticsData();
    }
  }, [activeTab, uploadRetailerId]);

  const fetchImportBatches = async () => {
    setBatchesLoading(true);
    setBatchesError(null);
    try {
      const res = await getImportBatches(uploadRetailerId);
      setImportBatches(res.batches || []);
    } catch (err) {
      setBatchesError(err?.response?.data?.detail || err?.message || 'Failed to load import batches');
      setImportBatches([]);
    } finally {
      setBatchesLoading(false);
    }
  };

  const fetchAnalyticsData = async () => {
    setReadinessLoading(true);
    setReadinessError(null);
    setAnalyticsLoading(true);
    setAnalyticsError(null);
    try {
      const readRes = await getAnalyticsReadiness(uploadRetailerId);
      setAnalyticsReadiness(readRes);
    } catch (err) {
      setReadinessError(err?.response?.data?.detail || err?.message || 'Failed to fetch data readiness');
    } finally {
      setReadinessLoading(false);
    }

    try {
      const res = await getAnalyticsResults(uploadRetailerId);
      setAnalyticsResults(res);
    } catch (err) {
      setAnalyticsError(err?.response?.data?.detail || err?.message || 'Failed to fetch analytics results');
    } finally {
      setAnalyticsLoading(false);
    }
  };

  const handleRunAnalytics = async () => {
    setRunningAnalytics(true);
    setAnalyticsError(null);
    try {
      const res = await runAnalytics(uploadRetailerId);
      setAnalyticsResults(res.analytics);
      fetchAnalyticsData();
    } catch (err) {
      const msg = err?.response?.data?.detail || err?.message || 'Failed to run analytics.';
      setAnalyticsError(msg);
    } finally {
      setRunningAnalytics(false);
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      if (file.size > 50 * 1024 * 1024) {
        setUploadError('File size exceeds maximum allowed limit of 50 MB.');
        return;
      }
      setUploadFile(file);
      setUploadError(null);
    }
  };

  const handleUploadSubmit = async (e) => {
    e.preventDefault();
    if (!uploadFile) {
      setUploadError('Please select a CSV or Excel file.');
      return;
    }
    setUploadLoading(true);
    setUploadError(null);
    try {
      const res = await uploadRetailerData(uploadFile, uploadRetailerId);
      setCurrentBatch(res);
      setColumnMapping(res.inferred_mapping || {});
      setPreviewData(null);
      setCommitResult(null);
    } catch (err) {
      const msg = err?.response?.data?.detail || err?.message || 'Failed to upload file.';
      setUploadError(msg);
    } finally {
      setUploadLoading(false);
    }
  };

  const handlePreview = async () => {
    if (!currentBatch) return;
    setPreviewLoading(true);
    setPreviewError(null);
    try {
      const res = await previewBatch(
        currentBatch.batch_id,
        currentBatch.inferred_dataset_type,
        columnMapping,
        null,
        uploadRetailerId
      );
      setPreviewData(res);
    } catch (err) {
      const msg = err?.response?.data?.detail || err?.message || 'Failed to preview batch.';
      setPreviewError(msg);
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleCommit = async () => {
    if (!currentBatch) return;
    setCommitLoading(true);
    setCommitError(null);
    setCommitResult(null);
    try {
      const res = await commitBatch(
        currentBatch.batch_id,
        currentBatch.inferred_dataset_type,
        columnMapping,
        null,
        uploadRetailerId
      );
      setCommitResult(res);
      fetchImportBatches();
      fetchAnalyticsData();
    } catch (err) {
      const msg = err?.response?.data?.detail || err?.message || 'Failed to commit batch.';
      setCommitError(msg);
    } finally {
      setCommitLoading(false);
    }
  };

  const renderUploadWizard = () => {
    const canonicalFields = canonicalFieldsMap[currentBatch?.inferred_dataset_type || 'products'] || [];

    return (
      <div className="space-y-6 max-w-7xl mx-auto">
        <div className="bg-gradient-to-r from-amber-600 to-amber-700 rounded-2xl p-6 text-white shadow-lg flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
          <div>
            <div className="flex items-center gap-2 text-amber-200 text-xs font-semibold uppercase tracking-wider mb-1">
              <Upload size={16} /> Multi-Retailer Intelligence Platform
            </div>
            <h2 className="text-2xl font-bold tracking-tight">Retailer Ingestion & Analytics Hub</h2>
            <p className="text-amber-100 text-sm mt-1 max-w-2xl">
              Securely ingest retailer data and power tenant-scoped demand forecasting, customer segmentation, inventory alignment, and promotion recommendations.
            </p>
          </div>
          <div className="flex bg-amber-800/60 p-1 rounded-xl border border-amber-500/30">
            <button
              onClick={() => setUploadSubTab('ingest')}
              className={`px-4 py-2 rounded-lg text-xs font-semibold transition-all ${uploadSubTab === 'ingest' ? 'bg-white text-amber-900 shadow-sm' : 'text-amber-100 hover:text-white'}`}
            >
              Data Ingestion Wizard
            </button>
            <button
              onClick={() => { setUploadSubTab('analytics'); fetchAnalyticsData(); }}
              className={`px-4 py-2 rounded-lg text-xs font-semibold transition-all ${uploadSubTab === 'analytics' ? 'bg-white text-amber-900 shadow-sm' : 'text-amber-100 hover:text-white'}`}
            >
              AI/ML Analytics & Readiness
            </button>
          </div>
        </div>

        {uploadSubTab === 'analytics' ? (
          <div className="space-y-6">
            {/* Tenant Context for Analytics */}
            <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
              <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <div>
                  <h3 className="text-lg font-bold text-slate-800 flex items-center gap-2">
                    <BarChartIcon size={20} className="text-amber-600" />
                    Tenant Analytics Workspace ({uploadRetailerId})
                  </h3>
                  <p className="text-sm text-slate-600 mt-1">
                    Run tenant-scoped machine learning models and data-readiness evaluations strictly on committed retailer records.
                  </p>
                </div>
                <div className="flex items-center gap-3 w-full md:w-auto">
                  <input
                    type="text"
                    className="px-3 py-2 rounded-lg border border-slate-200 bg-slate-50 text-xs font-semibold text-slate-800"
                    value={uploadRetailerId}
                    onChange={(e) => setUploadRetailerId(e.target.value.trim())}
                    placeholder="Retailer ID"
                  />
                  <button
                    onClick={handleRunAnalytics}
                    disabled={runningAnalytics}
                    className="px-5 py-2.5 bg-amber-600 hover:bg-amber-700 disabled:bg-slate-300 text-white font-semibold rounded-xl text-xs transition-all flex items-center gap-2 shadow-sm whitespace-nowrap"
                  >
                    {runningAnalytics ? <Loader2 className="animate-spin" size={14} /> : <Sparkles size={14} />}
                    Run Retailer Analytics
                  </button>
                </div>
              </div>
              {analyticsError && (
                <div className="mt-4 p-4 bg-rose-50 border border-rose-200 text-rose-700 rounded-xl text-xs flex items-center gap-2">
                  <AlertTriangle size={16} /> {analyticsError}
                </div>
              )}
            </div>

            {/* Data Readiness Summary Card */}
            <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
              <h4 className="text-base font-bold text-slate-800 mb-3 flex items-center gap-2">
                <Layers size={18} className="text-blue-600" /> Data-Readiness Summary
              </h4>
              {readinessLoading ? (
                <div className="text-center py-6 text-slate-400">Evaluating data readiness...</div>
              ) : analyticsReadiness ? (
                <div className="space-y-4">
                  <div className="flex flex-col md:flex-row items-start md:items-center justify-between bg-slate-50 p-4 rounded-xl border border-slate-200 gap-4">
                    <div>
                      <span className="text-xs font-bold text-slate-500 uppercase">Readiness Status</span>
                      <p className="text-lg font-extrabold capitalize text-slate-800 mt-0.5">{analyticsReadiness.readiness_status}</p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {Object.entries(analyticsReadiness.record_counts || {}).map(([ds, count]) => (
                        <div key={ds} className="bg-white px-3 py-2 rounded-lg border border-slate-200 text-center min-w-[70px]">
                          <span className="text-[10px] font-bold text-slate-400 uppercase block">{ds}</span>
                          <span className="text-sm font-bold text-slate-800">{count}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                  {analyticsReadiness.missing_fields_notes?.filter(Boolean).length > 0 && (
                    <div className="p-3 bg-amber-50 border border-amber-200 text-amber-800 rounded-xl text-xs">
                      <strong>Data Coverage Notes:</strong> {analyticsReadiness.missing_fields_notes.filter(Boolean).join(' | ')}
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-slate-400 text-xs">No readiness data available.</div>
              )}
            </div>

            {/* Analytics Results Display */}
            {analyticsLoading ? (
              <div className="text-center py-12 text-slate-400">Loading analytics results...</div>
            ) : analyticsResults && analyticsResults.status !== 'no_runs_found' ? (
              <div className="space-y-6">
                {/* Forecast Metrics & Summary */}
                <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
                  <h4 className="text-base font-bold text-slate-800 mb-3 flex items-center gap-2">
                    <TrendingUp size={18} className="text-emerald-600" /> Demand Forecasts & Metrics ({analyticsResults.forecast_summary?.length || 0} items)
                  </h4>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                    <div className="bg-slate-50 p-4 rounded-xl border border-slate-200">
                      <span className="text-xs font-bold text-slate-500 uppercase">Model Used</span>
                      <p className="text-sm font-bold text-slate-800 mt-1">{analyticsResults.forecast_metrics?.model || 'Naive Baseline'}</p>
                    </div>
                    <div className="bg-slate-50 p-4 rounded-xl border border-slate-200">
                      <span className="text-xs font-bold text-slate-500 uppercase">Mean Absolute Error (MAE)</span>
                      <p className="text-sm font-bold text-slate-800 mt-1">{analyticsResults.forecast_metrics?.mae ?? 'N/A'}</p>
                    </div>
                    <div className="bg-slate-50 p-4 rounded-xl border border-slate-200">
                      <span className="text-xs font-bold text-slate-500 uppercase">Root Mean Sq Error (RMSE)</span>
                      <p className="text-sm font-bold text-slate-800 mt-1">{analyticsResults.forecast_metrics?.rmse ?? 'N/A'}</p>
                    </div>
                  </div>
                  {analyticsResults.forecast_summary?.length > 0 ? (
                    <div className="overflow-x-auto border border-slate-200 rounded-xl">
                      <table className="w-full text-left text-xs">
                        <thead className="bg-slate-100 text-slate-600 font-semibold border-b border-slate-200">
                          <tr>
                            <th className="p-3">Item ID</th>
                            <th className="p-3">Last Recorded Date</th>
                            <th className="p-3">Forecast Date</th>
                            <th className="p-3">Predicted Units</th>
                            <th className="p-3">Historical Average</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                          {analyticsResults.forecast_summary.map((f, i) => (
                            <tr key={i} className="hover:bg-slate-50">
                              <td className="p-3 font-mono font-medium text-slate-800">{f.item_id}</td>
                              <td className="p-3 text-slate-600">{f.last_recorded_date}</td>
                              <td className="p-3 text-emerald-700 font-semibold">{f.forecast_date}</td>
                              <td className="p-3 font-bold text-slate-800">{f.predicted_units}</td>
                              <td className="p-3 text-slate-600">{f.historical_average}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <p className="text-xs text-slate-400">Insufficient sales history for forecasting.</p>
                  )}
                </div>

                {/* Inventory Alignment & Risks */}
                <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
                  <h4 className="text-base font-bold text-slate-800 mb-3 flex items-center gap-2">
                    <Package size={18} className="text-purple-600" /> Inventory Alignment & Risk Detection ({analyticsResults.inventory_alignment?.length || 0})
                  </h4>
                  {analyticsResults.inventory_alignment?.length > 0 ? (
                    <div className="overflow-x-auto border border-slate-200 rounded-xl">
                      <table className="w-full text-left text-xs">
                        <thead className="bg-slate-100 text-slate-600 font-semibold border-b border-slate-200">
                          <tr>
                            <th className="p-3">Store</th>
                            <th className="p-3">Item ID</th>
                            <th className="p-3">Stock on Hand</th>
                            <th className="p-3">Daily Velocity</th>
                            <th className="p-3">Coverage (Days)</th>
                            <th className="p-3">Risk Status</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                          {analyticsResults.inventory_alignment.map((inv, i) => (
                            <tr key={i} className="hover:bg-slate-50">
                              <td className="p-3 font-medium text-slate-800">{inv.store_id}</td>
                              <td className="p-3 font-mono text-slate-600">{inv.item_id}</td>
                              <td className="p-3">{inv.stock_on_hand}</td>
                              <td className="p-3">{inv.estimated_daily_velocity}</td>
                              <td className="p-3 font-bold">{inv.coverage_days}</td>
                              <td className="p-3">
                                <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                                  inv.risk_status.includes('Stockout') ? 'bg-rose-100 text-rose-800' :
                                  inv.risk_status.includes('Excess') ? 'bg-amber-100 text-amber-800' : 'bg-emerald-100 text-emerald-800'
                                }`}>
                                  {inv.risk_status}
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <p className="text-xs text-slate-400">No inventory alignment records found. Please commit inventory and sales data.</p>
                  )}
                </div>

                {/* Customer Segments & Product Affinity */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
                    <h4 className="text-base font-bold text-slate-800 mb-3 flex items-center gap-2">
                      <Lightbulb size={18} className="text-amber-600" /> Customer Segments ({analyticsResults.customer_segments?.length || 0})
                    </h4>
                    {analyticsResults.customer_segments?.length > 0 ? (
                      <div className="space-y-2 max-h-60 overflow-y-auto">
                        {analyticsResults.customer_segments.map((c, i) => (
                          <div key={i} className="flex justify-between items-center p-3 bg-slate-50 rounded-xl border border-slate-200 text-xs">
                            <div>
                              <span className="font-mono font-semibold text-slate-800">{c.customer_id}</span>
                              <span className="ml-2 px-2 py-0.5 bg-blue-100 text-blue-800 font-bold rounded text-[10px]">{c.segment}</span>
                            </div>
                            <span className="font-bold text-slate-700">${c.lifetime_spend ?? 0}</span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-xs text-slate-400">No customer-linked sales or customer records found.</p>
                    )}
                  </div>

                  <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
                    <h4 className="text-base font-bold text-slate-800 mb-3 flex items-center gap-2">
                      <Activity size={18} className="text-indigo-600" /> Product Affinity Rules ({analyticsResults.product_affinity_rules?.length || 0})
                    </h4>
                    {analyticsResults.product_affinity_rules?.length > 0 ? (
                      <div className="space-y-2 max-h-60 overflow-y-auto">
                        {analyticsResults.product_affinity_rules.map((rule, i) => (
                          <div key={i} className="p-3 bg-slate-50 rounded-xl border border-slate-200 text-xs flex justify-between items-center">
                            <div>
                              <span className="font-mono text-slate-700 font-semibold">{rule.item_a} + {rule.item_b}</span>
                              <p className="text-[10px] text-slate-500 mt-0.5">Support: {rule.support} | Conf: {rule.confidence}</p>
                            </div>
                            <span className="px-2.5 py-1 bg-indigo-100 text-indigo-800 font-bold rounded-full text-xs">
                              Lift {rule.lift}x
                            </span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-xs text-slate-400">No transaction-level basket data found for affinity analysis.</p>
                    )}
                  </div>
                </div>

                {/* Promotion Recommendations */}
                <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
                  <h4 className="text-base font-bold text-slate-800 mb-3 flex items-center gap-2">
                    <Sparkles size={18} className="text-amber-600" /> Tenant Promotion Recommendations ({analyticsResults.recommendations?.length || 0})
                  </h4>
                  {analyticsResults.recommendations?.length > 0 ? (
                    <div className="overflow-x-auto border border-slate-200 rounded-xl">
                      <table className="w-full text-left text-xs">
                        <thead className="bg-slate-100 text-slate-600 font-semibold border-b border-slate-200">
                          <tr>
                            <th className="p-3">Store</th>
                            <th className="p-3">Item ID</th>
                            <th className="p-3">Recommended Action</th>
                            <th className="p-3">Suggested Discount</th>
                            <th className="p-3">Reasoning</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                          {analyticsResults.recommendations.map((rec, i) => (
                            <tr key={i} className="hover:bg-slate-50">
                              <td className="p-3 font-medium text-slate-800">{rec.store_id}</td>
                              <td className="p-3 font-mono text-slate-600">{rec.item_id}</td>
                              <td className="p-3 font-semibold text-amber-800">{rec.recommendation}</td>
                              <td className="p-3 font-bold text-emerald-700">{rec.suggested_discount_pct}%</td>
                              <td className="p-3 text-slate-600">{rec.reason}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <p className="text-xs text-slate-400">No promotion recommendations triggered for this tenant dataset.</p>
                  )}
                </div>
              </div>
            ) : (
              <div className="text-center py-12 bg-white rounded-2xl border border-slate-200 p-8">
                <BarChartIcon size={40} className="mx-auto text-slate-300 mb-3" />
                <h5 className="text-base font-bold text-slate-700">No Analytics Computed Yet</h5>
                <p className="text-xs text-slate-500 mt-1 max-w-md mx-auto">
                  Click <strong>Run Retailer Analytics</strong> above to evaluate demand forecasts, inventory coverage, customer segments, and recommendations for tenant <code className="font-semibold text-slate-700">{uploadRetailerId}</code>.
                </p>
              </div>
            )}
          </div>
        ) : (
          <div className="space-y-6">
            {/* Step 1: Tenant Context */}
            <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-bold text-slate-800 flex items-center gap-2">
                  <span className="w-7 h-7 rounded-full bg-amber-100 text-amber-700 flex items-center justify-center text-sm font-bold">1</span>
                  Tenant & Retailer Context
                </h3>
                <span className="text-xs px-2.5 py-1 bg-amber-50 text-amber-800 font-semibold rounded-full border border-amber-200">
                  Header Isolation Active
                </span>
              </div>
              <p className="text-sm text-slate-600 mb-4">
                Specify the tenant retailer identifier sent via the <code className="bg-slate-100 px-1.5 py-0.5 rounded text-amber-800 font-mono text-xs">X-Retailer-ID</code> header. This ensures strict database isolation between retailers.
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">Retailer ID (Tenant Scope)</label>
                  <input
                    type="text"
                    className="w-full px-4 py-2.5 rounded-lg border border-slate-200 bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 text-sm font-semibold text-slate-800"
                    value={uploadRetailerId}
                    onChange={(e) => setUploadRetailerId(e.target.value.trim())}
                    placeholder="e.g. retailer_alpha"
                  />
                  <p className="text-xs text-slate-400 mt-1">2-64 chars: letters, numbers, hyphens, underscores.</p>
                </div>
                <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 flex flex-col justify-center">
                  <span className="text-xs font-semibold text-slate-500">Security Notice</span>
                  <p className="text-xs text-slate-600 mt-0.5">
                    This header is for local development identification and is <strong>not</strong> production authentication.
                  </p>
                </div>
              </div>
            </div>

            {/* Step 2: Upload File */}
            <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-bold text-slate-800 flex items-center gap-2">
                  <span className="w-7 h-7 rounded-full bg-amber-100 text-amber-700 flex items-center justify-center text-sm font-bold">2</span>
                  Upload Dataset File (.csv)
                </h3>
                {currentBatch && (
                  <span className="text-xs px-2.5 py-1 bg-emerald-50 text-emerald-700 font-semibold rounded-full border border-emerald-200 flex items-center gap-1">
                    <CheckCircle2 size={12} /> Uploaded ({currentBatch.total_rows} rows)
                  </span>
                )}
              </div>

              <form onSubmit={handleUploadSubmit} className="space-y-4">
                <div className="border-2 border-dashed border-slate-200 rounded-2xl p-8 text-center bg-slate-50/50 hover:bg-slate-50 transition-all">
                  <Upload className="mx-auto text-slate-400 mb-3" size={36} />
                  <p className="text-sm font-medium text-slate-700">Drag and drop your dataset file, or browse</p>
                  <p className="text-xs text-slate-400 mt-1">Supports CSV files up to 50 MB</p>
                  <input
                    type="file"
                    accept=".csv,.xlsx,.xls"
                    className="mt-4 block mx-auto text-sm text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-amber-50 file:text-amber-700 hover:file:bg-amber-100 cursor-pointer"
                    onChange={handleFileChange}
                  />
                  {uploadFile && (
                    <div className="mt-3 text-xs font-semibold text-slate-700 bg-white inline-block px-3 py-1.5 rounded-lg border border-slate-200">
                      Selected: {uploadFile.name} ({(uploadFile.size / 1024).toFixed(1)} KB)
                    </div>
                  )}
                </div>

                {uploadError && (
                  <div className="p-4 bg-rose-50 border border-rose-200 text-rose-700 rounded-xl text-sm flex items-center gap-2">
                    <AlertTriangle size={16} /> {uploadError}
                  </div>
                )}

                <div className="flex justify-end">
                  <button
                    type="submit"
                    disabled={uploadLoading || !uploadFile}
                    className="px-6 py-2.5 bg-amber-600 hover:bg-amber-700 disabled:bg-slate-300 text-white font-semibold rounded-xl text-sm transition-all flex items-center gap-2 shadow-sm"
                  >
                    {uploadLoading ? <Loader2 className="animate-spin" size={16} /> : <ArrowRight size={16} />}
                    Upload & Inspect Headers
                  </button>
                </div>
              </form>
            </div>

            {/* Step 3: Column Mapping & Preview */}
            {currentBatch && (
              <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 space-y-6">
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-bold text-slate-800 flex items-center gap-2">
                    <span className="w-7 h-7 rounded-full bg-amber-100 text-amber-700 flex items-center justify-center text-sm font-bold">3</span>
                    Column Mapping & Validation Preview
                  </h3>
                  <span className="text-xs px-2.5 py-1 bg-blue-50 text-blue-700 font-semibold rounded-full border border-blue-200">
                    Dataset: {currentBatch.inferred_dataset_type.toUpperCase()}
                  </span>
                </div>

                <p className="text-sm text-slate-600">
                  Review inferred column mappings. Match your file's source columns to the canonical schema fields required by the platform.
                </p>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 bg-slate-50 p-4 rounded-xl border border-slate-200">
                  {Object.entries(columnMapping).map(([origCol, targetField]) => (
                    <div key={origCol} className="bg-white p-3 rounded-lg border border-slate-200 shadow-sm">
                      <span className="text-xs font-semibold text-slate-500 block truncate" title={origCol}>
                        Source: <span className="text-slate-800">{origCol}</span>
                      </span>
                      <div className="mt-2">
                        <label className="text-[10px] uppercase font-bold text-slate-400 block mb-1">Canonical Target</label>
                        <select
                          className="w-full py-1.5 px-2 rounded border border-slate-200 bg-slate-50 text-xs font-semibold text-slate-700 focus:outline-none focus:ring-2 focus:ring-amber-500/20"
                          value={targetField}
                          onChange={(e) => {
                            const val = e.target.value;
                            setColumnMapping(prev => ({ ...prev, [origCol]: val }));
                          }}
                        >
                          {canonicalFields.map(f => (
                            <option key={f} value={f}>{f}</option>
                          ))}
                        </select>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="flex justify-end gap-3">
                  <button
                    type="button"
                    onClick={handlePreview}
                    disabled={previewLoading}
                    className="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 text-white font-semibold rounded-xl text-sm transition-all flex items-center gap-2 shadow-sm"
                  >
                    {previewLoading ? <Loader2 className="animate-spin" size={16} /> : <Layers size={16} />}
                    Run Validation Preview
                  </button>
                </div>

                {previewError && (
                  <div className="p-4 bg-rose-50 border border-rose-200 text-rose-700 rounded-xl text-sm flex items-center gap-2">
                    <AlertTriangle size={16} /> {previewError}
                  </div>
                )}

                {previewData && (
                  <div className="mt-6 space-y-4 border-t border-slate-200 pt-6">
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                      <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 text-center">
                        <span className="text-xs font-bold text-slate-500 uppercase">Total Rows</span>
                        <p className="text-xl font-extrabold text-slate-800 mt-1">{previewData.total_rows}</p>
                      </div>
                      <div className="bg-emerald-50 p-4 rounded-xl border border-emerald-200 text-center">
                        <span className="text-xs font-bold text-emerald-700 uppercase">Valid Rows</span>
                        <p className="text-xl font-extrabold text-emerald-800 mt-1">{previewData.valid_rows_count}</p>
                      </div>
                      <div className="bg-rose-50 p-4 rounded-xl border border-rose-200 text-center">
                        <span className="text-xs font-bold text-rose-700 uppercase">Invalid Rows</span>
                        <p className="text-xl font-extrabold text-rose-800 mt-1">{previewData.invalid_rows_count}</p>
                      </div>
                      <div className="bg-amber-50 p-4 rounded-xl border border-amber-200 text-center">
                        <span className="text-xs font-bold text-amber-700 uppercase">Missing Columns</span>
                        <p className="text-xl font-extrabold text-amber-800 mt-1">{previewData.missing_required_columns?.length || 0}</p>
                      </div>
                    </div>

                    {previewData.missing_required_columns?.length > 0 && (
                      <div className="p-4 bg-rose-50 border border-rose-200 text-rose-700 rounded-xl text-sm">
                        <strong>Missing Required Columns:</strong> {previewData.missing_required_columns.join(', ')}
                      </div>
                    )}

                    {previewData.sample_preview?.length > 0 && (
                      <div>
                        <h4 className="text-sm font-bold text-slate-700 mb-2">Sample Validated Rows (Preview Only — Not Committed)</h4>
                        <div className="overflow-x-auto border border-slate-200 rounded-xl">
                          <table className="w-full text-left text-xs">
                            <thead className="bg-slate-100 text-slate-600 font-semibold border-b border-slate-200">
                              <tr>
                                {Object.keys(previewData.sample_preview[0]).map(k => (
                                  <th key={k} className="p-3">{k}</th>
                                ))}
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100">
                              {previewData.sample_preview.map((row, idx) => (
                                <tr key={idx} className="hover:bg-slate-50">
                                  {Object.values(row).map((val, i) => (
                                    <td key={i} className="p-3 text-slate-700">{String(val ?? '')}</td>
                                  ))}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}

                    {previewData.row_errors?.length > 0 && (
                      <div>
                        <h4 className="text-sm font-bold text-rose-700 mb-2">Row Validation Errors</h4>
                        <div className="max-h-48 overflow-y-auto border border-rose-200 rounded-xl bg-rose-50/30 p-3 space-y-2">
                          {previewData.row_errors.map((err, idx) => (
                            <div key={idx} className="text-xs text-rose-800 bg-white p-2 rounded border border-rose-200">
                              <strong>Row {err.row_index}:</strong> {err.error}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Step 4: Commit */}
                    <div className="bg-slate-50 p-6 rounded-2xl border border-slate-200 flex flex-col md:flex-row justify-between items-center gap-4 mt-6">
                      <div>
                        <h4 className="text-base font-bold text-slate-800">Ready to Commit to Tenant Database?</h4>
                        <p className="text-xs text-slate-500 mt-0.5">
                          Commit will persist {previewData.valid_rows_count} valid records under tenant <code className="font-semibold text-slate-700">{uploadRetailerId}</code>. Idempotency guard prevents duplicate commits.
                        </p>
                      </div>
                      <button
                        onClick={handleCommit}
                        disabled={commitLoading || previewData.valid_rows_count === 0}
                        className="px-6 py-3 bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-300 text-white font-bold rounded-xl text-sm transition-all flex items-center gap-2 shadow-sm whitespace-nowrap"
                      >
                        {commitLoading ? <Loader2 className="animate-spin" size={16} /> : <CheckCircle2 size={16} />}
                        Confirm & Commit Batch
                      </button>
                    </div>

                    {commitError && (
                      <div className="p-4 bg-rose-50 border border-rose-200 text-rose-700 rounded-xl text-sm flex items-center gap-2">
                        <AlertTriangle size={16} /> {commitError}
                      </div>
                    )}

                    {commitResult && (
                      <div className="p-4 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-xl text-sm flex items-center gap-2">
                        <CheckCircle2 size={18} /> {commitResult.message}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Step 5: Import History */}
            <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-bold text-slate-800 flex items-center gap-2">
                  <History size={20} className="text-amber-600" />
                  Tenant Import History ({uploadRetailerId})
                </h3>
                <button
                  onClick={fetchImportBatches}
                  className="px-3 py-1.5 text-xs font-semibold text-slate-600 bg-slate-100 hover:bg-slate-200 rounded-lg transition-all flex items-center gap-1.5"
                >
                  <RefreshCw size={12} /> Refresh History
                </button>
              </div>

              {batchesLoading ? (
                <div className="text-center py-8 text-slate-400">Loading import history...</div>
              ) : batchesError ? (
                <div className="p-4 bg-rose-50 text-rose-700 rounded-xl text-xs">{batchesError}</div>
              ) : importBatches.length === 0 ? (
                <div className="text-center py-8 text-slate-400 text-sm">No import batches found for this retailer tenant.</div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-50 text-slate-600 font-semibold border-b border-slate-200">
                      <tr>
                        <th className="p-3">Batch ID</th>
                        <th className="p-3">Filename</th>
                        <th className="p-3">Dataset Type</th>
                        <th className="p-3">Status</th>
                        <th className="p-3">Total Rows</th>
                        <th className="p-3">Valid Rows</th>
                        <th className="p-3">Imported At</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {importBatches.map(b => (
                        <tr key={b.batch_id} className="hover:bg-slate-50">
                          <td className="p-3 font-mono text-slate-500">{b.batch_id.slice(0, 8)}...</td>
                          <td className="p-3 font-medium text-slate-800">{b.filename}</td>
                          <td className="p-3 uppercase font-semibold text-slate-600">{b.dataset_type}</td>
                          <td className="p-3">
                            <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                              b.status === 'committed' ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'
                            }`}>
                              {b.status}
                            </span>
                          </td>
                          <td className="p-3">{b.total_rows}</td>
                          <td className="p-3">{b.valid_rows_count ?? '-'}</td>
                          <td className="p-3 text-slate-500">{new Date(b.created_at).toLocaleString()}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    );
  };


  // Open explanation modal and fetch rule-engine data immediately
  const openExplanation = useCallback(async (itemId, storeId) => {
    setExplanationModal({ itemId, storeId });
    setExplanationData(null);
    setExplanationError(null);
    setExplanationLoading(true);
    setExpandedLimitations(false);
    // Reset AI tab state each time the modal opens
    setActiveModalTab('rule');
    setAiData(null);
    setAiError(null);
    setAiLoading(false);
    setAffinityData(null);
    setAffinityError(null);
    setAffinityLoading(true);

    getProductAffinity(itemId, storeId)
      .then(res => setAffinityData(res))
      .catch(err => setAffinityError(err?.message || 'Failed to load affinity'))
      .finally(() => setAffinityLoading(false));

    try {
      const data = await getRecommendationExplanation(itemId, storeId);
      setExplanationData(data);
    } catch (err) {
      const msg = err?.response?.data?.detail || err?.message || 'Failed to load explanation.';
      setExplanationError(msg);
    } finally {
      setExplanationLoading(false);
    }
  }, []);

  const closeExplanation = useCallback(() => {
    setExplanationModal(null);
    setExplanationData(null);
    setExplanationError(null);
    setAiData(null);
    setAiError(null);
  }, []);

  // Lazy AI explanation — called only when user clicks "Generate AI Explanation"
  const generateAiExplanation = useCallback(async () => {
    if (!explanationModal) return;
    setAiLoading(true);
    setAiError(null);
    setAiData(null);
    try {
      const data = await getAiExplanation(explanationModal.itemId, explanationModal.storeId);
      // The endpoint returns 200 even on provider errors; check explanation_type
      if (data.explanation_type === 'error') {
        setAiError(data.error_message || 'AI provider returned an error.');
      } else {
        setAiData(data);
      }
    } catch (err) {
      const msg = err?.response?.data?.detail || err?.message || 'Failed to reach AI endpoint.';
      setAiError(msg);
    } finally {
      setAiLoading(false);
    }
  }, [explanationModal]);

  // Safe numeric formatter — returns fallback string when value is null/undefined/NaN/Infinity
  const fmt = (val, decimals = 2, fallback = 'N/A') => {
    if (val === null || val === undefined) return fallback;
    const n = Number(val);
    if (!isFinite(n)) return fallback;
    return n.toFixed(decimals);
  };

  // -------------------------------------------------------------
  // ExplanationModal component (inline, uses App state via closure)
  // -------------------------------------------------------------
  const ExplanationModal = () => {
    if (!explanationModal) return null;
    const d = explanationData;

    const recommendationColor = (rec) => {
      if (!rec) return 'bg-slate-100 text-slate-700';
      if (rec.includes('excess inventory')) return 'bg-amber-100 text-amber-800';
      if (rec.includes('demand decline')) return 'bg-rose-100 text-rose-700';
      if (rec.includes('replenishment')) return 'bg-red-100 text-red-700';
      if (rec.includes('No action')) return 'bg-emerald-100 text-emerald-700';
      if (rec.includes('Cannot evaluate')) return 'bg-slate-100 text-slate-500';
      return 'bg-blue-100 text-blue-700';
    };

    return (
      <div
        id="explanation-modal-overlay"
        className="fixed inset-0 z-50 flex items-center justify-center p-4"
        style={{ background: 'rgba(15,23,42,0.55)', backdropFilter: 'blur(2px)' }}
        onClick={(e) => { if (e.target.id === 'explanation-modal-overlay') closeExplanation(); }}
        role="dialog"
        aria-modal="true"
        aria-label={`Explanation for ${explanationModal.itemId} at ${explanationModal.storeId}`}
      >
        <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] flex flex-col overflow-hidden border border-slate-200">

          {/* Modal Header */}
          <div className="px-6 py-5 border-b border-slate-100 flex items-start justify-between bg-slate-900 text-white rounded-t-2xl">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <HelpCircle size={18} className="text-blue-400" />
                <h2 className="font-bold text-lg tracking-tight">Why this recommendation?</h2>
              </div>
              <p className="text-slate-400 text-xs font-medium">
                {explanationModal.itemId} &bull; Store {explanationModal.storeId}
              </p>
            </div>
            <button
              id="close-explanation-modal"
              onClick={closeExplanation}
              className="ml-4 text-slate-400 hover:text-white transition-colors p-1 rounded-lg hover:bg-white/10"
              aria-label="Close explanation"
            >
              <X size={20} />
            </button>
          </div>

          {/* Tab Bar */}
          <div className="flex border-b border-slate-200 bg-slate-50">
            <button
              id="modal-tab-rule"
              onClick={() => setActiveModalTab('rule')}
              className={`flex-1 px-4 py-3 text-xs font-semibold tracking-wide uppercase transition-all ${
                activeModalTab === 'rule'
                  ? 'border-b-2 border-indigo-500 text-indigo-700 bg-white'
                  : 'text-slate-500 hover:text-slate-700 hover:bg-slate-100'
              }`}
            >
              <span className="flex items-center justify-center gap-1.5">
                <HelpCircle size={12} />
                Rule Engine
              </span>
            </button>
            <button
              id="modal-tab-ai"
              onClick={() => setActiveModalTab('ai')}
              className={`flex-1 px-4 py-3 text-xs font-semibold tracking-wide uppercase transition-all ${
                activeModalTab === 'ai'
                  ? 'border-b-2 border-violet-500 text-violet-700 bg-white'
                  : 'text-slate-500 hover:text-slate-700 hover:bg-slate-100'
              }`}
            >
              <span className="flex items-center justify-center gap-1.5">
                <Sparkles size={12} />
                AI Explanation
              </span>
            </button>
          </div>

          {/* Modal Body */}
          <div className="overflow-y-auto flex-1 p-6 space-y-5">

            {/* ==================== RULE ENGINE TAB ==================== */}
            {activeModalTab === 'rule' && (
              <>
                {/* Source badge */}
                <div className="flex items-center gap-2">
                  <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-100 text-slate-600 border border-slate-200">
                    <HelpCircle size={11} /> Rule-based engine — not an LLM
                  </span>
                </div>

                {/* Loading */}
                {explanationLoading && (
                  <div className="py-16 flex flex-col items-center justify-center gap-3 text-slate-400">
                    <Loader2 className="animate-spin" size={32} />
                    <p className="text-sm">Loading explanation…</p>
                  </div>
                )}

                {/* Error */}
                {explanationError && !explanationLoading && (
                  <div className="flex items-start gap-3 bg-red-50 border border-red-200 text-red-700 rounded-xl p-4">
                    <AlertCircle size={18} className="mt-0.5 shrink-0" />
                    <p className="text-sm">{explanationError}</p>
                  </div>
                )}

                {/* Content */}
                {d && !explanationLoading && (
                  <>
                    {/* Recommendation status */}
                    <div className="flex flex-wrap items-center gap-3">
                      <span className={`inline-flex items-center px-3 py-1.5 rounded-full text-xs font-bold ${recommendationColor(d.recommendation)}`}>
                        {d.recommendation || 'Unknown'}
                      </span>
                      {d.selected_candidate_discount_pct != null && (
                        <span className="inline-flex items-center px-3 py-1.5 rounded-full text-xs font-bold bg-purple-100 text-purple-700 border border-purple-200">
                          {d.selected_candidate_discount_pct}% Candidate Discount
                        </span>
                      )}
                      {d.selected_discounted_price != null && (
                        <span className="text-xs text-slate-500">
                          Discounted price: <strong className="text-slate-700">${fmt(d.selected_discounted_price)}</strong>
                          {d.selected_discounted_margin_pct != null && (
                            <> &bull; margin <strong>{fmt(d.selected_discounted_margin_pct, 1)}%</strong></>
                          )}
                        </span>
                      )}
                    </div>

                    {/* Stored explanation text */}
                    {d.explanation && (
                      <div className="bg-blue-50 border border-blue-100 rounded-xl p-4">
                        <p className="text-xs font-semibold text-blue-700 uppercase tracking-wider mb-2">Rule Engine Explanation</p>
                        <p className="text-sm text-slate-700 leading-relaxed">{d.explanation}</p>
                      </div>
                    )}

                    {/* Manager Decision Section */}
                    <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 space-y-3">
                      <div className="flex items-center justify-between">
                        <p className="text-xs font-semibold text-slate-700 uppercase tracking-wider">Campaign Approval Workflow</p>
                        {d.decision_status === 'approved' ? (
                          <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800">✓ Approved</span>
                        ) : d.decision_status === 'rejected' ? (
                          <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-rose-100 text-rose-800">✗ Rejected</span>
                        ) : (
                          <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-100 text-amber-800">Pending Review</span>
                        )}
                      </div>
                      {d.decided_at && (
                        <p className="text-xs text-slate-500">
                          Last decided: {new Date(d.decided_at).toLocaleString()} by <span className="font-medium text-slate-700">{d.actor || 'Local Demo Manager (Unauthenticated)'}</span>
                        </p>
                      )}
                      {d.decision_notes && (
                        <p className="text-xs text-slate-600 bg-white p-2 rounded border border-slate-100">
                          <strong>Manager Notes:</strong> {d.decision_notes}
                        </p>
                      )}
                      <div className="space-y-2 pt-2">
                        <input
                          type="text"
                          placeholder="Optional manager notes (e.g. Approved for weekend promo)..."
                          value={decisionNotes}
                          onChange={(e) => setDecisionNotes(e.target.value)}
                          className="w-full text-xs px-3 py-2 border border-slate-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                        />
                        <div className="flex gap-2">
                          <button
                            disabled={decisionLoading}
                            onClick={() => handleDecision(explanationModal.itemId, explanationModal.storeId, 'approve')}
                            className="flex-1 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold py-2 rounded-lg transition-colors shadow-sm disabled:opacity-50 flex items-center justify-center gap-1"
                          >
                            {decisionLoading ? <Loader2 size={14} className="animate-spin" /> : '✓ Approve Campaign'}
                          </button>
                          <button
                            disabled={decisionLoading}
                            onClick={() => handleDecision(explanationModal.itemId, explanationModal.storeId, 'reject')}
                            className="flex-1 bg-rose-600 hover:bg-rose-700 text-white text-xs font-semibold py-2 rounded-lg transition-colors shadow-sm disabled:opacity-50 flex items-center justify-center gap-1"
                          >
                            {decisionLoading ? <Loader2 size={14} className="animate-spin" /> : '✗ Reject Campaign'}
                          </button>
                        </div>
                        {decisionError && (
                          <p className="text-xs text-rose-600 mt-1">{decisionError}</p>
                        )}
                      </div>
                    </div>

                    {/* Frequently Bought Together (Product Affinity) */}
                    <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 space-y-3">
                      <div className="flex items-center justify-between">
                        <p className="text-xs font-semibold text-slate-700 uppercase tracking-wider">Frequently Bought Together (Product Affinity)</p>
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-800 border border-amber-200">
                          ⚠️ SYNTHETIC DEMO DATA
                        </span>
                      </div>
                      <p className="text-xs text-slate-500">
                        Association rules computed from synthetic basket transactions. Not real Walmart customer data.
                      </p>

                      {affinityLoading ? (
                        <div className="py-6 flex justify-center text-slate-400">
                          <Loader2 className="animate-spin" size={20} />
                        </div>
                      ) : affinityError ? (
                        <p className="text-xs text-rose-600">{affinityError}</p>
                      ) : affinityData?.affinity_items?.length > 0 ? (
                        <div className="space-y-2">
                          {affinityData.affinity_items.map((item, idx) => (
                            <div key={idx} className="bg-white rounded-lg p-3 border border-slate-100 flex items-center justify-between text-xs">
                              <div>
                                <span className="font-bold text-slate-800">{item.related_item_id}</span>
                                <div className="text-slate-400 text-[11px]">Co-occurrences: {item.co_occurrence_count}</div>
                              </div>
                              <div className="flex items-center gap-3 text-right">
                                <div>
                                  <div className="text-slate-500">Support</div>
                                  <div className="font-semibold text-slate-700">{(item.support * 100).toFixed(1)}%</div>
                                </div>
                                <div>
                                  <div className="text-slate-500">Confidence</div>
                                  <div className="font-semibold text-slate-700">{(item.confidence * 100).toFixed(1)}%</div>
                                </div>
                                <div>
                                  <div className="text-slate-500">Lift</div>
                                  <div className="font-semibold text-indigo-600">{item.lift.toFixed(2)}x</div>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p className="text-xs text-slate-500 italic">No synthetic affinity items found for this product.</p>
                      )}
                    </div>

                    {/* Supporting factors */}
                    {d.supporting_factors?.length > 0 && (
                      <div>
                        <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Supporting Factors</p>
                        <ul className="space-y-1.5">
                          {d.supporting_factors.map((f, i) => (
                            <li key={i} className="flex items-start gap-2 text-sm text-slate-700">
                              <span className="mt-1 w-1.5 h-1.5 rounded-full bg-indigo-400 shrink-0" />
                              {f}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Metrics grid */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">

                      {/* Demand metrics */}
                      <div className="bg-slate-50 rounded-xl p-4 border border-slate-100">
                        <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">Demand Metrics</p>
                        <dl className="space-y-2 text-sm">
                          <div className="flex justify-between">
                            <dt className="text-slate-500">Demand used</dt>
                            <dd className="font-medium text-slate-800">
                              {fmt(d.demand_metrics?.demand_used_units_per_day, 3)} units/day
                            </dd>
                          </div>
                          <div className="flex justify-between">
                            <dt className="text-slate-500">Previous 28d units</dt>
                            <dd className="font-medium text-slate-800">{d.demand_metrics?.previous_28d_units ?? 'N/A'}</dd>
                          </div>
                          <div className="flex justify-between">
                            <dt className="text-slate-500">Recent 28d units</dt>
                            <dd className="font-medium text-slate-800">{d.demand_metrics?.recent_28d_units ?? 'N/A'}</dd>
                          </div>
                          <div className="flex justify-between">
                            <dt className="text-slate-500">28d demand change</dt>
                            <dd className={`font-medium ${
                              d.demand_metrics?.demand_change_pct == null ? 'text-slate-400'
                              : d.demand_metrics.demand_change_pct < -20 ? 'text-rose-600'
                              : d.demand_metrics.demand_change_pct > 0 ? 'text-emerald-600'
                              : 'text-slate-700'
                            }`}>
                              {d.demand_metrics?.demand_change_pct != null
                                ? `${d.demand_metrics.demand_change_pct > 0 ? '+' : ''}${fmt(d.demand_metrics.demand_change_pct, 1)}%`
                                : 'N/A'}
                            </dd>
                          </div>
                        </dl>
                        <p className="mt-3 text-xs text-amber-700 bg-amber-50 rounded-lg px-2 py-1.5 leading-snug">
                          ⚠ {d.demand_metrics?.demand_label || 'Demand source unknown'}
                        </p>
                  </div>

                      {/* Inventory metrics */}
                      <div className="bg-slate-50 rounded-xl p-4 border border-slate-100">
                        <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">Inventory Metrics <span className="text-amber-600 normal-case font-normal">(Simulated)</span></p>
                        <dl className="space-y-2 text-sm">
                          <div className="flex justify-between">
                            <dt className="text-slate-500">Simulated stock</dt>
                            <dd className="font-medium text-slate-800">{d.inventory_metrics?.simulated_inventory_units ?? 'N/A'} units</dd>
                          </div>
                          <div className="flex justify-between">
                            <dt className="text-slate-500">Coverage days</dt>
                            <dd className="font-medium text-slate-800">{fmt(d.inventory_metrics?.coverage_days, 1)} days</dd>
                          </div>
                        </dl>
                        {d.inventory_metrics?.inventory_source && (
                          <p className="mt-3 text-xs text-amber-700 bg-amber-50 rounded-lg px-2 py-1.5 leading-snug">
                            ⚠ {d.inventory_metrics.inventory_source}
                          </p>
                        )}
                      </div>

                      {/* Price & margin */}
                      <div className="bg-slate-50 rounded-xl p-4 border border-slate-100">
                        <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">Price &amp; Margin</p>
                        <dl className="space-y-2 text-sm">
                          <div className="flex justify-between">
                            <dt className="text-slate-500">Selling price</dt>
                            <dd className="font-medium text-slate-800">${fmt(d.price_and_margin?.latest_sell_price)}</dd>
                          </div>
                          <div className="flex justify-between">
                            <dt className="text-slate-500">Assumed unit cost</dt>
                            <dd className="font-medium text-slate-800">${fmt(d.price_and_margin?.assumed_unit_cost)}</dd>
                          </div>
                          <div className="flex justify-between">
                            <dt className="text-slate-500">Current margin</dt>
                            <dd className="font-medium text-slate-800">{fmt(d.price_and_margin?.current_margin_pct, 1)}%</dd>
                          </div>
                        </dl>
                        {d.price_and_margin?.cost_source && (
                          <p className="mt-3 text-xs text-amber-700 bg-amber-50 rounded-lg px-2 py-1.5 leading-snug">
                            ⚠ {d.price_and_margin.cost_source}
                          </p>
                        )}
                      </div>

                      {/* Discount scenarios */}
                      {d.discount_scenarios?.length > 0 && (
                        <div className="bg-slate-50 rounded-xl p-4 border border-slate-100">
                          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">Discount Scenarios</p>
                          <div className="space-y-1.5">
                            {d.discount_scenarios.filter(s => s.discount_pct > 0).map((s) => (
                              <div key={s.discount_pct} className={`flex items-center justify-between text-xs rounded-lg px-3 py-2 ${
                                s.discount_pct === d.selected_candidate_discount_pct
                                  ? 'bg-purple-100 border border-purple-200 font-semibold'
                                  : 'bg-white border border-slate-100'
                              }`}>
                                <span className="text-slate-600">{s.discount_pct}% off &rarr; ${fmt(s.discounted_price)}</span>
                                <span className={`font-medium ${
                                  s.passes_margin_rules ? 'text-emerald-600' : 'text-slate-400 line-through'
                                }`}>
                                  {fmt(s.margin_pct, 1)}% margin
                                  {s.discount_pct === d.selected_candidate_discount_pct && ' ✓ selected'}
                                </span>
                              </div>
                            ))}
                            {d.rejected_discount_scenarios && (
                              <p className="text-xs text-slate-500 mt-1 italic">Blocked: {d.rejected_discount_scenarios}</p>
                            )}
                          </div>
                        </div>
                      )}

                    </div>

                    {/* Data limitations (collapsible) */}
                    {d.data_limitations?.length > 0 && (
                      <div className="border border-slate-200 rounded-xl overflow-hidden">
                        <button
                          id="toggle-data-limitations"
                          className="w-full flex items-center justify-between px-4 py-3 bg-slate-50 hover:bg-slate-100 transition-colors text-left"
                          onClick={() => setExpandedLimitations(prev => !prev)}
                          aria-expanded={expandedLimitations}
                        >
                          <span className="text-xs font-semibold text-slate-600 uppercase tracking-wider">Data Limitations &amp; Assumptions</span>
                          {expandedLimitations ? <ChevronUp size={16} className="text-slate-400" /> : <ChevronDown size={16} className="text-slate-400" />}
                        </button>
                        {expandedLimitations && (
                          <ul className="px-4 py-3 space-y-1.5 bg-white">
                            {d.data_limitations.map((lim, i) => (
                              <li key={i} className="flex items-start gap-2 text-xs text-slate-600">
                                <span className="mt-1 w-1.5 h-1.5 rounded-full bg-amber-400 shrink-0" />
                                {lim}
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                    )}
                  </>
                )}
              </>
            )}

            {/* ==================== AI EXPLANATION TAB ==================== */}
            {activeModalTab === 'ai' && (
              <>
                {/* Idle — not yet generated */}
                {!aiLoading && !aiData && !aiError && (
                  <div className="flex flex-col items-center justify-center py-12 gap-4 text-center">
                    <div className="w-14 h-14 rounded-2xl bg-violet-50 border border-violet-100 flex items-center justify-center">
                      <Sparkles size={24} className="text-violet-500" />
                    </div>
                    <div>
                      <p className="font-semibold text-slate-800 mb-1">Generate an AI Explanation</p>
                      <p className="text-xs text-slate-500 max-w-xs leading-relaxed">
                        Uses Google Gemini to produce a plain-language explanation grounded in the stored data.
                        The rule engine remains authoritative — the AI only explains, never decides.
                      </p>
                    </div>
                    <button
                      id="generate-ai-explanation-btn"
                      onClick={generateAiExplanation}
                      className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-violet-600 hover:bg-violet-700 text-white text-sm font-semibold transition-all shadow-sm hover:shadow-md"
                    >
                      <Sparkles size={14} /> Generate AI Explanation
                    </button>
                    <p className="text-xs text-slate-400">
                      Requires <code className="bg-slate-100 px-1 rounded">GEMINI_API_KEY</code> in the backend .env
                    </p>
                  </div>
                )}

                {/* Loading */}
                {aiLoading && (
                  <div className="py-16 flex flex-col items-center justify-center gap-3 text-slate-400">
                    <Loader2 className="animate-spin text-violet-500" size={32} />
                    <p className="text-sm">Generating AI explanation…</p>
                    <p className="text-xs text-slate-400">This may take up to 30 seconds.</p>
                  </div>
                )}

                {/* Error */}
                {aiError && !aiLoading && (
                  <div className="space-y-4">
                    <div className="flex items-start gap-3 bg-amber-50 border border-amber-200 text-amber-800 rounded-xl p-4">
                      <AlertCircle size={18} className="mt-0.5 shrink-0" />
                      <div>
                        <p className="text-sm font-semibold mb-1">AI Explanation Unavailable</p>
                        <p className="text-xs leading-relaxed">{aiError}</p>
                      </div>
                    </div>
                    <div className="flex justify-center">
                      <button
                        id="retry-ai-explanation-btn"
                        onClick={generateAiExplanation}
                        className="flex items-center gap-2 px-4 py-2 rounded-lg border border-slate-200 text-sm text-slate-600 hover:bg-slate-50 transition-all"
                      >
                        <RefreshCw size={13} /> Try again
                      </button>
                    </div>
                  </div>
                )}

                {/* Success */}
                {aiData && !aiLoading && (
                  <>
                    {/* Provider badge */}
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-violet-100 text-violet-700 border border-violet-200">
                        <Sparkles size={11} /> AI-GENERATED
                      </span>
                      <span className="text-xs text-slate-500">
                        {aiData.provider} · {aiData.model} · {aiData.latency_ms}ms
                      </span>
                      {aiData.ai_explanation?.human_review_required && (
                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-100 text-amber-700 border border-amber-200">
                          ⚠ Human review required
                        </span>
                      )}
                    </div>

                    {/* Summary */}
                    {aiData.ai_explanation?.summary && (
                      <div className="bg-violet-50 border border-violet-100 rounded-xl p-4">
                        <p className="text-xs font-semibold text-violet-700 uppercase tracking-wider mb-2">AI Summary</p>
                        <p className="text-sm text-slate-700 leading-relaxed">{aiData.ai_explanation.summary}</p>
                      </div>
                    )}

                    {/* Supporting factors */}
                    {aiData.ai_explanation?.supporting_factors?.length > 0 && (
                      <div>
                        <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Supporting Factors</p>
                        <ul className="space-y-1.5">
                          {aiData.ai_explanation.supporting_factors.map((f, i) => (
                            <li key={i} className="flex items-start gap-2 text-sm text-slate-700">
                              <span className="mt-1 w-1.5 h-1.5 rounded-full bg-violet-400 shrink-0" />
                              {f}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Inventory & discount context */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      {aiData.ai_explanation?.inventory_context && (
                        <div className="bg-slate-50 rounded-xl p-4 border border-slate-100">
                          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Inventory Context <span className="normal-case text-amber-600 font-normal">(Simulated)</span></p>
                          <p className="text-sm text-slate-700">{aiData.ai_explanation.inventory_context}</p>
                        </div>
                      )}
                      {aiData.ai_explanation?.discount_context && (
                        <div className="bg-slate-50 rounded-xl p-4 border border-slate-100">
                          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Discount Context</p>
                          <p className="text-sm text-slate-700">{aiData.ai_explanation.discount_context}</p>
                        </div>
                      )}
                    </div>

                    {/* Limitations */}
                    {aiData.ai_explanation?.limitations?.length > 0 && (
                      <div className="border border-amber-200 rounded-xl overflow-hidden">
                        <div className="px-4 py-3 bg-amber-50 flex items-center gap-2">
                          <AlertCircle size={13} className="text-amber-600" />
                          <span className="text-xs font-semibold text-amber-700 uppercase tracking-wider">AI-Stated Limitations</span>
                        </div>
                        <ul className="px-4 py-3 space-y-1.5 bg-white">
                          {aiData.ai_explanation.limitations.map((lim, i) => (
                            <li key={i} className="flex items-start gap-2 text-xs text-slate-600">
                              <span className="mt-1 w-1.5 h-1.5 rounded-full bg-amber-400 shrink-0" />
                              {lim}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Factual metrics grounding notice */}
                    <p className="text-xs text-slate-400 leading-relaxed">
                      The AI explanation above was generated from the stored MongoDB record at {aiData.generated_at ? new Date(aiData.generated_at).toLocaleString() : ''}.
                      The recommendation and discount are determined solely by the rule engine and were not changed by the AI.
                    </p>
                  </>
                )}
              </>
            )}

          </div>

          {/* Modal Footer */}
          <div className="px-6 py-4 border-t border-slate-100 bg-slate-50 rounded-b-2xl flex justify-between items-center">
            <p className="text-xs text-slate-400">Candidate discounts are suggestions for human review only. No sales or profit outcome is guaranteed.</p>
            <button
              id="close-explanation-modal-footer"
              onClick={closeExplanation}
              className="text-xs font-semibold text-slate-600 hover:text-slate-900 transition-colors px-3 py-1.5 rounded-lg hover:bg-slate-200"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    );
  };

  // -------------------------------------------------------------
  // Views
  // -------------------------------------------------------------
  const renderDashboard = () => (
    <div className="max-w-7xl mx-auto space-y-6 animate-in fade-in duration-500 pb-12">
      
      {/* Disclaimers */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-amber-50/80 border border-amber-200/60 text-amber-800 px-4 py-3 rounded-xl flex items-start gap-3 shadow-sm">
          <AlertCircle size={20} className="mt-0.5 shrink-0 text-amber-600" />
          <p className="text-xs font-medium leading-relaxed"><strong>Data Integrity Note:</strong> Inventory values are simulated and unit costs are assumed for prototype purposes.</p>
        </div>
        <div className="bg-blue-50/80 border border-blue-200/60 text-blue-800 px-4 py-3 rounded-xl flex items-start gap-3 shadow-sm">
          <Lightbulb size={20} className="mt-0.5 shrink-0 text-blue-600" />
          <p className="text-xs font-medium leading-relaxed"><strong>AI Note:</strong> Promotion recommendations are rule-based prototype suggestions and should be reviewed by a human.</p>
        </div>
      </div>

      {/* KPI Section */}
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4">
        <div className="bg-white rounded-2xl p-5 shadow-sm border border-slate-100 hover:shadow-md transition-shadow group">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Total Products</p>
          <div className="flex items-end justify-between">
            <h3 className="text-3xl font-bold text-slate-800 group-hover:text-blue-600 transition-colors">{totalProducts.toLocaleString()}</h3>
            <Package size={20} className="text-blue-200 mb-1" />
          </div>
        </div>
        <div className="bg-white rounded-2xl p-5 shadow-sm border border-slate-100 hover:shadow-md transition-shadow group">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Total Recs</p>
          <div className="flex items-end justify-between">
            <h3 className="text-3xl font-bold text-slate-800 group-hover:text-purple-600 transition-colors">{totalRecs.toLocaleString()}</h3>
            <TrendingUp size={20} className="text-purple-200 mb-1" />
          </div>
        </div>
        <div className="bg-white rounded-2xl p-5 shadow-sm border border-slate-100 hover:shadow-md transition-shadow group">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Promotions</p>
          <div className="flex items-end justify-between">
            <h3 className="text-3xl font-bold text-emerald-600">{promoCount}</h3>
            <span className="text-xs font-medium text-slate-400 mb-1 flex items-center gap-1">items</span>
          </div>
        </div>
        <div className="bg-white rounded-2xl p-5 shadow-sm border border-slate-100 hover:shadow-md transition-shadow group">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Avg Discount</p>
          <div className="flex items-end justify-between">
            <h3 className="text-3xl font-bold text-indigo-600">{avgDiscount}%</h3>
            <span className="text-xs font-medium text-slate-400 mb-1 flex items-center gap-1">avg</span>
          </div>
        </div>
        <div className="bg-white rounded-2xl p-5 shadow-sm border border-slate-100 hover:shadow-md transition-shadow group">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Avg Inventory</p>
          <div className="flex items-end justify-between">
            <h3 className="text-3xl font-bold text-slate-800">{avgInventory}</h3>
            <span className="text-xs font-medium text-slate-400 mb-1 flex items-center gap-1">units</span>
          </div>
        </div>
        <div className="bg-white rounded-2xl p-5 shadow-sm border border-slate-100 hover:shadow-md transition-shadow group">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Attention Required</p>
          <div className="flex items-end justify-between">
            <h3 className="text-3xl font-bold text-rose-600">{lowStockCount}</h3>
            <span className="text-xs font-medium text-slate-400 mb-1 flex items-center gap-1">low stock</span>
          </div>
        </div>
      </div>

      {/* Decision Insights */}
      <div className="bg-gradient-to-r from-blue-900 to-indigo-900 rounded-2xl p-6 text-white shadow-md relative overflow-hidden">
        <div className="absolute top-0 right-0 p-8 opacity-10 pointer-events-none">
          <Activity size={120} />
        </div>
        <div className="relative z-10">
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Lightbulb size={20} className="text-yellow-400" />
            Decision Insights
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="bg-white/10 backdrop-blur-sm rounded-xl p-4 border border-white/10">
              <p className="text-sm text-blue-100 mb-1">Promotion Strategy</p>
              <p className="text-base font-medium">
                {promoCount > 0 
                  ? `${Math.round((promoCount / (recommendations.length || 1)) * 100)}% of items on this page have active promotion recommendations, averaging a ${avgDiscount}% discount.`
                  : "No promotions recommended for the current selection."}
              </p>
            </div>
            <div className="bg-white/10 backdrop-blur-sm rounded-xl p-4 border border-white/10">
              <p className="text-sm text-blue-100 mb-1">Inventory Health</p>
              <p className="text-base font-medium">
                {lowStockCount > 0
                  ? `${lowStockCount} items have less than 14 days of simulated coverage and may require immediate restocking.`
                  : "All items on this page show healthy simulated inventory levels."}
              </p>
            </div>
            <div className="bg-white/10 backdrop-blur-sm rounded-xl p-4 border border-white/10">
              <p className="text-sm text-blue-100 mb-1">Demand Leaders</p>
              <p className="text-base font-medium">
                {demandData.length > 0 
                  ? `Item ${demandData[0].name} leads historical proxy demand with ${demandData[0].demand} units/day.`
                  : "Insufficient data to determine demand leaders."}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Analytics Charts */}
      {(loadingProducts || loadingRecs) ? (
        <div className="h-64 flex items-center justify-center bg-white rounded-2xl border border-slate-100">
          <Loader2 className="animate-spin text-primary" size={32} />
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          
          {/* Chart 1: Demand */}
          <div className="bg-white rounded-2xl p-5 shadow-sm border border-slate-100 lg:col-span-2">
            <div className="flex items-center gap-2 mb-6">
              <BarChart2 size={18} className="text-slate-400" />
              <h3 className="text-base font-semibold text-slate-800">Historical Demand by Product</h3>
            </div>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={demandData} margin={{ top: 10, right: 10, left: -20, bottom: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                  <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#64748b' }} angle={-45} textAnchor="end" />
                  <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#64748b' }} />
                  <RechartsTooltip cursor={{fill: '#f8fafc'}} contentStyle={{borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)'}} />
                  <Bar dataKey="demand" name="Avg Daily Units" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Chart 2: Promo Distribution */}
          <div className="bg-white rounded-2xl p-5 shadow-sm border border-slate-100">
            <div className="flex items-center gap-2 mb-2">
              <PieChartIcon size={18} className="text-slate-400" />
              <h3 className="text-base font-semibold text-slate-800">Recommended Discounts</h3>
            </div>
            <div className="h-72 relative">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={promoDistributionData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={90}
                    paddingAngle={5}
                    dataKey="value"
                  >
                    {promoDistributionData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <RechartsTooltip contentStyle={{borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)'}} />
                  <Legend verticalAlign="bottom" height={36} iconType="circle" wrapperStyle={{fontSize: '12px'}} />
                </PieChart>
              </ResponsiveContainer>
              {promoDistributionData.length === 0 && (
                <div className="absolute inset-0 flex items-center justify-center text-sm text-slate-400">No data</div>
              )}
            </div>
          </div>

          {/* Chart 3: Inventory vs Coverage */}
          <div className="bg-white rounded-2xl p-5 shadow-sm border border-slate-100 lg:col-span-3">
            <div className="flex items-center gap-2 mb-6">
              <Package size={18} className="text-slate-400" />
              <h3 className="text-base font-semibold text-slate-800">Simulated Inventory vs Coverage Days</h3>
            </div>
            <div className="h-80">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={inventoryData} margin={{ top: 10, right: 10, left: -20, bottom: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                  <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#64748b' }} />
                  <YAxis yAxisId="left" orientation="left" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#64748b' }} />
                  <YAxis yAxisId="right" orientation="right" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#64748b' }} />
                  <RechartsTooltip cursor={{fill: '#f8fafc'}} contentStyle={{borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)'}} />
                  <Legend wrapperStyle={{fontSize: '12px', paddingTop: '20px'}} />
                  <Bar yAxisId="left" dataKey="stock" name="Simulated Stock (Units)" fill="#10b981" radius={[4, 4, 0, 0]} maxBarSize={50} />
                  <Line yAxisId="right" type="monotone" dataKey="coverage" name="Coverage (Days)" stroke="#f59e0b" strokeWidth={3} dot={{r: 4, strokeWidth: 2}} activeDot={{r: 6}} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </div>

        </div>
      )}
    </div>
  );

  const renderInventory = () => (
    <div className="max-w-7xl mx-auto space-y-8 animate-in fade-in duration-500 pb-12">
      {/* Disclaimer */}
      <div className="bg-amber-50 border border-amber-200 text-amber-800 px-4 py-3 rounded-lg flex items-start gap-3 shadow-sm">
        <AlertCircle size={20} className="mt-0.5 shrink-0" />
        <p className="text-sm font-medium">Prototype Disclaimer: Inventory values are simulated for prototype purposes.</p>
      </div>

      {/* Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100 flex items-center justify-between hover:shadow-md transition-shadow">
          <div>
            <p className="text-sm font-medium text-slate-500 mb-1">Total Products</p>
            <h3 className="text-3xl font-bold text-slate-800">{totalProducts.toLocaleString()}</h3>
          </div>
          <div className="w-12 h-12 bg-blue-50 rounded-full flex items-center justify-center text-blue-600">
            <Package size={24} />
          </div>
        </div>
        
        <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100 flex items-center justify-between hover:shadow-md transition-shadow">
          <div>
            <p className="text-sm font-medium text-slate-500 mb-1">Average Inventory</p>
            <h3 className="text-3xl font-bold text-slate-800">{avgInventory} <span className="text-sm font-normal text-slate-500">units</span></h3>
          </div>
          <div className="w-12 h-12 bg-emerald-50 rounded-full flex items-center justify-center text-emerald-600">
            <TrendingUp size={24} />
          </div>
        </div>
        
        <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100 flex items-center justify-between hover:shadow-md transition-shadow">
          <div>
            <p className="text-sm font-medium text-slate-500 mb-1">Low Stock Items</p>
            <h3 className="text-3xl font-bold text-rose-600">{lowStockCount}</h3>
          </div>
          <div className="w-12 h-12 bg-rose-50 rounded-full flex items-center justify-center text-rose-600">
            <AlertCircle size={24} />
          </div>
        </div>
      </div>

      {/* Inventory Section */}
      <section className="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden">
        <div className="px-6 py-5 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
          <h2 className="text-lg font-semibold text-slate-800">Inventory Levels</h2>
          <span className="text-xs font-medium text-slate-500 bg-slate-100 px-3 py-1 rounded-full">Showing up to 20</span>
        </div>
        
        {loadingProducts ? (
          <div className="p-12 flex justify-center text-primary">
            <Loader2 className="animate-spin" size={32} />
          </div>
        ) : errorProducts ? (
          <div className="p-8 text-center text-red-500 bg-red-50">{errorProducts}</div>
        ) : products.length === 0 ? (
          <div className="p-12 text-center text-slate-500">No products found.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-600">
              <thead className="text-xs uppercase bg-slate-50 text-slate-500 border-b border-slate-100">
                <tr>
                  <th className="px-6 py-4 font-semibold">Item ID</th>
                  <th className="px-6 py-4 font-semibold">Store</th>
                  <th className="px-6 py-4 font-semibold text-right">Selling Price</th>
                  <th className="px-6 py-4 font-semibold text-right">Simulated Stock*</th>
                  <th className="px-6 py-4 font-semibold text-right">Coverage Days*</th>
                  <th className="px-6 py-4 font-semibold text-right">Avg Daily Demand</th>
                  <th className="px-6 py-4 font-semibold text-right">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {products.map((prod) => {
                  const isLowStock = (prod.simulated_coverage_days || 0) < 14;
                  return (
                    <tr key={prod.id || prod.item_id} className="hover:bg-slate-50/80 transition-colors">
                      <td className="px-6 py-4 font-medium text-slate-900">{prod.item_id}</td>
                      <td className="px-6 py-4">
                        <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-slate-100 text-slate-700">
                          {prod.store_id}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-right">${prod.latest_sell_price?.toFixed(2)}</td>
                      <td className="px-6 py-4 text-right font-medium text-slate-900">{prod.simulated_inventory_units}</td>
                      <td className="px-6 py-4 text-right">{prod.simulated_coverage_days?.toFixed(1) || 'N/A'}</td>
                      <td className="px-6 py-4 text-right">{prod.average_daily_units?.toFixed(3) || 'N/A'}</td>
                      <td className="px-6 py-4 text-right">
                        {isLowStock ? (
                          <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-rose-100 text-rose-700">Low Stock</span>
                        ) : (
                          <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-emerald-100 text-emerald-700">Healthy</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );

  const renderPromotions = () => (
    <div className="max-w-7xl mx-auto space-y-6 animate-in fade-in duration-500 pb-12">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100 flex items-center justify-between hover:shadow-md transition-shadow">
          <div>
            <p className="text-sm font-medium text-slate-500 mb-1">Total Recommendations</p>
            <h3 className="text-3xl font-bold text-slate-800">{totalRecs.toLocaleString()}</h3>
          </div>
          <div className="w-12 h-12 bg-blue-50 rounded-full flex items-center justify-center text-blue-600">
            <TrendingUp size={24} />
          </div>
        </div>

        <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100 flex items-center justify-between hover:shadow-md transition-shadow">
          <div>
            <p className="text-sm font-medium text-slate-500 mb-1">Active Promos</p>
            <h3 className="text-3xl font-bold text-emerald-600">{promoCount}</h3>
          </div>
          <div className="w-12 h-12 bg-emerald-50 rounded-full flex items-center justify-center text-emerald-600">
            <Package size={24} />
          </div>
        </div>

        <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100 flex items-center justify-between hover:shadow-md transition-shadow">
          <div>
            <p className="text-sm font-medium text-slate-500 mb-1">Avg Discount</p>
            <h3 className="text-3xl font-bold text-purple-600">{avgDiscount}%</h3>
          </div>
          <div className="w-12 h-12 bg-purple-50 rounded-full flex items-center justify-center text-purple-600">
            <TrendingUp size={24} />
          </div>
        </div>
      </div>

      {/* Promotions Section */}
      <section className="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden">
        <div className="px-6 py-5 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
          <h2 className="text-lg font-semibold text-slate-800">Promotion Recommendations</h2>
          <span className="text-xs font-medium text-slate-500 bg-slate-100 px-3 py-1 rounded-full">Showing up to 20</span>
        </div>
        
        {loadingRecs ? (
          <div className="p-12 flex justify-center text-primary">
            <Loader2 className="animate-spin" size={32} />
          </div>
        ) : errorRecs ? (
          <div className="p-8 text-center text-red-500 bg-red-50">{errorRecs}</div>
        ) : recommendations.length === 0 ? (
          <div className="p-12 text-center text-slate-500">No recommendations found.</div>
        ) : (
          <div className="p-6 grid grid-cols-1 xl:grid-cols-2 gap-6">
            {recommendations.map((rec) => (
              <div key={rec._id || rec.item_id} className={`border ${rec.selected_candidate_discount_pct > 0 ? 'border-purple-200 bg-white hover:border-purple-300 hover:shadow-md' : 'border-slate-200 bg-slate-50/50 hover:border-slate-300 hover:shadow-sm'} rounded-xl p-5 transition-all group`}>
                <div className="flex justify-between items-start mb-4">
                  <div>
                    <h3 className="font-bold text-slate-800 text-lg group-hover:text-primary transition-colors">{rec.item_id}</h3>
                    <p className="text-xs text-slate-500">{rec.dept_id} • {rec.store_id}</p>
                  </div>
                  <div className="text-right">
                    {rec.selected_candidate_discount_pct > 0 ? (
                      <span className="inline-block px-3 py-1 rounded-full text-xs font-bold bg-purple-100 text-purple-700 border border-purple-200">
                        {rec.selected_candidate_discount_pct}% Discount
                      </span>
                    ) : (
                      <span className="inline-block px-3 py-1 rounded-full text-xs font-bold bg-slate-100 text-slate-600 border border-slate-200">
                        No Promotion
                      </span>
                    )}
                  </div>
                </div>
                
                <div className="grid grid-cols-3 gap-4 mb-5 p-4 bg-white rounded-lg text-sm border border-slate-100 shadow-sm">
                  <div>
                    <p className="text-slate-500 text-xs mb-1">Current Price</p>
                    <p className={`font-semibold ${rec.selected_candidate_discount_pct > 0 ? 'text-slate-500 line-through decoration-slate-400/50' : 'text-slate-800'}`}>
                      ${rec.latest_sell_price?.toFixed(2)}
                    </p>
                  </div>
                  <div>
                    <p className="text-slate-500 text-xs mb-1">Promo Price</p>
                    <p className={`font-bold ${rec.selected_candidate_discount_pct > 0 ? 'text-emerald-600' : 'text-slate-500'}`}>
                      ${rec.selected_discounted_price?.toFixed(2) || rec.latest_sell_price?.toFixed(2)}
                    </p>
                  </div>
                  <div>
                    <p className="text-slate-500 text-xs mb-1">Target Margin</p>
                    <p className="font-semibold text-slate-700">
                      {rec.selected_discounted_margin_pct ? `${rec.selected_discounted_margin_pct.toFixed(1)}%` : 'N/A'}
                    </p>
                  </div>
                </div>
                
                <div className="flex items-center justify-between pt-3 mb-3 border-t border-slate-100">
                  <div className="flex items-center gap-2 text-xs">
                    {rec.decision_status === 'approved' ? (
                      <span className="px-2.5 py-0.5 rounded-full font-bold bg-emerald-100 text-emerald-800">✓ Approved</span>
                    ) : rec.decision_status === 'rejected' ? (
                      <span className="px-2.5 py-0.5 rounded-full font-bold bg-rose-100 text-rose-800">✗ Rejected</span>
                    ) : (
                      <span className="px-2.5 py-0.5 rounded-full font-bold bg-amber-100 text-amber-800">Pending Review</span>
                    )}
                  </div>
                  <div className="flex items-center gap-1.5">
                    <button
                      disabled={decisionLoading}
                      onClick={() => handleDecision(rec.item_id, rec.store_id, 'approve')}
                      className="px-2.5 py-1 rounded-lg text-xs font-semibold bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200 transition-colors disabled:opacity-50"
                    >
                      Approve
                    </button>
                    <button
                      disabled={decisionLoading}
                      onClick={() => handleDecision(rec.item_id, rec.store_id, 'reject')}
                      className="px-2.5 py-1 rounded-lg text-xs font-semibold bg-rose-50 text-rose-700 hover:bg-rose-100 border border-rose-200 transition-colors disabled:opacity-50"
                    >
                      Reject
                    </button>
                  </div>
                </div>

                <div className="mb-4">
                  <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">AI Assessment</h4>
                  <p className="text-sm text-slate-800 font-medium mb-1">{rec.recommendation}</p>
                  <p className="text-sm text-slate-500 leading-relaxed line-clamp-3" title={rec.explanation}>{rec.explanation}</p>
                </div>

                <div className="flex items-center justify-between pt-4 border-t border-slate-200">
                  <div className="flex items-center gap-2 text-xs text-slate-600">
                    <Package size={14} className="text-slate-400" />
                    Simulated Stock: <span className="font-medium text-slate-700">{rec.simulated_inventory_units}</span>
                    <span className="text-slate-400 mx-1">|</span>
                    Coverage: <span className="font-medium text-slate-700">{rec.coverage_days?.toFixed(1)} days</span>
                  </div>
                  <button
                    id={`explain-btn-${rec.item_id}-${rec.store_id}`}
                    onClick={() => openExplanation(rec.item_id, rec.store_id)}
                    className="flex items-center gap-1.5 text-xs font-semibold text-indigo-600 hover:text-indigo-800 hover:bg-indigo-50 px-3 py-1.5 rounded-lg transition-all border border-indigo-200 hover:border-indigo-300"
                    title={`Explain recommendation for ${rec.item_id} at ${rec.store_id}`}
                  >
                    <HelpCircle size={13} />
                    Why this?
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );

  const renderSegments = () => (
    <div className="max-w-7xl mx-auto space-y-6 animate-in fade-in duration-500 pb-12">
      <div className="flex justify-between items-center bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h1 className="text-2xl font-bold text-slate-800">Customer Segmentation & Personalized Promotions</h1>
            <span className="px-2.5 py-0.5 rounded text-xs font-bold bg-amber-100 text-amber-800 border border-amber-200">
              ⚠️ SYNTHETIC DEMO DATA
            </span>
          </div>
          <p className="text-sm text-slate-500">
            Derived from reproducible synthetic demo customer transactions. Does not represent real shopper behavior or live CRM data.
          </p>
        </div>
      </div>

      {loadingSegments ? (
        <div className="py-20 flex justify-center text-primary">
          <Loader2 className="animate-spin" size={36} />
        </div>
      ) : errorSegments ? (
        <div className="p-6 bg-red-50 text-red-600 rounded-xl">{errorSegments}</div>
      ) : (
        <div className="space-y-6">
          {/* Segments Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
            {segments.map((seg, idx) => (
              <div key={idx} className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100 flex flex-col justify-between">
                <div>
                  <div className="flex justify-between items-start mb-3">
                    <h3 className="text-lg font-bold text-slate-800">{seg.segment}</h3>
                    <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-blue-50 text-blue-700">
                      {seg.customer_count} customers
                    </span>
                  </div>
                  <div className="space-y-2 text-sm text-slate-600 mb-6">
                    <div className="flex justify-between">
                      <span className="text-slate-400">Avg Spend:</span>
                      <span className="font-semibold text-slate-800">${seg.avg_spend?.toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Avg Frequency:</span>
                      <span className="font-semibold text-slate-800">{seg.avg_frequency?.toFixed(1)} orders</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Avg Basket Value:</span>
                      <span className="font-semibold text-slate-800">${seg.avg_basket_value?.toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Avg Discount Usage:</span>
                      <span className="font-semibold text-slate-800">{seg.avg_discount_pct?.toFixed(1)}%</span>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Segment Targeted Promotions Section */}
          <div className="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden">
            <div className="px-6 py-5 border-b border-slate-100 bg-slate-50/50 flex items-center justify-between">
              <h3 className="text-base font-semibold text-slate-800">Targeted Promotional Campaign Suggestions</h3>
              <span className="text-xs text-slate-500 bg-slate-100 px-3 py-1 rounded-full">Segment-Specific</span>
            </div>
            <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-6">
              {segmentPromos.map((promo, idx) => (
                <div key={idx} className="border border-slate-200 rounded-xl p-5 bg-slate-50/50 hover:shadow-md transition-all space-y-3">
                  <div className="flex justify-between items-start">
                    <div>
                      <span className="inline-block px-2 py-0.5 rounded text-xs font-bold bg-purple-100 text-purple-700 mb-2">
                        {promo.segment}
                      </span>
                      <h4 className="font-bold text-slate-800 text-base">{promo.campaign_title}</h4>
                    </div>
                    <span className="px-3 py-1 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800">
                      {promo.suggested_discount_pct}% Discount
                    </span>
                  </div>
                  <p className="text-xs text-slate-500">
                    <strong>Target Category:</strong> {promo.target_category}
                  </p>
                  <p className="text-sm text-slate-700 leading-relaxed">
                    {promo.rationale}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );

  const renderCampaignReports = () => {
    const rep = campaignReports || {};
    const counts = rep.decision_counts || { approved: 0, rejected: 0, pending: 0 };
    const rates = rep.decision_rates_pct || { approved: 0, rejected: 0, pending: 0 };
    const discDist = rep.discount_distribution || {};
    const categories = rep.recommendation_categories || {};

    const statusPieData = [
      { name: 'Approved', value: counts.approved },
      { name: 'Rejected', value: counts.rejected },
      { name: 'Pending', value: counts.pending }
    ].filter(d => d.value > 0);

    const discountBarData = Object.keys(discDist).map(k => ({
      name: k,
      count: discDist[k]
    }));

    const outcomesList = campaignOutcomesData?.outcomes || [];

    return (
      <div className="max-w-7xl mx-auto space-y-6 animate-in fade-in duration-500 pb-12">
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center bg-white p-6 rounded-2xl shadow-sm border border-slate-100 gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <h1 className="text-2xl font-bold text-slate-800">Campaign Effectiveness & Impact Reporting</h1>
              <span className="px-2.5 py-0.5 rounded text-xs font-bold bg-indigo-100 text-indigo-800 border border-indigo-200">
                Stage 4 Report
              </span>
            </div>
            <p className="text-sm text-slate-500">
              Summarizes decision history, approval rates, discount distributions, and measured campaign outcomes.
            </p>
          </div>
          <div className="text-xs bg-slate-100 text-slate-600 px-3 py-2 rounded-xl border border-slate-200">
            <div><strong>Time Period:</strong> M5 Historical Proxy & Log Window</div>
            <div><strong>Source:</strong> Real Operational Records & Evaluated Outcomes</div>
          </div>
        </div>

        <div className="bg-amber-50 border border-amber-200 rounded-2xl p-5 text-amber-900 text-xs md:text-sm flex items-start gap-3 shadow-sm">
          <AlertCircle size={20} className="text-amber-600 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <strong className="font-bold">Important Methodological Distinction:</strong>
            <p>
              {rep.execution_status_note || 'Proposed or approved campaigns are distinct from executed campaigns. Approval does not imply campaign execution, nor does it infer causal promotion lift from ordinary sales changes.'}
            </p>
          </div>
        </div>

        {loadingCampaignReports ? (
          <div className="py-20 flex justify-center text-primary">
            <Loader2 className="animate-spin" size={36} />
          </div>
        ) : errorCampaignReports ? (
          <div className="p-6 bg-red-50 text-red-600 rounded-xl">{errorCampaignReports}</div>
        ) : (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-6">
              <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100 flex flex-col justify-between">
                <div>
                  <p className="text-xs font-medium text-slate-500 mb-1">Total Recommendations</p>
                  <h3 className="text-3xl font-bold text-slate-800">{rep.total_recommendations?.toLocaleString() || 0}</h3>
                </div>
                <div className="mt-4 pt-3 border-t border-slate-100 text-xs text-slate-400">
                  Across selected store scope
                </div>
              </div>

              <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100 flex flex-col justify-between">
                <div>
                  <p className="text-xs font-medium text-slate-500 mb-1">Approved Decisions</p>
                  <h3 className="text-3xl font-bold text-emerald-600">{counts.approved} <span className="text-sm font-normal text-slate-500">({rates.approved}%)</span></h3>
                </div>
                <div className="mt-4 pt-3 border-t border-slate-100 text-xs text-emerald-600 font-medium">
                  Approved for execution
                </div>
              </div>

              <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100 flex flex-col justify-between">
                <div>
                  <p className="text-xs font-medium text-slate-500 mb-1">Rejected Decisions</p>
                  <h3 className="text-3xl font-bold text-rose-600">{counts.rejected} <span className="text-sm font-normal text-slate-500">({rates.rejected}%)</span></h3>
                </div>
                <div className="mt-4 pt-3 border-t border-slate-100 text-xs text-rose-600 font-medium">
                  Declined by manager
                </div>
              </div>

              <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100 flex flex-col justify-between">
                <div>
                  <p className="text-xs font-medium text-slate-500 mb-1">Pending Review</p>
                  <h3 className="text-3xl font-bold text-amber-600">{counts.pending} <span className="text-sm font-normal text-slate-500">({rates.pending}%)</span></h3>
                </div>
                <div className="mt-4 pt-3 border-t border-slate-100 text-xs text-amber-600 font-medium">
                  Awaiting review
                </div>
              </div>

              <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100 flex flex-col justify-between">
                <div>
                  <p className="text-xs font-medium text-slate-500 mb-1">Average Discount</p>
                  <h3 className="text-3xl font-bold text-purple-600">{rep.average_discount_pct || 0}%</h3>
                </div>
                <div className="mt-4 pt-3 border-t border-slate-100 text-xs text-purple-600 font-medium">
                  Mean planned markdown
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100 flex flex-col">
                <h3 className="text-base font-bold text-slate-800 mb-4">Decision Status Breakdown</h3>
                <div className="h-64 flex items-center justify-center">
                  {statusPieData.length === 0 ? (
                    <p className="text-sm text-slate-400">No decision data available</p>
                  ) : (
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={statusPieData}
                          cx="50%"
                          cy="50%"
                          innerRadius={60}
                          outerRadius={90}
                          paddingAngle={4}
                          dataKey="value"
                          label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                        >
                          {statusPieData.map((entry, index) => (
                            <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                          ))}
                        </Pie>
                        <RechartsTooltip />
                      </PieChart>
                    </ResponsiveContainer>
                  )}
                </div>
              </div>

              <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100 flex flex-col">
                <h3 className="text-base font-bold text-slate-800 mb-4">Discount Tier Distribution</h3>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={discountBarData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                      <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                      <YAxis tick={{ fontSize: 12 }} />
                      <RechartsTooltip />
                      <Bar dataKey="count" fill="#8b5cf6" radius={[6, 6, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100 flex flex-col">
                <h3 className="text-base font-bold text-slate-800 mb-4">Recommendation Categories</h3>
                <div className="h-64 overflow-y-auto pr-2">
                  <div className="space-y-3">
                    {Object.entries(categories).map(([cat, count], idx) => (
                      <div key={idx} className="flex justify-between items-center text-xs border-b border-slate-100 pb-2">
                        <span className="text-slate-600 font-medium truncate max-w-[200px]" title={cat}>{cat}</span>
                        <span className="font-bold text-slate-800 bg-slate-100 px-2 py-0.5 rounded-full">{count}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden">
              <div className="px-6 py-5 border-b border-slate-100 bg-slate-50/50 flex flex-col md:flex-row justify-between items-start md:items-center gap-2">
                <div>
                  <h3 className="text-base font-semibold text-slate-800">Campaign Outcome Evaluation Interface</h3>
                  <p className="text-xs text-slate-500">Record measured campaign results (redemptions, sales lift, revenue gain) separately from proposed recommendations.</p>
                </div>
                <span className="px-3 py-1 rounded-full text-xs font-bold bg-amber-100 text-amber-800 border border-amber-200">
                  ⚠️ SYNTHETIC & REAL EVALUATION
                </span>
              </div>

              <div className="p-6">
                {outcomeError && <div className="mb-4 p-3 bg-red-50 text-red-600 rounded-lg text-sm">{outcomeError}</div>}
                {outcomeSuccess && <div className="mb-4 p-3 bg-emerald-50 text-emerald-600 rounded-lg text-sm">{outcomeSuccess}</div>}

                <form onSubmit={handleOutcomeSubmit} className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8 p-5 bg-slate-50 rounded-xl border border-slate-200">
                  <div>
                    <label className="block text-xs font-semibold text-slate-600 mb-1">Item ID</label>
                    <input
                      type="text"
                      required
                      className="w-full px-3 py-2 rounded-lg border border-slate-300 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                      value={outcomeItemId}
                      onChange={(e) => setOutcomeItemId(e.target.value)}
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-600 mb-1">Store ID</label>
                    <input
                      type="text"
                      required
                      className="w-full px-3 py-2 rounded-lg border border-slate-300 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                      value={outcomeStoreIdForm}
                      onChange={(e) => setOutcomeStoreIdForm(e.target.value)}
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-600 mb-1">Actual Redemptions (int &ge; 0)</label>
                    <input
                      type="number"
                      min="0"
                      required
                      className="w-full px-3 py-2 rounded-lg border border-slate-300 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                      value={outcomeRedemptions}
                      onChange={(e) => setOutcomeRedemptions(e.target.value)}
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-600 mb-1">Sales Lift % (float)</label>
                    <input
                      type="number"
                      step="0.1"
                      required
                      className="w-full px-3 py-2 rounded-lg border border-slate-300 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                      value={outcomeSalesLift}
                      onChange={(e) => setOutcomeSalesLift(e.target.value)}
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-600 mb-1">Revenue Gain ($)</label>
                    <input
                      type="number"
                      step="0.01"
                      required
                      className="w-full px-3 py-2 rounded-lg border border-slate-300 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                      value={outcomeRevenueGain}
                      onChange={(e) => setOutcomeRevenueGain(e.target.value)}
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-600 mb-1">Measured Period</label>
                    <input
                      type="text"
                      required
                      className="w-full px-3 py-2 rounded-lg border border-slate-300 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                      value={outcomePeriod}
                      onChange={(e) => setOutcomePeriod(e.target.value)}
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-600 mb-1">Data Source Label</label>
                    <select
                      className="w-full px-3 py-2 rounded-lg border border-slate-300 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 font-semibold text-slate-700"
                      value={outcomeDataSource}
                      onChange={(e) => setOutcomeDataSource(e.target.value)}
                    >
                      <option value="SYNTHETIC_DEMO_DATA">SYNTHETIC_DEMO_DATA</option>
                      <option value="REAL_RETAILER_DATA">REAL_RETAILER_DATA</option>
                    </select>
                  </div>

                  <div className="flex items-end">
                    <button
                      type="submit"
                      disabled={outcomeSubmitting}
                      className="w-full py-2 px-4 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg text-sm transition-colors shadow-sm disabled:opacity-50"
                    >
                      {outcomeSubmitting ? 'Saving...' : 'Record Outcome'}
                    </button>
                  </div>
                </form>

                <h4 className="font-bold text-slate-800 text-sm mb-3">Measured Campaign Outcomes ({outcomesList.length})</h4>
                <div className="overflow-x-auto border border-slate-200 rounded-xl">
                  <table className="w-full text-left text-sm">
                    <thead className="bg-slate-100 text-slate-700 font-semibold text-xs uppercase tracking-wider border-b border-slate-200">
                      <tr>
                        <th className="p-3">Item ID / Store</th>
                        <th className="p-3">Redemptions</th>
                        <th className="p-3">Sales Lift</th>
                        <th className="p-3">Revenue Gain</th>
                        <th className="p-3">Measured Period</th>
                        <th className="p-3">Data Source</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200 bg-white">
                      {outcomesList.length === 0 ? (
                        <tr>
                          <td colSpan="6" className="p-6 text-center text-slate-400">No measured campaign outcomes recorded yet.</td>
                        </tr>
                      ) : (
                        outcomesList.map((out, idx) => (
                          <tr key={idx} className="hover:bg-slate-50 transition-colors">
                            <td className="p-3 font-semibold text-slate-800">{out.item_id} <span className="text-xs font-normal text-slate-500">({out.store_id})</span></td>
                            <td className="p-3 text-slate-700">{out.actual_redemptions?.toLocaleString()}</td>
                            <td className="p-3 text-emerald-600 font-bold">+{out.actual_sales_lift_pct}%</td>
                            <td className="p-3 text-purple-600 font-bold">${out.actual_revenue_gain?.toLocaleString(undefined, {minimumFractionDigits: 2})}</td>
                            <td className="p-3 text-slate-600">{out.measured_period}</td>
                            <td className="p-3">
                              <span className={`px-2.5 py-1 rounded-full text-xs font-bold ${out.data_source === 'SYNTHETIC_DEMO_DATA' ? 'bg-amber-100 text-amber-800 border border-amber-200' : 'bg-blue-100 text-blue-800 border border-blue-200'}`}>
                                {out.data_source}
                              </span>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    );
  };

  return (
    <div className="flex h-screen bg-background text-slate-800 overflow-hidden font-sans">
      {/* Explanation Modal (portal-style, rendered above everything) */}
      <ExplanationModal />
      {/* Sidebar */}
      <aside className="w-64 bg-slate-900 text-white flex flex-col hidden md:flex border-r border-slate-800">
        <div className="p-6 border-b border-slate-800">
          <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-xl flex items-center justify-center mb-4 shadow-lg shadow-blue-500/20">
            <Activity size={24} className="text-white" />
          </div>
          <h2 className="text-xl font-bold text-white tracking-tight">IntelliPromo</h2>
          <p className="text-slate-400 text-xs mt-1 font-medium">Decision Support System</p>
        </div>
        <nav className="flex-1 mt-6 px-4 space-y-2">
          <button 
            onClick={() => setActiveTab('dashboard')} 
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all font-medium text-sm ${activeTab === 'dashboard' ? 'bg-blue-600/10 text-blue-400' : 'hover:bg-slate-800 text-slate-300'}`}
          >
            <LayoutDashboard size={18} /> Dashboard
          </button>
          <button 
            onClick={() => setActiveTab('inventory')} 
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all font-medium text-sm ${activeTab === 'inventory' ? 'bg-emerald-600/10 text-emerald-400' : 'hover:bg-slate-800 text-slate-300'}`}
          >
            <Package size={18} /> Inventory
          </button>
          <button 
            onClick={() => setActiveTab('promotions')} 
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all font-medium text-sm ${activeTab === 'promotions' ? 'bg-purple-600/10 text-purple-400' : 'hover:bg-slate-800 text-slate-300'}`}
          >
            <TrendingUp size={18} /> Promotions
          </button>
          <button 
            onClick={() => setActiveTab('segments')} 
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all font-medium text-sm ${activeTab === 'segments' ? 'bg-amber-600/10 text-amber-400' : 'hover:bg-slate-800 text-slate-300'}`}
          >
            <Lightbulb size={18} /> Segments & Promos
          </button>
          <button 
            onClick={() => setActiveTab('reports')} 
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all font-medium text-sm ${activeTab === 'reports' ? 'bg-indigo-600/10 text-indigo-400' : 'hover:bg-slate-800 text-slate-300'}`}
          >
            <BarChart2 size={18} /> Campaign Reports
          </button>
          <button 
            onClick={() => setActiveTab('upload')} 
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all font-medium text-sm ${activeTab === 'upload' ? 'bg-amber-600/10 text-amber-400' : 'hover:bg-slate-800 text-slate-300'}`}
          >
            <Upload size={18} /> Upload Data
          </button>
        </nav>
        <div className="p-4 text-xs text-slate-500 text-center border-t border-slate-800">
          Academic Prototype
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col h-full overflow-hidden relative bg-slate-50/50">
        {/* Header */}
        <header className="bg-white shadow-sm px-8 py-5 flex flex-col sm:flex-row justify-between items-center gap-4 z-10 border-b border-slate-200">
          <div>
            <h1 className="text-xl md:text-2xl font-bold text-slate-800 tracking-tight">Retail Promotion & Inventory Intelligence</h1>
            <p className="text-xs md:text-sm text-slate-500 font-medium mt-1">AI-assisted decision support for demand, inventory and promotion planning</p>
          </div>
          
          <div className="flex items-center gap-4 w-full md:w-auto">
            <form onSubmit={handleSearch} className="flex flex-1 md:w-64 relative">
              <input 
                type="text" 
                placeholder="Search Item ID..." 
                className="w-full pl-10 pr-4 py-2 rounded-lg border border-slate-200 bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all text-sm"
                value={searchItem}
                onChange={(e) => setSearchItem(e.target.value)}
              />
              <Search className="absolute left-3 top-2.5 text-slate-400" size={16} />
              <button type="submit" className="hidden">Search</button>
            </form>

            <div className="flex items-center gap-2">
              <Store size={18} className="text-slate-500" />
              <select 
                className="py-2 px-3 rounded-lg border border-slate-200 bg-slate-50 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 text-sm font-semibold text-slate-700"
                value={storeId}
                onChange={(e) => setStoreId(e.target.value)}
              >
                <option value="">All Stores</option>
                <option value="CA_1">CA_1</option>
                <option value="CA_2">CA_2</option>
                <option value="CA_3">CA_3</option>
                <option value="TX_1">TX_1</option>
                <option value="TX_2">TX_2</option>
                <option value="TX_3">TX_3</option>
                <option value="WI_1">WI_1</option>
                <option value="WI_2">WI_2</option>
                <option value="WI_3">WI_3</option>
              </select>
            </div>
          </div>
        </header>

        {/* Scrollable Content */}
        <div className="flex-1 overflow-y-auto p-8">
          {activeTab === 'dashboard' && renderDashboard()}
          {activeTab === 'inventory' && renderInventory()}
          {activeTab === 'promotions' && renderPromotions()}
          {activeTab === 'segments' && renderSegments()}
          {activeTab === 'reports' && renderCampaignReports()}
          {activeTab === 'upload' && renderUploadWizard()}
        </div>
      </main>
    </div>
  );
};

export default App;
