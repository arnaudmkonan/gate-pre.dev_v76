import { Check, X, SkipForward, Loader, ChevronRight } from 'lucide-react'
import { Button } from '../Button'

interface ReviewActionsProps {
  onApprove: () => void
  onApproveAndNext?: () => void
  onReject: () => void
  onSkip: () => void
  isLoading?: boolean
  disabled?: boolean
  hasNext?: boolean
}

export const ReviewActions = ({
  onApprove,
  onApproveAndNext,
  onReject,
  onSkip,
  isLoading = false,
  disabled = false,
  hasNext = false,
}: ReviewActionsProps) => {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <Button
        onClick={onApproveAndNext || onApprove}
        disabled={disabled || isLoading}
        className="bg-green-600 hover:bg-green-700 text-white"
      >
        {isLoading ? (
          <Loader className="w-4 h-4 mr-2 animate-spin" />
        ) : (
          <Check className="w-4 h-4 mr-2" />
        )}
        {hasNext && onApproveAndNext ? 'Approve & next' : 'Approve'}
        {hasNext && onApproveAndNext && <ChevronRight className="ml-1 h-4 w-4" />}
      </Button>
      {hasNext && onApproveAndNext && (
        <Button onClick={onApprove} variant="secondary" disabled={disabled || isLoading}>
          Approve only
        </Button>
      )}
      <Button
        onClick={onReject}
        variant="danger"
        disabled={disabled || isLoading}
      >
        <X className="w-4 h-4 mr-2" />
        Reject
      </Button>
      <Button
        onClick={onSkip}
        variant="secondary"
        disabled={disabled || isLoading}
      >
        <SkipForward className="w-4 h-4 mr-2" />
        Skip
      </Button>
    </div>
  )
}
