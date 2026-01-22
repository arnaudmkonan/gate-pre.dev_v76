import { Check, X, SkipForward, Loader } from 'lucide-react'
import { Button } from '../Button'

interface ReviewActionsProps {
  onApprove: () => void
  onReject: () => void
  onSkip: () => void
  isLoading?: boolean
  disabled?: boolean
}

export const ReviewActions = ({
  onApprove,
  onReject,
  onSkip,
  isLoading = false,
  disabled = false
}: ReviewActionsProps) => {
  return (
    <div className="flex items-center gap-3">
      <Button
        onClick={onApprove}
        disabled={disabled || isLoading}
        className="bg-green-600 hover:bg-green-700 text-white"
      >
        {isLoading ? (
          <Loader className="w-4 h-4 mr-2 animate-spin" />
        ) : (
          <Check className="w-4 h-4 mr-2" />
        )}
        Approve
      </Button>
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
