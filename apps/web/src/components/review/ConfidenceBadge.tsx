interface ConfidenceBadgeProps {
  confidence: number
  showPercentage?: boolean
  size?: 'sm' | 'md'
}

export const ConfidenceBadge = ({
  confidence,
  showPercentage = true,
  size = 'md'
}: ConfidenceBadgeProps) => {
  const getColorClass = () => {
    if (confidence >= 0.9) return 'bg-green-100 text-green-800'
    if (confidence >= 0.7) return 'bg-yellow-100 text-yellow-800'
    if (confidence >= 0.5) return 'bg-orange-100 text-orange-800'
    return 'bg-red-100 text-red-800'
  }

  const sizeClass = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-sm'

  return (
    <span className={`inline-flex items-center rounded-full font-medium ${getColorClass()} ${sizeClass}`}>
      {showPercentage ? `${Math.round(confidence * 100)}%` : confidence.toFixed(2)}
    </span>
  )
}
