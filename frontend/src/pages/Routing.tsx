import { useState } from 'react'
import {
  Button,
  Card,
  Col,
  Descriptions,
  Form,
  InputNumber,
  Row,
  Select,
  Space,
  Table,
  Tag,
  message,
} from 'antd'
import { PlayCircleOutlined } from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import { getRouteDemo, planRoute } from '../api/client'

interface RouteResult {
  route_id: string
  route: string[]
  feasible: boolean
  violation: string
  total_distance_km: number
  total_time_min: number
  total_energy_kwh: number
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
    optimized: boolean
  }
  legs: Array<{
    from: string
    to: string
    distance_km: number
    travel_time_min: number
    energy_kwh: number
    soc_before: number
    soc_after: number
  }>
  soc_trajectory: Array<{ node_id: string; soc: number; time_min: number }>
  node_positions: Record<string, { x: number; y: number; type: string }>
  runtime_s: number
  method: string
}

export default function Routing() {
  const [form] = Form.useForm()
  const [result, setResult] = useState<RouteResult | null>(null)
  const [loading, setLoading] = useState(false)

  const runDemo = async () => {
    setLoading(true)
    try {
      const res = await getRouteDemo()
      setResult(res.data)
      message.success('路径优化演示完成')
    } catch {
      message.error('路径规划失败，请确认后端已启动')
    } finally {
      setLoading(false)
    }
  }

  const runWithParams = async () => {
    const values = await form.validateFields()
    setLoading(true)
    try {
      const res = await planRoute({ use_demo: true, ...values })
      setResult(res.data)
      message.success('路径优化完成')
    } catch {
      message.error('路径规划失败')
    } finally {
      setLoading(false)
    }
  }

  const mapOption = result
    ? (() => {
        const positions = result.node_positions
        const route = result.route
        const typeColor: Record<string, string> = {
          depot: '#1677ff',
          task: '#52c41a',
          charge: '#faad14',
        }
        const scatterData = Object.entries(positions).map(([id, pos]) => ({
          name: id,
          value: [pos.x, pos.y],
          itemStyle: { color: typeColor[pos.type] ?? '#999' },
        }))
        const lineData = route
          .map((id) => positions[id])
          .filter(Boolean)
          .map((p) => [p.x, p.y])
        return {
          tooltip: { trigger: 'item', formatter: (p: { name: string; value: number[] }) => `${p.name}: (${p.value[0]}, ${p.value[1]}) km` },
          xAxis: { name: 'X (km)', scale: true },
          yAxis: { name: 'Y (km)', scale: true },
          series: [
            {
              type: 'scatter',
              symbolSize: 14,
              data: scatterData,
              label: { show: true, position: 'top', formatter: '{b}' },
            },
            {
              type: 'line',
              data: lineData,
              lineStyle: { color: '#1677ff', width: 2 },
              symbol: 'none',
            },
          ],
        }
      })()
    : {}

  const socOption = result?.soc_trajectory?.length
    ? {
        tooltip: { trigger: 'axis' },
        xAxis: {
          type: 'category',
          name: '节点',
          data: result.soc_trajectory.map((p) => p.node_id),
        },
        yAxis: { type: 'value', name: 'SOC', min: 0, max: 1 },
        series: [
          {
            type: 'line',
            data: result.soc_trajectory.map((p) => p.soc),
            smooth: true,
            areaStyle: { opacity: 0.15 },
          },
        ],
      }
    : {}

  const costOption = result
    ? {
        tooltip: { trigger: 'item', formatter: '{b}: ¥{c}' },
        series: [
          {
            type: 'pie',
            radius: '60%',
            data: [
              { value: result.cost_breakdown.travel, name: '运输成本' },
              { value: result.cost_breakdown.energy, name: '能耗成本' },
              { value: result.cost_breakdown.charge, name: '充电成本' },
              { value: result.cost_breakdown.waiting, name: '等待成本' },
              { value: result.cost_breakdown.degradation, name: '退化成本' },
            ].filter((d) => d.value > 0),
          },
        ],
      }
    : {}

  const legColumns = [
    { title: '起点', dataIndex: 'from', key: 'from' },
    { title: '终点', dataIndex: 'to', key: 'to' },
    { title: '距离(km)', dataIndex: 'distance_km', key: 'distance_km' },
    { title: '时间(min)', dataIndex: 'travel_time_min', key: 'travel_time_min' },
    { title: '能耗(kWh)', dataIndex: 'energy_kwh', key: 'energy_kwh' },
    {
      title: 'SOC',
      key: 'soc',
      render: (_: unknown, r: { soc_before: number; soc_after: number }) =>
        `${r.soc_before.toFixed(3)} → ${r.soc_after.toFixed(3)}`,
    },
  ]

  return (
    <div>
      <Card title="EVRPTW 路径优化" style={{ marginBottom: 16 }}>
        <Form
          form={form}
          layout="inline"
          initialValues={{
            battery_capacity_kwh: 60,
            initial_soc: 0.25,
            soh: 0.95,
            speed_kmh: 40,
            temperature: 25,
            method: 'insertion_2opt',
          }}
        >
          <Form.Item name="battery_capacity_kwh" label="电池容量(kWh)">
            <InputNumber min={10} max={200} />
          </Form.Item>
          <Form.Item name="initial_soc" label="初始 SOC">
            <InputNumber min={0.1} max={1} step={0.05} />
          </Form.Item>
          <Form.Item name="soh" label="SOH">
            <InputNumber min={0.5} max={1} step={0.01} />
          </Form.Item>
          <Form.Item name="speed_kmh" label="车速(km/h)">
            <InputNumber min={20} max={80} />
          </Form.Item>
          <Form.Item name="method" label="算法">
            <Select
              style={{ width: 150 }}
              options={[
                { value: 'insertion_2opt', label: 'Insertion + 2-opt' },
                { value: 'alns', label: 'ALNS' },
              ]}
            />
          </Form.Item>
        </Form>
        <Space style={{ marginTop: 16 }}>
          <Button type="primary" icon={<PlayCircleOutlined />} loading={loading} onClick={runDemo}>
            运行演示算例
          </Button>
          <Button loading={loading} onClick={runWithParams}>
            自定义参数运行
          </Button>
        </Space>
        <p style={{ marginTop: 12, color: '#999' }}>
          约束：时间窗、SOC 下限、充电站补能。综合成本 C_total = C_travel + C_energy + C_charge + C_waiting + C_degradation。
        </p>
      </Card>

      {result && (
        <>
          <Card title="规划结果" style={{ marginBottom: 16 }}>
            <Descriptions column={2} bordered size="small">
              <Descriptions.Item label="可行性">
                <Tag color={result.feasible ? 'success' : 'error'}>
                  {result.feasible ? '可行' : '不可行'}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="算法">{result.method}</Descriptions.Item>
              <Descriptions.Item label="路线" span={2}>
                {result.route.join(' → ')}
              </Descriptions.Item>
              <Descriptions.Item label="总距离">{result.total_distance_km} km</Descriptions.Item>
              <Descriptions.Item label="总时间">{result.total_time_min} min</Descriptions.Item>
              <Descriptions.Item label="总能耗">{result.total_energy_kwh} kWh</Descriptions.Item>
              <Descriptions.Item label="求解时间">{result.runtime_s} s</Descriptions.Item>
              <Descriptions.Item label="综合成本" span={2}>
                ¥ {result.cost_breakdown.total}
                （运输 {result.cost_breakdown.travel} + 能耗 {result.cost_breakdown.energy} + 充电{' '}
                {result.cost_breakdown.charge} + 等待 {result.cost_breakdown.waiting} + 退化{' '}
                {result.cost_breakdown.degradation}）
              </Descriptions.Item>
              {result.violation && (
                <Descriptions.Item label="约束违反" span={2}>
                  <Tag color="warning">{result.violation}</Tag>
                </Descriptions.Item>
              )}
            </Descriptions>
          </Card>

          <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
            <Col xs={24} lg={12}>
              <Card title="路径地图">
                <ReactECharts option={mapOption} style={{ height: 320 }} />
              </Card>
            </Col>
            <Col xs={24} lg={12}>
              <Card title="SOC 轨迹">
                <ReactECharts option={socOption} style={{ height: 320 }} />
              </Card>
            </Col>
            <Col xs={24} lg={12}>
              <Card title="成本构成">
                <ReactECharts option={costOption} style={{ height: 320 }} />
              </Card>
            </Col>
          </Row>

          <Card title="路段明细">
            <Table
              rowKey={(r) => `${r.from}-${r.to}`}
              columns={legColumns}
              dataSource={result.legs}
              pagination={false}
              size="small"
            />
          </Card>
        </>
      )}
    </div>
  )
}
