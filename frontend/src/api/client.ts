import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
})

export default api

// --- 车辆 ---
export const getVehicles = () => api.get('/vehicles/')
export const createVehicle = (data: Record<string, unknown>) => api.post('/vehicles/', data)

// --- 订单 ---
export const getTasks = () => api.get('/tasks/')
export const createTask = (data: Record<string, unknown>) => api.post('/tasks/', data)

// --- 充电站 ---
export const getChargeStations = () => api.get('/charge-stations/')
export const createChargeStation = (data: Record<string, unknown>) =>
  api.post('/charge-stations/', data)

// --- 智能决策 ---
export const runDecision = (data: {
  vehicle_ids?: string[]
  task_ids?: string[]
  algorithm?: string
  use_demo?: boolean
  battery_capacity_kwh?: number
  initial_soc?: number
  soh?: number
}) => api.post('/decision/run', data)

export const getDecisionDemo = () => api.get('/decision/demo')

export const trainDecision = (data: { algorithm?: string; episodes?: number }) =>
  api.post('/decision/train', data)

export const getAlgorithms = () => api.get('/decision/algorithms')

// --- 电池退化 ---
export const getBatteryParams = () => api.get('/battery/params')

export const evaluateBatteryHealth = (data: Record<string, unknown>) =>
  api.post('/battery/health', data)

export const estimateSOC = (data: Record<string, unknown>) =>
  api.post('/battery/soc/estimate', data)

export const simulateSOC = (data: Record<string, unknown>) =>
  api.post('/battery/soc/simulate', data)

export const computeDegradationCost = (data: Record<string, unknown>) =>
  api.post('/battery/degradation-cost', data)

export const predictDegradation = (data: Record<string, unknown>) =>
  api.post('/battery/degradation/predict', data)

// --- 路径优化 ---
export const planRoute = (data: Record<string, unknown>) =>
  api.post('/routing/plan', data)

export const getRouteDemo = () => api.get('/routing/demo')

// --- 充电调度 ---
export const planCharging = (data: Record<string, unknown>) =>
  api.post('/scheduling/plan', data)

export const getChargeDemo = () => api.get('/scheduling/demo')

export const integratedPlan = (data: Record<string, unknown>) =>
  api.post('/scheduling/integrated', data)
