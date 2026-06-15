import { Layout, Menu, theme } from 'antd'
import {
  DashboardOutlined,
  CarOutlined,
  ShoppingOutlined,
  ThunderboltOutlined,
  RobotOutlined,
  LineChartOutlined,
  ExperimentOutlined,
  NodeIndexOutlined,
} from '@ant-design/icons'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'

const { Header, Sider, Content } = Layout

const menuItems = [
  { key: '/dashboard', icon: <DashboardOutlined />, label: '系统概览' },
  { key: '/vehicles', icon: <CarOutlined />, label: '车辆管理' },
  { key: '/tasks', icon: <ShoppingOutlined />, label: '订单管理' },
  { key: '/charge-stations', icon: <ThunderboltOutlined />, label: '充电站' },
  { key: '/routing', icon: <NodeIndexOutlined />, label: '路径优化' },
  { key: '/scheduling', icon: <RobotOutlined />, label: '智能调度' },
  { key: '/battery', icon: <ExperimentOutlined />, label: '电池退化' },
  { key: '/visualization', icon: <LineChartOutlined />, label: '结果可视化' },
]

export default function AppLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const { token: { colorBgContainer, borderRadiusLG } } = theme.useToken()

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider breakpoint="lg" collapsedWidth="0">
        <div style={{
          height: 64,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#fff',
          fontSize: 14,
          fontWeight: 600,
          padding: '0 12px',
          textAlign: 'center',
        }}>
          电动物流车调度系统
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout>
        <Header style={{ padding: '0 24px', background: colorBgContainer }}>
          <h2 style={{ margin: 0, lineHeight: '64px', fontSize: 18 }}>
            考虑电池退化成本的路径规划与充电调度一体化决策
          </h2>
        </Header>
        <Content style={{ margin: 24 }}>
          <div style={{
            padding: 24,
            minHeight: 360,
            background: colorBgContainer,
            borderRadius: borderRadiusLG,
          }}>
            <Outlet />
          </div>
        </Content>
      </Layout>
    </Layout>
  )
}
