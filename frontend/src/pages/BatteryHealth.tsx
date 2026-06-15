import { useEffect, useState } from 'react'
import {
  Button,
  Card,
  Col,
  Descriptions,
  Form,
  InputNumber,
  Row,
  Space,
  Tabs,
  message,
} from 'antd'
import ReactECharts from 'echarts-for-react'
import {
  evaluateBatteryHealth,
  estimateSOC,
  predictDegradation,
  getBatteryParams,
} from '../api/client'

interface HealthResult {
  soh_t: number
  delta_soh: number
  degradation_rate: number
  rul_t: number
  cycle_degradation: number
  calendar_degradation: number
  degradation_cost: number
}

export default function BatteryHealth() {
  const [healthForm] = Form.useForm()
  const [socForm] = Form.useForm()
  const [healthResult, setHealthResult] = useState<HealthResult | null>(null)
  const [socResult, setSocResult] = useState<Record<string, number> | null>(null)
  const [trajectory, setTrajectory] = useState<{ cycle: number; soh: number }[]>([])
  const [loading, setLoading] = useState(false)
  const [batteryCost, setBatteryCost] = useState(80000)

  useEffect(() => {
    getBatteryParams()
      .then((res) => setBatteryCost(res.data.battery_cost))
      .catch(() => {})
  }, [])

  const handleHealthEval = async () => {
    const values = await healthForm.validateFields()
    setLoading(true)
    try {
      const res = await evaluateBatteryHealth({ ...values, battery_cost: batteryCost })
      setHealthResult(res.data)
      message.success('健康评估完成')
    } catch {
      message.error('评估失败，请确认后端已启动')
    } finally {
      setLoading(false)
    }
  }

  const handleSocEstimate = async () => {
    const values = await socForm.validateFields()
    setLoading(true)
    try {
      const res = await estimateSOC(values)
      setSocResult(res.data)
      message.success('SOC 估计完成')
    } catch {
      message.error('SOC 估计失败')
    } finally {
      setLoading(false)
    }
  }

  const handlePredict = async () => {
    const values = healthForm.getFieldsValue()
    setLoading(true)
    try {
      const res = await predictDegradation({
        soh_init: values.soh ?? 1.0,
        dod: values.dod ?? 0.8,
        soc: values.soc ?? 0.5,
        temperature: values.temperature ?? 25,
        cycles: 200,
      })
      setTrajectory(res.data.trajectory)
    } catch {
      message.error('退化预测失败')
    } finally {
      setLoading(false)
    }
  }

  const chartOption = {
    title: { text: 'SOH 退化轨迹预测', left: 'center' },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', name: '等效循环', data: trajectory.map((t) => t.cycle) },
    yAxis: { type: 'value', name: 'SOH', min: 0.75, max: 1.0 },
    series: [{
      type: 'line',
      data: trajectory.map((t) => t.soh),
      smooth: true,
      markLine: {
        data: [{ yAxis: 0.8, name: 'EOL (80%)' }],
        lineStyle: { color: '#ff4d4f', type: 'dashed' },
      },
    }],
  }

  return (
    <div>
      <Tabs
        items={[
          {
            key: 'health',
            label: '健康评估',
            children: (
              <Row gutter={24}>
                <Col xs={24} lg={10}>
                  <Card title="工况输入">
                    <Form
                      form={healthForm}
                      layout="vertical"
                      initialValues={{ soc: 0.6, soh: 0.95, dod: 0.3, temperature: 25, duration_hours: 0 }}
                    >
                      <Form.Item name="soc" label="当前 SOC" rules={[{ required: true }]}>
                        <InputNumber min={0} max={1} step={0.01} style={{ width: '100%' }} />
                      </Form.Item>
                      <Form.Item name="soh" label="当前 SOH" rules={[{ required: true }]}>
                        <InputNumber min={0} max={1} step={0.01} style={{ width: '100%' }} />
                      </Form.Item>
                      <Form.Item name="dod" label="放电深度 DOD" rules={[{ required: true }]}>
                        <InputNumber min={0} max={1} step={0.01} style={{ width: '100%' }} />
                      </Form.Item>
                      <Form.Item name="temperature" label="温度 (°C)">
                        <InputNumber style={{ width: '100%' }} />
                      </Form.Item>
                      <Form.Item name="duration_hours" label="静置时长 (h)">
                        <InputNumber min={0} style={{ width: '100%' }} />
                      </Form.Item>
                      <Space>
                        <Button type="primary" loading={loading} onClick={handleHealthEval}>
                          评估退化
                        </Button>
                        <Button loading={loading} onClick={handlePredict}>
                          预测轨迹
                        </Button>
                      </Space>
                    </Form>
                  </Card>
                </Col>
                <Col xs={24} lg={14}>
                  {healthResult && (
                    <Card title="评估结果" style={{ marginBottom: 16 }}>
                      <Descriptions column={2} bordered size="small">
                        <Descriptions.Item label="更新 SOH">{healthResult.soh_t}</Descriptions.Item>
                        <Descriptions.Item label="SOH 衰减 ΔSOH">{healthResult.delta_soh}</Descriptions.Item>
                        <Descriptions.Item label="循环老化分量">{healthResult.cycle_degradation}</Descriptions.Item>
                        <Descriptions.Item label="日历老化分量">{healthResult.calendar_degradation}</Descriptions.Item>
                        <Descriptions.Item label="退化率 (每EFC)">{healthResult.degradation_rate}</Descriptions.Item>
                        <Descriptions.Item label="剩余寿命 RUL">{healthResult.rul_t} 次EFC</Descriptions.Item>
                        <Descriptions.Item label="退化成本" span={2}>
                          ¥ {healthResult.degradation_cost?.toFixed(2)} (C_deg = ΔSOH × C_battery)
                        </Descriptions.Item>
                      </Descriptions>
                    </Card>
                  )}
                  {trajectory.length > 0 && (
                    <Card title="SOH 退化曲线">
                      <ReactECharts option={chartOption} style={{ height: 350 }} />
                    </Card>
                  )}
                </Col>
              </Row>
            ),
          },
          {
            key: 'soc',
            label: 'SOC 估计 (ECM+EKF)',
            children: (
              <Row gutter={24}>
                <Col xs={24} lg={10}>
                  <Card title="测量输入">
                    <Form
                      form={socForm}
                      layout="vertical"
                      initialValues={{ current: 50, voltage: 360, temperature: 25, dt: 1, soc_init: 0.8 }}
                    >
                      <Form.Item name="current" label="电流 (A)" rules={[{ required: true }]}>
                        <InputNumber style={{ width: '100%' }} />
                      </Form.Item>
                      <Form.Item name="voltage" label="端电压 (V)" rules={[{ required: true }]}>
                        <InputNumber style={{ width: '100%' }} />
                      </Form.Item>
                      <Form.Item name="temperature" label="温度 (°C)">
                        <InputNumber style={{ width: '100%' }} />
                      </Form.Item>
                      <Form.Item name="dt" label="采样间隔 (s)">
                        <InputNumber min={0.1} style={{ width: '100%' }} />
                      </Form.Item>
                      <Form.Item name="soc_init" label="初始 SOC 猜测">
                        <InputNumber min={0} max={1} step={0.01} style={{ width: '100%' }} />
                      </Form.Item>
                      <Button type="primary" loading={loading} onClick={handleSocEstimate}>
                        EKF 估计
                      </Button>
                    </Form>
                  </Card>
                </Col>
                <Col xs={24} lg={14}>
                  {socResult && (
                    <Card title="EKF 估计结果">
                      <Descriptions column={2} bordered size="small">
                        <Descriptions.Item label="估计 SOC">{socResult.soc}</Descriptions.Item>
                        <Descriptions.Item label="极化电压 V1">{socResult.v1} V</Descriptions.Item>
                        <Descriptions.Item label="预测端电压">{socResult.voltage_predicted} V</Descriptions.Item>
                        <Descriptions.Item label="实测端电压">{socResult.voltage_measured} V</Descriptions.Item>
                        <Descriptions.Item label="SOC 不确定度">{socResult.soc_uncertainty}</Descriptions.Item>
                      </Descriptions>
                    </Card>
                  )}
                </Col>
              </Row>
            ),
          },
        ]}
      />
    </div>
  )
}
