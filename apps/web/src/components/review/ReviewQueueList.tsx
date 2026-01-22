import { ReviewItemCard } from './ReviewItemCard'

interface ReviewItem {
  id: string
  document_id: string
  filename?: string
  file_type?: string
  priority: number
  status: string
  reason: string
  reason_code?: string
  confidence_score?: number
  assigned_to?: string
  created_at: string
  issues_detected?: unknown[]
}

interface ReviewQueueListProps {
  items: ReviewItem[]
  onItemClick: (item: ReviewItem) => void
  emptyMessage?: string
}

export const ReviewQueueList = ({
  items,
  onItemClick,
  emptyMessage = 'No items in the review queue'
}: ReviewQueueListProps) => {
  if (items.length === 0) {
    return (
      <div className="text-center py-12 text-gray-500">
        {emptyMessage}
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {items.map((item) => (
        <ReviewItemCard
          key={item.id}
          item={item}
          onClick={() => onItemClick(item)}
        />
      ))}
    </div>
  )
}
