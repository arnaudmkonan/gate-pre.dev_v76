import { QueueList } from '../components/QueueList'

export const QueuePage: React.FC = () => {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Job Queue</h1>
        <p className="text-gray-600 mt-2">
          Monitor and manage document processing jobs in the queue
        </p>
      </div>

      <QueueList autoRefresh={true} refreshInterval={2000} />
    </div>
  )
}
