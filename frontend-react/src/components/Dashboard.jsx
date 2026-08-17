import { useState, useEffect, useRef } from 'react'
import confetti from 'canvas-confetti'
import { getDailySummary, addFoodEntry, deleteEntry } from '../api'
import ProgressRing from './ProgressRing'

export default function Dashboard() {
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const fileInputRef = useRef(null)
  const confettiFired = useRef(false)

  const today = new Date().toISOString().split('T')[0]

  useEffect(() => {
    loadSummary()
  }, [])

  useEffect(() => {
    if (summary && !confettiFired.current) {
      const { total_calories, goal } = summary
      if (goal && total_calories >= goal.target_calories * 0.95 && total_calories <= goal.target_calories) {
        confettiFired.current = true
        confetti({
          particleCount: 100,
          spread: 70,
          origin: { y: 0.6 },
          colors: ['#10b981', '#34d399', '#6ee7b7'],
        })
      }
    }
  }, [summary])

  const loadSummary = async () => {
    try {
      const data = await getDailySummary(today)
      setSummary(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleCapture = () => {
    fileInputRef.current?.click()
  }

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return

    setUploading(true)
    setError('')

    try {
      const base64 = await fileToBase64(file)
      const result = await addFoodEntry(base64)
      if (result.daily_summary) {
        setSummary(result.daily_summary)
      } else {
        await loadSummary()
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setUploading(false)
      e.target.value = ''
    }
  }

  const handleDelete = async (entryId) => {
    try {
      await deleteEntry(entryId, today)
      await loadSummary()
    } catch (err) {
      setError(err.message)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-secondary animate-pulse">Cargando...</div>
      </div>
    )
  }

  const totalCalories = summary?.total_calories || 0
  const goalCalories = summary?.goal?.target_calories || 2000
  const entries = summary?.entries || []

  return (
    <div className="px-4 pt-6 space-y-6">
      {/* Header */}
      <div className="text-center">
        <h1 className="text-xl font-bold text-white">Hoy</h1>
        <p className="text-secondary text-sm">{formatDate(today)}</p>
      </div>

      {/* Progress Ring */}
      <div className="flex justify-center">
        <ProgressRing consumed={totalCalories} goal={goalCalories} />
      </div>

      {/* Macros Summary */}
      {entries.length > 0 && (
        <div className="grid grid-cols-3 gap-3">
          <div className="bg-dark-card border border-dark-border rounded-xl p-3 text-center">
            <p className="text-accent font-bold text-lg">
              {Math.round(entries.reduce((sum, e) => sum + (e.protein_g || 0), 0))}g
            </p>
            <p className="text-secondary text-xs">Proteína</p>
          </div>
          <div className="bg-dark-card border border-dark-border rounded-xl p-3 text-center">
            <p className="text-warning font-bold text-lg">
              {Math.round(entries.reduce((sum, e) => sum + (e.carbs_g || 0), 0))}g
            </p>
            <p className="text-secondary text-xs">Carbos</p>
          </div>
          <div className="bg-dark-card border border-dark-border rounded-xl p-3 text-center">
            <p className="text-danger font-bold text-lg">
              {Math.round(entries.reduce((sum, e) => sum + (e.fat_g || 0), 0))}g
            </p>
            <p className="text-secondary text-xs">Grasa</p>
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <p className="text-danger text-sm text-center">{error}</p>
      )}

      {/* Entries */}
      <div className="space-y-3">
        <h2 className="text-white font-semibold text-sm">Comidas de hoy</h2>
        {entries.length === 0 ? (
          <p className="text-secondary text-sm text-center py-4">
            Sin registros aún. Toma una foto para empezar.
          </p>
        ) : (
          entries.map((entry) => (
            <div
              key={entry.entry_id}
              className="bg-dark-card border border-dark-border rounded-xl p-4 flex items-center justify-between"
            >
              <div className="flex-1 min-w-0">
                <p className="text-white text-sm font-medium truncate">
                  {entry.food_name || entry.description || 'Alimento'}
                </p>
                <p className="text-secondary text-xs">
                  {entry.calories} kcal
                  {entry.protein_g > 0 && ` · ${entry.protein_g}g prot`}
                  {entry.carbs_g > 0 && ` · ${entry.carbs_g}g carbs`}
                  {entry.fat_g > 0 && ` · ${entry.fat_g}g grasa`}
                </p>
              </div>
              <button
                onClick={() => handleDelete(entry.entry_id)}
                className="ml-3 w-8 h-8 flex items-center justify-center text-secondary hover:text-danger transition-colors rounded-lg hover:bg-danger/10"
                aria-label="Eliminar entrada"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>
          ))
        )}
      </div>

      {/* Upload overlay */}
      {uploading && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-dark-card border border-dark-border rounded-2xl p-8 text-center">
            <div className="animate-spin w-8 h-8 border-2 border-accent border-t-transparent rounded-full mx-auto mb-4" />
            <p className="text-white">Analizando imagen...</p>
            <p className="text-secondary text-sm mt-1">La IA está identificando los alimentos</p>
          </div>
        </div>
      )}

      {/* FAB Camera Button */}
      <div className="fixed bottom-24 left-1/2 -translate-x-1/2 z-40">
        <button
          onClick={handleCapture}
          disabled={uploading}
          className="w-14 h-14 bg-accent rounded-full flex items-center justify-center shadow-lg shadow-accent/30 hover:bg-emerald-600 transition-all active:scale-95 disabled:opacity-50"
          aria-label="Tomar foto"
        >
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2">
            <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" />
            <circle cx="12" cy="13" r="4" />
          </svg>
        </button>
      </div>

      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        onChange={handleFileChange}
        className="hidden"
      />
    </div>
  )
}

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const base64 = reader.result.split(',')[1]
      resolve(base64)
    }
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

function formatDate(dateStr) {
  const date = new Date(dateStr + 'T12:00:00')
  return date.toLocaleDateString('es-ES', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  })
}
