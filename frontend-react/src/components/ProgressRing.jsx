export default function ProgressRing({ consumed, goal }) {
  const percentage = Math.min((consumed / goal) * 100, 100)
  const radius = 80
  const strokeWidth = 12
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (percentage / 100) * circumference

  let color = '#10b981' // green
  if (percentage > 100) color = '#ef4444' // red
  else if (percentage > 80) color = '#f59e0b' // orange

  const remaining = Math.max(goal - consumed, 0)

  return (
    <div className="flex flex-col items-center">
      <div className="relative">
        <svg width="200" height="200" className="transform -rotate-90">
          {/* Background circle */}
          <circle
            cx="100"
            cy="100"
            r={radius}
            stroke="#2a2a5a"
            strokeWidth={strokeWidth}
            fill="none"
          />
          {/* Progress circle */}
          <circle
            cx="100"
            cy="100"
            r={radius}
            stroke={color}
            strokeWidth={strokeWidth}
            fill="none"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
            className="transition-all duration-1000 ease-out"
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-3xl font-bold text-white">{consumed}</span>
          <span className="text-secondary text-sm">/ {goal} kcal</span>
        </div>
      </div>
      <div className="mt-4 text-center">
        {consumed > goal ? (
          <p className="text-danger font-medium">
            Excedido por {consumed - goal} kcal
          </p>
        ) : (
          <p className="text-secondary">
            Quedan <span className="text-white font-medium">{remaining}</span> kcal
          </p>
        )}
      </div>
    </div>
  )
}
