import { useState } from 'react'
import { createProfile } from '../api'

const ACTIVITY_LEVELS = [
  { value: 'sedentary', label: 'Sedentario', desc: 'Poco o ningún ejercicio' },
  { value: 'light', label: 'Ligero', desc: 'Ejercicio 1-3 días/semana' },
  { value: 'moderate', label: 'Moderado', desc: 'Ejercicio 3-5 días/semana' },
  { value: 'active', label: 'Activo', desc: 'Ejercicio 6-7 días/semana' },
  { value: 'very_active', label: 'Muy activo', desc: 'Ejercicio intenso diario' },
]

export default function Onboarding({ onComplete }) {
  const [step, setStep] = useState(0)
  const [data, setData] = useState({
    weight_kg: '',
    height_cm: '',
    age: '',
    sex: 'male',
    activity_level: 'moderate',
  })
  const [result, setResult] = useState(null)
  const [adjustedGoal, setAdjustedGoal] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const totalSteps = 4

  const validate = () => {
    if (step === 0) {
      const w = parseFloat(data.weight_kg)
      const h = parseFloat(data.height_cm)
      if (!w || w < 30 || w > 300) return 'Peso debe estar entre 30-300 kg'
      if (!h || h < 100 || h > 250) return 'Altura debe estar entre 100-250 cm'
    }
    if (step === 1) {
      const a = parseInt(data.age)
      if (!a || a < 13 || a > 120) return 'Edad debe estar entre 13-120 años'
    }
    return ''
  }

  const nextStep = () => {
    const err = validate()
    if (err) {
      setError(err)
      return
    }
    setError('')
    setStep(step + 1)
  }

  const handleSubmit = async () => {
    setLoading(true)
    setError('')
    try {
      const res = await createProfile({
        weight_kg: parseFloat(data.weight_kg),
        height_cm: parseFloat(data.height_cm),
        age: parseInt(data.age),
        sex: data.sex,
        activity_level: data.activity_level,
      })
      setResult(res)
      setAdjustedGoal(res.suggested_goal?.toString() || res.tdee?.toString() || '')
      setStep(3)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleFinish = async () => {
    onComplete()
  }

  const updateField = (field, value) => {
    setData({ ...data, [field]: value })
    setError('')
  }

  return (
    <div className="min-h-screen bg-dark-bg flex items-center justify-center px-4">
      <div className="w-full max-w-[400px] bg-dark-card border border-dark-border rounded-2xl p-8">
        {/* Progress dots */}
        <div className="flex justify-center gap-2 mb-8">
          {Array.from({ length: totalSteps }).map((_, i) => (
            <div
              key={i}
              className={`w-2.5 h-2.5 rounded-full transition-colors ${
                i <= step ? 'bg-accent' : 'bg-dark-border'
              }`}
            />
          ))}
        </div>

        {/* Step 0: Weight & Height */}
        {step === 0 && (
          <div className="space-y-6">
            <h2 className="text-xl font-bold text-white text-center">Peso y altura</h2>
            <div className="space-y-4">
              <div>
                <label className="text-secondary text-sm mb-1 block">Peso (kg)</label>
                <input
                  type="number"
                  value={data.weight_kg}
                  onChange={(e) => updateField('weight_kg', e.target.value)}
                  placeholder="70"
                  className="w-full px-4 py-3 bg-dark-bg border border-dark-border rounded-xl text-white placeholder-secondary focus:border-accent transition-colors"
                />
              </div>
              <div>
                <label className="text-secondary text-sm mb-1 block">Altura (cm)</label>
                <input
                  type="number"
                  value={data.height_cm}
                  onChange={(e) => updateField('height_cm', e.target.value)}
                  placeholder="170"
                  className="w-full px-4 py-3 bg-dark-bg border border-dark-border rounded-xl text-white placeholder-secondary focus:border-accent transition-colors"
                />
              </div>
            </div>
          </div>
        )}

        {/* Step 1: Age & Sex */}
        {step === 1 && (
          <div className="space-y-6">
            <h2 className="text-xl font-bold text-white text-center">Edad y sexo</h2>
            <div className="space-y-4">
              <div>
                <label className="text-secondary text-sm mb-1 block">Edad</label>
                <input
                  type="number"
                  value={data.age}
                  onChange={(e) => updateField('age', e.target.value)}
                  placeholder="25"
                  className="w-full px-4 py-3 bg-dark-bg border border-dark-border rounded-xl text-white placeholder-secondary focus:border-accent transition-colors"
                />
              </div>
              <div>
                <label className="text-secondary text-sm mb-2 block">Sexo</label>
                <div className="flex gap-3">
                  <button
                    type="button"
                    onClick={() => updateField('sex', 'male')}
                    className={`flex-1 py-3 rounded-xl border transition-colors ${
                      data.sex === 'male'
                        ? 'border-accent bg-accent/10 text-accent'
                        : 'border-dark-border text-secondary'
                    }`}
                  >
                    Masculino
                  </button>
                  <button
                    type="button"
                    onClick={() => updateField('sex', 'female')}
                    className={`flex-1 py-3 rounded-xl border transition-colors ${
                      data.sex === 'female'
                        ? 'border-accent bg-accent/10 text-accent'
                        : 'border-dark-border text-secondary'
                    }`}
                  >
                    Femenino
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Step 2: Activity Level */}
        {step === 2 && (
          <div className="space-y-6">
            <h2 className="text-xl font-bold text-white text-center">Nivel de actividad</h2>
            <div className="space-y-2">
              {ACTIVITY_LEVELS.map((level) => (
                <button
                  key={level.value}
                  type="button"
                  onClick={() => updateField('activity_level', level.value)}
                  className={`w-full text-left px-4 py-3 rounded-xl border transition-colors ${
                    data.activity_level === level.value
                      ? 'border-accent bg-accent/10'
                      : 'border-dark-border'
                  }`}
                >
                  <div className={data.activity_level === level.value ? 'text-accent' : 'text-white'}>
                    {level.label}
                  </div>
                  <div className="text-secondary text-xs">{level.desc}</div>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Step 3: Result */}
        {step === 3 && result && (
          <div className="space-y-6">
            <h2 className="text-xl font-bold text-white text-center">Tu plan</h2>
            <div className="text-center space-y-4">
              <div className="bg-dark-bg rounded-xl p-6 border border-dark-border">
                <p className="text-secondary text-sm">Tu TDEE estimado</p>
                <p className="text-3xl font-bold text-white mt-1">{result.tdee} kcal</p>
              </div>
              <div className="bg-dark-bg rounded-xl p-6 border border-dark-border">
                <p className="text-secondary text-sm">Meta diaria sugerida</p>
                <p className="text-3xl font-bold text-accent mt-1">{result.suggested_goal} kcal</p>
              </div>
              <div>
                <label className="text-secondary text-sm mb-1 block">Ajustar meta (kcal)</label>
                <input
                  type="number"
                  value={adjustedGoal}
                  onChange={(e) => setAdjustedGoal(e.target.value)}
                  className="w-full px-4 py-3 bg-dark-bg border border-dark-border rounded-xl text-white text-center focus:border-accent transition-colors"
                />
              </div>
            </div>
          </div>
        )}

        {/* Error */}
        {error && (
          <p className="text-danger text-sm text-center mt-4">{error}</p>
        )}

        {/* Navigation buttons */}
        <div className="mt-8 flex gap-3">
          {step > 0 && step < 3 && (
            <button
              onClick={() => { setStep(step - 1); setError('') }}
              className="flex-1 py-3 border border-dark-border text-secondary rounded-xl hover:border-accent hover:text-white transition-colors"
            >
              Atrás
            </button>
          )}
          {step < 2 && (
            <button
              onClick={nextStep}
              className="flex-1 py-3 bg-accent text-white font-semibold rounded-xl hover:bg-emerald-600 transition-colors"
            >
              Siguiente
            </button>
          )}
          {step === 2 && (
            <button
              onClick={handleSubmit}
              disabled={loading}
              className="flex-1 py-3 bg-accent text-white font-semibold rounded-xl hover:bg-emerald-600 transition-colors disabled:opacity-50"
            >
              {loading ? 'Calculando...' : 'Calcular'}
            </button>
          )}
          {step === 3 && (
            <button
              onClick={handleFinish}
              className="flex-1 py-3 bg-accent text-white font-semibold rounded-xl hover:bg-emerald-600 transition-colors"
            >
              Comenzar
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
