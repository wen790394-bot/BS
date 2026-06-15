import { useEffect, useState } from 'react'
import { Button, Table, Space, message } from 'antd'
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons'
import { getTasks } from '../api/client'

interface Task {
  task_id: string
  location: string
  demand: number
  service_time: number
  time_window_start: number | null
  time_window_end: number | null
}

export default function Tasks() {
  const [data, setData] = useState<Task[]>([])
  const [loading, setLoading] = useState(false)

  const fetchData = async () => {
    setLoading(true)
    try {
      const res = await getTasks()
      setData(res.data)
    } catch {
      message.error('获取订单列表失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchData() }, [])

  const columns = [
    { title: '订单编号', dataIndex: 'task_id', key: 'task_id' },
    { title: '配送点', dataIndex: 'location', key: 'location' },
    { title: '需求量', dataIndex: 'demand', key: 'demand' },
    { title: '服务时间 (min)', dataIndex: 'service_time', key: 'service_time' },
    { title: '时间窗', key: 'time_window', render: (_: unknown, r: Task) =>
      r.time_window_start != null ? `${r.time_window_start} - ${r.time_window_end}` : '-'
    },
  ]

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />}>新增订单</Button>
        <Button icon={<ReloadOutlined />} onClick={fetchData}>刷新</Button>
      </Space>
      <Table rowKey="task_id" columns={columns} dataSource={data} loading={loading} />
    </div>
  )
}
