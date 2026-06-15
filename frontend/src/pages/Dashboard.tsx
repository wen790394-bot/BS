import { Card, Col, Row, Statistic } from 'antd'
import {
  CarOutlined,
  ShoppingOutlined,
  ThunderboltOutlined,
  DollarOutlined,
} from '@ant-design/icons'

export default function Dashboard() {
  return (
    <div>
      <h3 style={{ marginBottom: 24 }}>系统概览</h3>
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic title="车辆数量" value={0} prefix={<CarOutlined />} />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic title="待配送订单" value={0} prefix={<ShoppingOutlined />} />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic title="充电站" value={0} prefix={<ThunderboltOutlined />} />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="综合运营成本"
              value={0}
              prefix={<DollarOutlined />}
              suffix="元"
            />
          </Card>
        </Col>
      </Row>
      <Card style={{ marginTop: 24 }} title="成本构成">
        <p>C_total = C_travel + C_energy + C_charge + C_degradation</p>
        <p style={{ color: '#999' }}>待接入调度结果数据后展示图表</p>
      </Card>
    </div>
  )
}
