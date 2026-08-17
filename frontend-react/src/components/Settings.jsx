import { useState, useEffect } from 'react'
import { getProfile, updateGoal } from '../api'

export default function Settings({ onLogout }) {
  const [profile, setProfile] = useState(null)
  const [newGoal, setNewGoal] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [success, setSuccess] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    loadProfile()
  }, [])

  const loadProfile = async () => {
    try {
      const data = await getProfile()
      setProfile(data)
      setNewGoal(data.daily_calorie_goal?.toString() || '')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleUpdateGoal = async (e) => {
    e.preventDefault()
    const goal = parseInt(newGoal)
    if (!goal || goal < 800 || goal > 5000) {
      setError('La meta debe estar entre 800-5000 kcal')
      return
    }

    setSaving(true)
    setError('')
    setSuccess('')

    try {
      await updateGoal(goal)
      setSuccess('Meta actualizada')
      setTimeout(() => setSuccess(''), 3000)
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
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
        <h1 className="text-xl font-bold text-white">Configuración</h1>
      </div>

      {/* Profile info */}
      {profile && (
        <div className="bg-dark-card border border-dark-border rounded-2xl p-6">
          <h3 className="text-white font-semibold mb-4">Perfil</h3>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <p className="text-secondary">Peso</p>
              <p className="text-white font-medium">{profile.weight_kg} kg</p>
            </div>
            <div>
              <p className="text-secondary">Altura</p>
              <p className="text-white font-medium">{profile.height_cm} cm</p>
            </div>
            <div>
              <p className="text-secondary">TDEE</p>
              <p className="text-white font-medium">{profile.tdee} kcal</p>
            </div>
            <div>
              <p className="text-secondary">Meta actual</p>
              <p className="text-accent font-medium">{profile.daily_calorie_goal} kcal</p>
            </div>
          </div>
        </div>
      )}

      {/* Update goal */}
      <div className="bg-dark-card border border-dark-border rounded-2xl p-6">
        <h3 className="text-white font-semibold mb-4">Ajustar meta diaria</h3>
        <form onSubmit={handleUpdateGoal} className="space-y-3">
          <input
            type="number"
            value={newGoal}
            onChange={(e) => { setNewGoal(e.target.value); setError(''); setSuccess('') }}
            placeholder="Calorías diarias"
            className="w-full px-4 py-3 bg-dark-bg border border-dark-border rounded-xl text-white placeholder-secondary focus:border-accent transition-colors"
          />
          <button
            type="submit"
            disabled={saving}
            className="w-full py-3 bg-accent text-white font-semibold rounded-xl hover:bg-emerald-600 transition-colors disabled:opacity-50"
          >
            {saving ? 'Guardando...' : 'Actualizar meta'}
          </button>
        </form>
        {success && <p className="text-accent text-sm text-center mt-3">{success}</p>}
        {error && <p className="text-danger text-sm text-center mt-3">{error}</p>}
      </div>

      {/* Logout */}
      <button
        onClick={onLogout}
        className="w-full py-3 border border-danger/50 text-danger rounded-xl hover:bg-danger/10 transition-colors font-medium"
      >
        Cerrar sesión
      </button>
    </div>
  )
}
