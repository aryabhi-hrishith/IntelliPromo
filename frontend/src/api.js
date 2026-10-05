import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

export const getProducts = async (limit = 20, storeId = '', itemId = '') => {
  let url = `${API_BASE_URL}/products?limit=${limit}`;
  if (storeId) {
    url += `&store_id=${storeId}`;
  }
  
  if (itemId) {
    // Search by item id endpoint
    let searchUrl = `${API_BASE_URL}/products/${itemId}`;
    if (storeId) {
      searchUrl += `?store_id=${storeId}`;
    }
    const response = await axios.get(searchUrl);
    return {
      results: response.data.results || [],
      total_matching: response.data.returned || 0
    };
  }

  const response = await axios.get(url);
  return response.data;
};

export const getRecommendations = async (limit = 20, storeId = '', itemId = '') => {
  let url = `${API_BASE_URL}/recommendations?limit=${limit}`;
  if (storeId) {
    url += `&store_id=${storeId}`;
  }

  if (itemId) {
    // Search by item id endpoint
    let searchUrl = `${API_BASE_URL}/recommendations/${itemId}`;
    if (storeId) {
      searchUrl += `?store_id=${storeId}`;
    }
    const response = await axios.get(searchUrl);
    return {
      results: response.data.results || [],
      total_matching: response.data.returned || 0
    };
  }

  const response = await axios.get(url);
  return response.data;
};

/**
 * Fetch the structured rule-based explanation for a single (item_id, store_id) pair.
 * store_id is always required because item_id is not unique across stores.
 */
export const getRecommendationExplanation = async (itemId, storeId) => {
  const url = `${API_BASE_URL}/recommendations/${encodeURIComponent(itemId)}/explanation?store_id=${encodeURIComponent(storeId)}`;
  const response = await axios.get(url);
  return response.data;
};

/**
 * Fetch a real LLM-generated explanation for a single (item_id, store_id) pair.
 *
 * Returns a dict with explanation_type = "ai_generated" on success or
 * explanation_type = "error" when the provider is not configured or fails.
 * The server never throws a 5xx for provider errors — check explanation_type
 * in the response to determine whether the text was AI-generated.
 *
 * store_id is required (same constraint as the rule-engine endpoint).
 */
export const getAiExplanation = async (itemId, storeId) => {
  const url = `${API_BASE_URL}/recommendations/${encodeURIComponent(itemId)}/ai-explanation?store_id=${encodeURIComponent(storeId)}`;
  const response = await axios.get(url);
  return response.data;
};

/**
 * Post an approval or rejection decision for a recommendation.
 */
export const postRecommendationDecision = async (itemId, storeId, action, notes = '') => {
  const url = `${API_BASE_URL}/recommendations/${encodeURIComponent(itemId)}/decision?store_id=${encodeURIComponent(storeId)}`;
  const response = await axios.post(url, { action, notes });
  return response.data;
};

/**
 * Fetch decision history for a recommendation.
 */
export const getRecommendationDecisions = async (itemId, storeId) => {
  const url = `${API_BASE_URL}/recommendations/${encodeURIComponent(itemId)}/decisions?store_id=${encodeURIComponent(storeId)}`;
  const response = await axios.get(url);
  return response.data;
};

/**
 * Fetch product affinity (Frequently Bought Together) items.
 */
export const getProductAffinity = async (itemId, storeId = '') => {
  let url = `${API_BASE_URL}/recommendations/${encodeURIComponent(itemId)}/affinity`;
  if (storeId) {
    url += `?store_id=${encodeURIComponent(storeId)}`;
  }
  const response = await axios.get(url);
  return response.data;
};

/**
 * Fetch synthetic customer segments.
 */
export const getCustomerSegments = async () => {
  const url = `${API_BASE_URL}/segments`;
  const response = await axios.get(url);
  return response.data;
};

/**
 * Fetch segment-targeted promotional campaigns.
 */
export const getSegmentPromotions = async () => {
  const url = `${API_BASE_URL}/segments/promotions`;
  const response = await axios.get(url);
  return response.data;
};

/**
 * Fetch campaign effectiveness reports.
 */
export const getCampaignReports = async (storeId = '') => {
  let url = `${API_BASE_URL}/campaign-reports`;
  if (storeId) {
    url += `?store_id=${storeId}`;
  }
  const response = await axios.get(url);
  return response.data;
};

/**
 * Fetch measured campaign outcomes.
 */
export const getCampaignOutcomes = async (storeId = '') => {
  let url = `${API_BASE_URL}/campaign-reports/outcomes`;
  if (storeId) {
    url += `?store_id=${storeId}`;
  }
  const response = await axios.get(url);
  return response.data;
};

/**
 * Record or evaluate campaign outcomes.
 */
export const postCampaignOutcome = async (outcomeData) => {
  const url = `${API_BASE_URL}/campaign-reports/outcomes`;
  const response = await axios.post(url, outcomeData);
  return response.data;
};

/**
 * Upload a retailer dataset file.
 */
export const uploadRetailerData = async (file, retailerId) => {
  const formData = new FormData();
  formData.append('file', file);
  const response = await axios.post(`${API_BASE_URL}/ingest/upload`, formData, {
    headers: {
      'X-Retailer-ID': retailerId,
      'Content-Type': 'multipart/form-data'
    }
  });
  return response.data;
};

/**
 * List tenant-scoped import batches.
 */
export const getImportBatches = async (retailerId) => {
  const response = await axios.get(`${API_BASE_URL}/ingest/batches`, {
    headers: { 'X-Retailer-ID': retailerId }
  });
  return response.data;
};

/**
 * Get import batch status/details.
 */
export const getBatchStatus = async (batchId, retailerId) => {
  const response = await axios.get(`${API_BASE_URL}/ingest/batches/${encodeURIComponent(batchId)}`, {
    headers: { 'X-Retailer-ID': retailerId }
  });
  return response.data;
};

/**
 * Preview mapped import batch.
 */
export const previewBatch = async (batchId, datasetType, mapping, sheetName = null, retailerId) => {
  const response = await axios.post(
    `${API_BASE_URL}/ingest/batches/${encodeURIComponent(batchId)}/preview`,
    { dataset_type: datasetType, mapping, sheet_name: sheetName },
    { headers: { 'X-Retailer-ID': retailerId } }
  );
  return response.data;
};

/**
 * Commit validated import batch.
 */
export const commitBatch = async (batchId, datasetType, mapping, sheetName = null, retailerId) => {
  const response = await axios.post(
    `${API_BASE_URL}/ingest/batches/${encodeURIComponent(batchId)}/commit`,
    { dataset_type: datasetType, mapping, sheet_name: sheetName },
    { headers: { 'X-Retailer-ID': retailerId } }
  );
  return response.data;
};

/**
 * Assess data readiness for tenant retailer.
 */
export const getAnalyticsReadiness = async (retailerId) => {
  const response = await axios.get(`${API_BASE_URL}/analytics/readiness`, {
    headers: { 'X-Retailer-ID': retailerId }
  });
  return response.data;
};

/**
 * Run tenant analytics.
 */
export const runAnalytics = async (retailerId) => {
  const response = await axios.post(`${API_BASE_URL}/analytics/run`, {}, {
    headers: { 'X-Retailer-ID': retailerId }
  });
  return response.data;
};

/**
 * Retrieve latest analytics run results.
 */
export const getAnalyticsResults = async (retailerId) => {
  const response = await axios.get(`${API_BASE_URL}/analytics/results`, {
    headers: { 'X-Retailer-ID': retailerId }
  });
  return response.data;
};

/**
 * Retrieve unified AI decisions for tenant retailer.
 */
export const getAnalyticsDecisions = async (retailerId) => {
  const response = await axios.get(`${API_BASE_URL}/analytics/decisions`, {
    headers: { 'X-Retailer-ID': retailerId }
  });
  return response.data;
};



