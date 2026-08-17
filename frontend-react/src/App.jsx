import { useState } from 'react'
import { useAuth } from './hooks/useAuth'
import Login from './components/Login'
import Onboarding from './components/Onboarding'
import Dashboard from './components/Dashboard'
import WeeklyChart from './components/WeeklyChart'
import WeightTracker from './components/WeightTracker'
import Settings from './components/Settings'
import NavBar from './components/NavBar'

function App() {
  const { authenticated, loading, needsOnboarding, login, logout, completeOnboarding } = useAuth()
  const [activeTab, setActiveTab] = useState('today')

  if (loading) {
    return (
      <div className="min-h-screen bg-dark-bg flex items-center justify-center">
        <div className="text-white text-lg animate-pulse">Cargando...</div>
      </div>
    )
  }

  if (!authenticated) {
    return <Login onLogin={login} />
  }

  if (needsOnboarding) {
    return <Onboarding onComplete={completeOnboarding} />
  }

  return (
    <div className="min-h-screen bg-dark-bg flex flex-col items-center">
      <div className="w-full max-w-[480px] flex-1 pb-20">
        {activeTab === 'today' && <Dashboard />}
        {activeTab === 'weekly' && <WeeklyChart />}
        {activeTab === 'weight' && <WeightTracker />}
        {activeTab === 'settings' && <Settings onLogout={logout} />}
      </div>
      <NavBar activeTab={activeTab} onTabChange={setActiveTab} />
    </div>
  )
}

export default App
