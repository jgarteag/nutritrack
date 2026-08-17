import { useState, useEffect } from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, ReferenceLine, ResponsiveContainer, Cell } from 'recharts'
import { getWeeklySummary } from '../api'

const DAY_LABELS = ['dom', 'lun', 'mar', 'mié', 'jue', 'vie', 'sáb']

export default function WeeklyChart() {
  const [data, setData] = useState([])
  const [goal, setGoal] = useState(2000)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    loadWeekData()
  }, [])

  const loadWeekData = async () => {
    try {
      const startDate = getWeekStart()
      const result = await getWeeklySummary(startDate)
      const summaries = result.summaries || []

      if (summaries.length > 0 && summaries[0].goal) {
        setGoal(summaries[0].goal.target_calories || summaries[0].goal)
      }

      const chartData = summaries.map((s) => {
        const date = new Date(s.date + 'T12:00:00')
        const dayIndex = date.getDay()
        return {
          day: DAY_LABELS[dayIndex],
          calories: s.total_calories || 0,
          date: s.date,
          overGoal: (s.total_calories || 0) > (typeof s.goal === 'object' ? s.goal.target_calories : s.goal || goal),
        }
      })

      setData(chartData)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-secondary animate-pulse">Cargando...</div>
      </div>
    )
  }

  return (
    <div className="px-4 pt-6 space-y-6">
      <div className="text-center">
        <h1 className="text-xl font-bold text-white">Resumen semanal</h1>
        <p className="text-secondary text-sm">Últimos 7 días</p>
      </div>

      {error && (
        <p className="text-danger text-sm text-center">{error}</p>
      )}

      <div className="bg-dark-card border border-dark-border rounded-2xl p-4">
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={data} margin={{ top: 20, right: 10, left: -10, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#2a2a5a" vertical={false} />
            <XAxis
              dataKey="day"
              axisLine={false}
              tickLine={false}
              tick={{ fill: '#94a3b8', fontSize: 12 }}
            />
            <YAxis
              axisLine={false}
              tickLine={false}
              tick={{ fill: '#94a3b8', fontSize: 11 }}
              width={40}
            />
            <ReferenceLine
              y={goal}
              stroke="#f59e0b"
              strokeDasharray="4 4"
              strokeWidth={1.5}
              label={{ value: 'Meta', fill: '#f59e0b', fontSize: 11, position: 'right' }}
            />
            <Bar dataKey="calories" radius={[6, 6, 0, 0]} maxBarSize={36}>
              {data.map((entry, index) => (
                <Cell
                  key={index}
                  fill={entry.overGoal ? '#ef4444' : '#10b981'}
                  fillOpacity={0.85}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Stats summary */}
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-dark-card border border-dark-border rounded-xl p-4 text-center">
          <p className="text-secondary text-xs">Promedio diario</p>
          <p className="text-white font-bold text-lg mt-1">
            {data.length > 0
              ? Math.round(data.reduce((sum, d) => sum + d.calories, 0) / data.length)
              : 0} kcal
          </p>
        </div>
        <div className="bg-dark-card border border-dark-border rounded-xl p-4 text-center">
          <p className="text-secondary text-xs">Días en meta</p>
          <p className="text-accent font-bold text-lg mt-1">
            {data.filter((d) => !d.overGoal && d.calories > 0).length} / {data.length}
          </p>
        </div>
      </div>
    </div>
  )
}

function getWeekStart() {
  const now = new Date()
  const day = now.getDay()
  const diff = now.getDate() - day + (day === 0 ? -6 : 1)
  const monday = new Date(now.setDate(diff))
  return monday.toISOString().split('T')[0]
}
