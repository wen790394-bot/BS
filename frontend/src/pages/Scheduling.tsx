import { useState } from 'react'
import {
  Button,
  Card,
  Descriptions,
  Space,
  Select,
  Table,
  Tag,
  Tabs,
  message,
} from 'antd'
import { PlayCircleOutlined, ThunderboltOutlined } from '@ant-design/icons'
import { getChargeDemo, getDecisionDemo, integratedPlan, runDecision as runDecisionApi } from '../api/client'

interface DecisionResult {
  route_id: string
  cost: number
  runtime: number
  route_data?: {
    algorithm: string
    feasible: boolean
    route: string[]
    cost_breakdown: {
      travel: number
      energy: number
      charge: number
      waiting: number
      degradation: number
      total: number
    }
    charge_plan?: {
      plans: Array<{
        station_id: string
        charge_kwh: number
        charge_cost: number
        waiting_cost: number
        total_cost: number
        soc_before: number
        soc_after: number
      }>
    }
    routes?: Array<{
      route: string[]
      feasible: boolean
      total_distance_km: number
      cost_breakdown: {
        travel: number
        energy: number
        charge: number
        waiting: number
        degradation: number
        total: number
      }
    }>
  }
}

interface ChargePlanResult {
  route: string[]
  charge_plan: {
    stations: string[]
    charge_amounts: number[]
    charge_times: number[]
    plans: Array<{
      station_id: string
      charge_kwh: number
      charge_time_min: number
      charge_price: number
      charge_cost: number
      waiting_cost: number
      total_cost: number
      soc_before: number
      soc_after: number
    }>
    cost: { charge: number; waiting: number; total: number }
    optimized: boolean
  }
  cost_breakdown: {
    travel: number
    energy: number
    charge: number
    waiting: number
    degradation: number
    total: number
  }
  feasible: boolean
  total_distance_km: number
  runtime_s: number
}

export default function Scheduling() {
  const [chargeResult, setChargeResult] = useState<ChargePlanResult | null>(null)
  const [decisionResult, setDecisionResult] = useState<DecisionResult | null>(null)
  const [algorithm, setAlgorithm] = useState('mamba_ppo')
  const [loading, setLoading] = useState(false)

  const runChargeDemo = async () => {
    setLoading(true)
    try {
      const res = await getChargeDemo()
      setChargeResult(res.data)
      message.success('路径+充电联合调度完成')
    } catch {
      message.error('充电调度失败，请确认后端已启动')
    } finally {
      setLoading(false)
    }
  }

  const runIntegrated = async () => {
    setLoading(true)
    try {
      const res = await integratedPlan({ use_demo: true, optimize_charging: true })
      setChargeResult(res.data)
      message.success('联合优化完成')
    } catch {
      message.error('联合调度失败')
    } finally {
      setLoading(false)
    }
  }

  const runDecisionDemo = async () => {
    setLoading(true)
    try {
      const res = await getDecisionDemo()
      setDecisionResult(res.data)
      message.success('Mamba-PPO 决策完成')
    } catch {
      message.error('决策失败，请确认后端已启动')
    } finally {
      setLoading(false)
    }
  }

  const runDecisionWithAlgo = async () => {
    setLoading(true)
    try {
      const res = await runDecisionApi({
        vehicle_ids: [],
        task_ids: [],
        algorithm,
        use_demo: true,
      })
      setDecisionResult(res.data)
      message.success('智能决策完成')
    } catch {
      message.error('决策失败')
    } finally {
      setLoading(false)
    }
  }

  const chargeColumns = [
    { title: '充电站', dataIndex: 'station_id', key: 'station_id' },
    { title: '充电量(kWh)', dataIndex: 'charge_kwh', key: 'charge_kwh' },
    { title: '时长(min)', dataIndex: 'charge_time_min', key: 'charge_time_min' },
    {
      title: 'SOC',
      key: 'soc',
      render: (_: unknown, r: { soc_before: number; soc_after: number }) =>
        `${r.soc_before} → ${r.soc_after}`,
    },
    { title: '电价(元/kWh)', dataIndex: 'charge_price', key: 'charge_price' },
    { title: '充电费(元)', dataIndex: 'charge_cost', key: 'charge_cost' },
    { title: '等待费(元)', dataIndex: 'waiting_cost', key: 'waiting_cost' },
    { title: '小计(元)', dataIndex: 'total_cost', key: 'total_cost' },
  ]

  const chargeTab = (
    <div>
      <Card title="充电调度 (min C_charge + C_waiting)" style={{ marginBottom: 16 }}>
        <Space>
          <Button
            type="primary"
            icon={<ThunderboltOutlined />}
            loading={loading}
            onClick={runChargeDemo}
          >
            运行演示算例
          </Button>
          <Button loading={loading} onClick={runIntegrated}>
            路径+充电联合优化
          </Button>
        </Space>
        <p style={{ marginTop: 12, color: '#999' }}>
          基于路径规划结果，决策充电站、充电量与充电时间，并计入 C_charge 与 C_waiting。
        </p>
      </Card>

      {chargeResult && (
        <>
          <Card title="联合调度结果" style={{ marginBottom: 16 }}>
            <Descriptions column={2} bordered size="small">
              <Descriptions.Item label="可行性">
                <Tag color={chargeResult.feasible ? 'success' : 'error'}>
                  {chargeResult.feasible ? '可行' : '不可行'}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="路线">
                {chargeResult.route.join(' → ')}
              </Descriptions.Item>
              <Descriptions.Item label="总距离">
                {chargeResult.total_distance_km} km
              </Descriptions.Item>
              <Descriptions.Item label="求解时间">
                {chargeResult.runtime_s} s
              </Descriptions.Item>
              <Descriptions.Item label="C_charge">
                ¥ {chargeResult.cost_breakdown.charge}
              </Descriptions.Item>
              <Descriptions.Item label="C_waiting">
                ¥ {chargeResult.cost_breakdown.waiting}
              </Descriptions.Item>
              <Descriptions.Item label="综合成本" span={2}>
                ¥ {chargeResult.cost_breakdown.total}
                （运输 {chargeResult.cost_breakdown.travel} + 能耗{' '}
                {chargeResult.cost_breakdown.energy} + 充电{' '}
                {chargeResult.cost_breakdown.charge} + 等待{' '}
                {chargeResult.cost_breakdown.waiting} + 退化{' '}
                {chargeResult.cost_breakdown.degradation}）
              </Descriptions.Item>
              {chargeResult.charge_plan?.optimized && (
                <Descriptions.Item label="充电优化" span={2}>
                  <Tag color="blue">已优化充电量</Tag>
                </Descriptions.Item>
              )}
            </Descriptions>
          </Card>

          {chargeResult.charge_plan?.plans?.length > 0 && (
            <Card title="充电计划明细">
              <Table
                rowKey="station_id"
                columns={chargeColumns}
                dataSource={chargeResult.charge_plan.plans}
                pagination={false}
                size="small"
              />
            </Card>
          )}
        </>
      )}
    </div>
  )

  const decisionTab = (
    <div>
      <Card title="Mamba-PPO 智能决策" style={{ marginBottom: 16 }}>
        <Space wrap>
          <Select
            value={algorithm}
            style={{ width: 200 }}
            onChange={setAlgorithm}
            options={[
              { value: 'mamba_ppo', label: 'Mamba-PPO' },
              { value: 'transformer_ppo', label: 'Transformer-PPO' },
              { value: 'ppo', label: 'PPO' },
            ]}
          />
          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            loading={loading}
            onClick={runDecisionDemo}
          >
            运行演示算例
          </Button>
          <Button loading={loading} onClick={runDecisionWithAlgo}>
            运行所选算法
          </Button>
        </Space>
        <p style={{ marginTop: 12, color: '#999' }}>
          基于强化学习序贯决策：Mamba 编码历史轨迹与能量特征，Actor 输出下一节点与充电策略，Critic 评估状态价值，PPO 优化综合成本。
        </p>
      </Card>
      {decisionResult && (
        <>
          <Card title="决策结果" style={{ marginBottom: 16 }}>
            <Descriptions column={2} bordered size="small">
              <Descriptions.Item label="路线ID">{decisionResult.route_id}</Descriptions.Item>
              <Descriptions.Item label="算法">
                {decisionResult.route_data?.algorithm ?? algorithm}
              </Descriptions.Item>
              <Descriptions.Item label="可行性">
                <Tag color={decisionResult.route_data?.feasible ? 'success' : 'error'}>
                  {decisionResult.route_data?.feasible ? '可行' : '不可行'}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="求解时间">{decisionResult.runtime} s</Descriptions.Item>
              <Descriptions.Item label="路线" span={2}>
                {(decisionResult.route_data?.route ?? []).join(' → ')}
              </Descriptions.Item>
              <Descriptions.Item label="综合成本" span={2}>
                ¥ {decisionResult.cost}
                {decisionResult.route_data?.cost_breakdown && (
                  <>
                    （运输 {decisionResult.route_data.cost_breakdown.travel} + 能耗{' '}
                    {decisionResult.route_data.cost_breakdown.energy} + 充电{' '}
                    {decisionResult.route_data.cost_breakdown.charge} + 等待{' '}
                    {decisionResult.route_data.cost_breakdown.waiting} + 退化{' '}
                    {decisionResult.route_data.cost_breakdown.degradation}）
                  </>
                )}
              </Descriptions.Item>
            </Descriptions>
          </Card>
          {decisionResult.route_data?.charge_plan?.plans &&
            decisionResult.route_data.charge_plan.plans.length > 0 && (
              <Card title="充电决策明细">
                <Table
                  rowKey="station_id"
                  columns={chargeColumns}
                  dataSource={decisionResult.route_data.charge_plan.plans}
                  pagination={false}
                  size="small"
                />
              </Card>
            )}
        </>
      )}
    </div>
  )

  return (
    <Tabs
      defaultActiveKey="charge"
      items={[
        { key: 'charge', label: '充电调度', children: chargeTab },
        { key: 'decision', label: '智能决策', children: decisionTab },
      ]}
    />
  )
}
