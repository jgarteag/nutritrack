import { useState, useEffect } from 'react'
import { LineChart, Line, XAxis, YAxis, ResponsiveContainer, Area, CartesianGrid } from 'recharts'
import { getWeightHistory, addWeight } from '../api'

export default function WeightTracker() {
  const [history, setHistory] = useState([])
  const [weight, setWeight] = useState('')
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    loadHistory()
  }, [])

  const loadHistory = async () => {
    try {
      const data = await getWeightHistory(30)
      const records = (data.records || []).map((r) => ({
        date: formatShortDate(r.date),
        weight: r.weight_kg,
      })).reverse()
      setHistory(records)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    const w = parseFloat(weight)
    if (!w || w < 30 || w > 300) {
      setError('Peso debe estar entre 30-300 kg')
      return
    }

    setSubmitting(true)
    setError('')
    setResult(null)

    try {
      const res = await addWeight(w)
      setResult(res)
      setWeight('')
      await loadHistory()
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  const handleAcceptGoal = () => {
    setResult(null)
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
        <h1 className="text-xl font-bold text-white">Peso</h1>
        <p className="text-secondary text-sm">Seguimiento corporal</p>
      </div>

      {/* Chart */}
      {history.length > 1 && (
        <div className="bg-dark-card border border-dark-border rounded-2xl p-4">
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={history} margin={{ top: 10, right: 10, left: -10, bottom: 5 }}>
              <defs>
                <linearGradient id="weightGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#2a2a5a" vertical={false} />
              <XAxis
                dataKey="date"
                axisLine={false}
                tickLine={false}
                tick={{ fill: '#94a3b8', fontSize: 11 }}
              />
              <YAxis
                axisLine={false}
                tickLine={false}
                tick={{ fill: '#94a3b8', fontSize: 11 }}
                domain={['dataMin - 2', 'dataMax + 2']}
                width={40}
              />
              <Area
                type="monotone"
                dataKey="weight"
                stroke="none"
                fill="url(#weightGradient)"
              />
              <Line
                type="monotone"
                dataKey="weight"
                stroke="#10b981"
                strokeWidth={2.5}
                dot={{ fill: '#10b981', r: 3 }}
                activeDot={{ r: 5 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {history.length <= 1 && (
        <div className="bg-dark-card border border-dark-border rounded-2xl p-8 text-center">
          <p className="text-secondary text-sm">Registra tu peso para ver el progreso</p>
        </div>
      )}

      {/* Weight input form */}
      <form onSubmit={handleSubmit} className="space-y-3">
        <div className="flex gap-3">
          <input
            type="number"
            step="0.1"
            value={weight}
            onChange={(e) => { setWeight(e.target.value); setError('') }}
            placeholder="Peso en kg"
            className="flex-1 px-4 py-3 bg-dark-card border border-dark-border rounded-xl text-white placeholder-secondary focus:border-accent transition-colors"
          />
          <button
            type="submit"
            disabled={submitting}
            className="px-6 py-3 bg-accent text-white font-semibold rounded-xl hover:bg-emerald-600 transition-colors disabled:opacity-50"
          >
            {submitting ? '...' : 'Registrar'}
          </button>
        </div>
      </form>

      {error && (
        <p className="text-danger text-sm text-center">{error}</p>
      )}

      {/* Result after submitting weight */}
      {result && (
        <div className="bg-dark-card border border-accent/30 rounded-2xl p-6 space-y-4">
          <h3 className="text-white font-semibold text-center">Actualización</h3>
          <div className="grid grid-cols-2 gap-3">
            <div className="text-center">
              <p className="text-secondary text-xs">Nuevo TDEE</p>
              <p className="text-white font-bold">{result.new_tdee} kcal</p>
            </div>
            <div className="text-center">
              <p className="text-secondary text-xs">Meta sugerida</p>
              <p className="text-accent font-bold">{result.suggested_goal} kcal</p>
            </div>
          </div>
          <div className="flex gap-3">
            <button
              onClick={handleAcceptGoal}
              className="flex-1 py-2.5 bg-accent text-white rounded-xl text-sm font-medium hover:bg-emerald-600 transition-colors"
            >
              Aceptar
            </button>
            <button
              onClick={() => setResult(null)}
              className="flex-1 py-2.5 border border-dark-border text-secondary rounded-xl text-sm hover:text-white transition-colors"
            >
              Mantener actual
            </button>
          </div>
        </div>
      )}

      {/* Current weight */}
      {history.length > 0 && (
        <div className="text-center">
          <p className="text-secondary text-xs">Peso actual</p>
          <p className="text-white font-bold text-2xl">{history[history.length - 1]?.weight} kg</p>
        </div>
      )}
    </div>
  )
}

function formatShortDate(dateStr) {
  const date = new Date(dateStr + 'T12:00:00')
  return `${date.getDate()}/${date.getMonth() + 1}`
}
