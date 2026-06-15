import { Card, Col, Row } from 'antd'
import ReactECharts from 'echarts-for-react'

const placeholderOption = (title: string) => ({
  title: { text: title, left: 'center', textStyle: { color: '#999', fontSize: 14 } },
  xAxis: { type: 'category', data: [] },
  yAxis: { type: 'value' },
  series: [{ type: 'line', data: [] }],
})

export default function Visualization() {
  return (
    <div>
      <h3 style={{ marginBottom: 24 }}>结果可视化</h3>
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card title="路径轨迹">
            <div style={{ height: 300, background: '#f5f5f5', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#999' }}>
              Leaflet 地图（待接入路线数据）
            </div>
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="SOC 曲线">
            <ReactECharts option={placeholderOption('SOC 变化')} style={{ height: 300 }} />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="SOH 曲线">
            <ReactECharts option={placeholderOption('SOH 退化')} style={{ height: 300 }} />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="成本构成">
            <ReactECharts
              option={{
                tooltip: { trigger: 'item' },
                series: [{
                  type: 'pie',
                  radius: '60%',
                  data: [
                    { value: 0, name: '运输成本' },
                    { value: 0, name: '能耗成本' },
                    { value: 0, name: '充电成本' },
                    { value: 0, name: '退化成本' },
                  ],
                }],
              }}
              style={{ height: 300 }}
            />
          </Card>
        </Col>
      </Row>
    </div>
  )
}
