import { useEffect, useState } from 'react'
import { Button, Table, Space, message } from 'antd'
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons'
import { getChargeStations } from '../api/client'

interface Station {
  station_id: string
  location: string | null
  price: number
  queue: number
}

export default function ChargeStations() {
  const [data, setData] = useState<Station[]>([])
  const [loading, setLoading] = useState(false)

  const fetchData = async () => {
    setLoading(true)
    try {
      const res = await getChargeStations()
      setData(res.data)
    } catch {
      message.error('获取充电站列表失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchData() }, [])

  const columns = [
    { title: '充电站编号', dataIndex: 'station_id', key: 'station_id' },
    { title: '位置', dataIndex: 'location', key: 'location' },
    { title: '电价 (元/kWh)', dataIndex: 'price', key: 'price' },
    { title: '排队车辆', dataIndex: 'queue', key: 'queue' },
  ]

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />}>新增充电站</Button>
        <Button icon={<ReloadOutlined />} onClick={fetchData}>刷新</Button>
      </Space>
      <Table rowKey="station_id" columns={columns} dataSource={data} loading={loading} />
    </div>
  )
}
