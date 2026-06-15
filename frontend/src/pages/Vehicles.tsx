import { useEffect, useState } from 'react'
import { Button, Table, Space, message } from 'antd'
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons'
import { getVehicles } from '../api/client'

interface Vehicle {
  vehicle_id: string
  capacity: number
  soc: number
  soh: number
  location: string | null
}

export default function Vehicles() {
  const [data, setData] = useState<Vehicle[]>([])
  const [loading, setLoading] = useState(false)

  const fetchData = async () => {
    setLoading(true)
    try {
      const res = await getVehicles()
      setData(res.data)
    } catch {
      message.error('获取车辆列表失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchData() }, [])

  const columns = [
    { title: '车辆编号', dataIndex: 'vehicle_id', key: 'vehicle_id' },
    { title: '电池容量 (kWh)', dataIndex: 'capacity', key: 'capacity' },
    { title: 'SOC', dataIndex: 'soc', key: 'soc', render: (v: number) => `${(v * 100).toFixed(1)}%` },
    { title: 'SOH', dataIndex: 'soh', key: 'soh', render: (v: number) => `${(v * 100).toFixed(1)}%` },
    { title: '当前位置', dataIndex: 'location', key: 'location' },
  ]

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />}>新增车辆</Button>
        <Button icon={<ReloadOutlined />} onClick={fetchData}>刷新</Button>
      </Space>
      <Table rowKey="vehicle_id" columns={columns} dataSource={data} loading={loading} />
    </div>
  )
}
