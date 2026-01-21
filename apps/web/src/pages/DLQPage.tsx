import { DLQPanel } from '../components/DLQPanel'

export const DLQPage: React.FC = () => {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold mb-2">Dead Letter Queue</h1>
        <p className="text-gray-600">Failed ingestion jobs awaiting manual review or reprocessing</p>
      </div>

      <DLQPanel />
    </div>
  )
}
